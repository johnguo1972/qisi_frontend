"""Dictionary views: subjects, knowledge points, question types, difficulty levels."""
import uuid
import logging
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.knowledge.models import KnowledgePoint
from apps.parser.models import ExamQuestion

logger = logging.getLogger(__name__)


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subjects(request):
    """DICT-01: Subject list."""
    try:
        subjects_from_db = KnowledgePoint.objects.values_list('subject', flat=True).distinct()
        subject_list = [
            {'code': s, 'name': dict(KnowledgePoint.SUBJECT_CHOICES).get(s, s)}
            for s in subjects_from_db
        ]
    except Exception:
        subject_list = [
            {'code': 'math', 'name': '数学'},
            {'code': 'physics', 'name': '物理'},
            {'code': 'chemistry', 'name': '化学'},
        ]
    return Response({
        'code': 0, 'message': 'success',
        'data': subject_list,
        'trace_id': make_trace_id(),
    })


def _count_questions_for_kp(kp_id: int) -> int:
    """Count questions that have the given knowledge point ID in their knowledge_points JSON."""
    return ExamQuestion.objects.filter(
        knowledge_points__contains=[{'id': kp_id}]
    ).count()


def _count_unclassified_questions(subject: str = '') -> int:
    """Count questions with empty or null knowledge_points (optionally filtered by subject)."""
    qs = ExamQuestion.objects.filter(
        Q(knowledge_points__isnull=True) | Q(knowledge_points=[]),
        parse_status__in=('photo_created', 'reviewing', 'reviewed'),
    )
    if subject:
        paper_subject_map = {'math': 'M', 'physics': 'P', 'chemistry': 'C'}
        subj_code = paper_subject_map.get(subject, '')
        if subj_code:
            qs = qs.filter(paper__subject=subj_code)
        else:
            qs = qs.filter(paper__subject=subject)
    return qs.distinct().count()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knowledge_points(request):
    """DICT-02: Knowledge tree (学年 -> 学期 -> 知识点 + 未分类).

    Returns a hierarchical tree for the new-question page sidebar.
    """
    subject = request.GET.get('subject')
    stages = request.GET.get('stages')  # comma-separated: '初中,高中'

    qs = KnowledgePoint.objects.all()

    stage_map = {'小学': 'primary', '初中': 'junior', '高中': 'senior'}

    # Filter by teacher's subject
    if subject:
        qs = qs.filter(subject=subject)
    elif request.user.is_authenticated and getattr(request.user, 'subject', None):
        qs = qs.filter(subject=request.user.subject)

    # Filter by teacher's stages
    if stages:
        stage_list = [s.strip() for s in stages.split(',') if s.strip()]
        db_stages = [stage_map.get(s, s) for s in stage_list]
        qs = qs.filter(stage__in=db_stages)
    elif request.user.is_authenticated and getattr(request.user, 'stages', None):
        user_stages = request.user.stages
        logger.info(f'[dict] user={request.user.id} stages={user_stages} type={type(user_stages).__name__}')
        # stages can be list or str — normalize to list
        if isinstance(user_stages, str):
            stage_list = [s.strip() for s in user_stages.split(',') if s.strip()]
        elif isinstance(user_stages, (list, tuple)):
            stage_list = [str(s).strip() for s in user_stages if s]
        else:
            stage_list = []
        logger.info(f'[dict] stage_list={stage_list}')
        db_stages = [stage_map.get(s, s) for s in stage_list]
        logger.info(f'[dict] db_stages={db_stages}')
        if db_stages:
            qs = qs.filter(stage__in=db_stages)

    qs = qs.order_by('grade_index', 'term', 'module')

    logger.info(f'[dict] after filtering: qs.count()={qs.count()}, user={request.user.id}, subject={subject or getattr(request.user, "subject", None)}')

    # Build tree: grade -> term -> knowledge_points
    tree = {}
    TERM_DISPLAY = {'up': '上学期', 'down': '下学期'}

    for kp in qs:
        grade_name = kp.grade_name or '未分类'
        grade_idx = kp.grade_index or 99
        term_display = TERM_DISPLAY.get(kp.term, kp.term)
        term_order = 0 if kp.term == 'up' else 1

        if grade_name not in tree:
            tree[grade_name] = {'_idx': grade_idx, 'terms': {}}
        if term_display not in tree[grade_name]['terms']:
            tree[grade_name]['terms'][term_display] = {'_order': term_order, 'kps': [], '_seen': set()}

        # Deduplicate by module name within same grade+term
        if kp.module and kp.module not in tree[grade_name]['terms'][term_display]['_seen']:
            tree[grade_name]['terms'][term_display]['_seen'].add(kp.module)
            q_count = _count_questions_for_kp(kp.id)
            tree[grade_name]['terms'][term_display]['kps'].append({
                'id': kp.id,
                'label': kp.module,
                'question_count': q_count,
            })

    # Convert to list format
    effective_subject = subject or ''
    result = []
    for grade_name in sorted(tree.keys(), key=lambda g: tree[g].get('_idx', 99)):
        grade_node = {
            'id': f'grade_{grade_name}',
            'content': grade_name,
            'label': grade_name,
            'children': [],
        }
        sorted_terms = sorted(tree[grade_name]['terms'].items(), key=lambda x: x[1].get('_order', 99))
        for term_name, term_data in sorted_terms:
            term_node = {
                'id': f'term_{grade_name}_{term_name}',
                'content': term_name,
                'label': term_name,
                'children': list(term_data['kps']),  # copy
            }
            # Add "未分类" node at the end of each term
            unc_count = _count_unclassified_questions(effective_subject)
            if unc_count > 0 or term_data['kps']:
                term_node['children'].append({
                    'id': -1,
                    'label': '未分类',
                    'question_count': unc_count,
                    'is_unclassified': True,
                })
            grade_node['children'].append(term_node)
        result.append(grade_node)

    logger.info(f'[dict] returning {len(result)} grades')
    return Response({
        'code': 0, 'message': 'success',
        'data': result,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_types(request):
    """DICT-03: Question type dict."""
    return Response({
        'code': 0, 'message': 'success',
        'data': [
            {'code': 'single_choice', 'name': '单选题'},
            {'code': 'multiple_choice', 'name': '多选题'},
            {'code': 'fill_blank', 'name': '填空题'},
            {'code': 'short_answer', 'name': '简答题'},
            {'code': 'essay', 'name': '作文题'},
            {'code': 'proof', 'name': '证明题'},
            {'code': 'computation', 'name': '计算题'},
            {'code': 'subjective', 'name': '主观题'},
        ],
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def difficulty_levels(request):
    """DICT-04: Difficulty levels."""
    return Response({
        'code': 0, 'message': 'success',
        'data': [
            {'code': '1.00', 'name': '基础巩固'},
            {'code': '2.00', 'name': '边界挑战'},
            {'code': '3.00', 'name': '专项突破'},
        ],
        'trace_id': make_trace_id(),
    })
