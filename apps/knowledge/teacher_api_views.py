"""Teacher API endpoints for knowledge tree."""
import logging
import re
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.knowledge.models import KnowledgePoint
from apps.parser.models import ExamQuestion
from apps.knowledge.teacher_scope import (
    TeachingScopeForbidden,
    apply_stage_scope,
    resolve_teacher_question_scope,
)

logger = logging.getLogger(__name__)

# Extract chapter number for sorting: "第一章" -> 1, "第二十九章" -> 29, "专题" -> 99
_CHAPTER_NUM_RE = re.compile(r'第([一二三四五六七八九十\d]+)[章节篇]')
_CHINESE_NUMS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _parse_chinese_numeral(text):
    """Parse Chinese numeral: 二十一->21, 十二->12, 十->10, 3->3."""
    if text.isdigit():
        return int(text)
    if text in _CHINESE_NUMS:
        return _CHINESE_NUMS[text]
    # Composite: 二十一, 三十一, etc.
    result = 0
    i = 0
    while i < len(text):
        if text[i] == '十':
            if i == 0:
                result += 10
            elif i > 0 and text[i-1] in _CHINESE_NUMS:
                result += _CHINESE_NUMS[text[i-1]] * 10
            else:
                result += 10
            i += 1
        elif text[i] in _CHINESE_NUMS:
            if i + 1 < len(text) and text[i+1] == '十':
                pass
            else:
                result += _CHINESE_NUMS[text[i]]
            i += 1
        else:
            i += 1
    return result


def _chapter_sort_key(chapter_name):
    """Extract numeric chapter index for proper sorting."""
    match = _CHAPTER_NUM_RE.search(chapter_name)
    if not match:
        return 99
    text = match.group(1)
    return _parse_chinese_numeral(text)


def _deduplicate_knowledge_points(knowledge_points):
    """Remove duplicate point names while preserving the first point's data."""
    unique_points = []
    seen_names = set()
    for point in knowledge_points:
        name = str(point.get('name') or '').strip()
        if name in seen_names:
            continue
        seen_names.add(name)
        unique_points.append(point)
    return unique_points


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knowledge_tree(request):
    """Get knowledge point tree filtered by teacher's subject and stage.

    Returns hierarchical structure: grades -> semesters(上学期/下学期) -> chapters -> knowledge_points
    (module level is removed, knowledge points are directly under chapters)
    """
    try:
        scope = resolve_teacher_question_scope(
            request,
            requested_subject=request.query_params.get('subject', ''),
            requested_stages=request.query_params.get('stages', '') or request.query_params.get('stage', ''),
        )
    except TeachingScopeForbidden:
        return Response({
            'code': 'TEACHING_SCOPE_FORBIDDEN',
            'message': 'Requested subject or stage is outside the teacher teaching scope.',
            'data': None,
        }, status=403)

    if scope is not None and not scope.configured:
        return Response({'success': True, 'data': {
            'grades': [],
            'allowed_subjects': list(scope.subjects),
            'allowed_stages': list(scope.stages),
            'selected_subject': None,
            'scope_configured': False,
        }})

    subject = request.query_params.get('subject', '')
    stage = request.query_params.get('stage', '')

    # Map Chinese names to database values (pass-through if already DB value)
    subject_map = {'数学': 'math', '语文': 'chinese', '英语': 'english', '物理': 'physics', '化学': 'chemistry'}
    stage_map = {'小学': 'primary', '初中': 'junior', '高中': 'senior'}

    db_subject = subject_map.get(subject, subject)

    # Handle multiple stages (comma-separated: "初中,高中" -> ["junior", "senior"])
    stage_param = request.query_params.get('stages', '')
    if not stage_param:
        stage_param = request.query_params.get('stage', '')
    db_stages = []
    for s in stage_param.split(','):
        s = s.strip()
        mapped = stage_map.get(s, s)
        if mapped in {'primary', 'junior', 'senior'}:
            db_stages.append(mapped)

    if scope is not None:
        db_subject = scope.selected_subject
        db_stages = list(scope.stages)

    # Term display mapping: up -> 上学期, down -> 下学期
    TERM_DISPLAY = {'up': '上学期', 'down': '下学期'}

    # --- Count questions per knowledge point ---
    kp_counts = {}
    unclassified_count = 0
    try:
        qs_questions = ExamQuestion.objects.filter(knowledge_points__isnull=False)
        if db_subject:
            qs_questions = qs_questions.filter(subject=db_subject)
        if db_stages:
            qs_questions = apply_stage_scope(qs_questions, tuple(db_stages))
        qs_questions = qs_questions.values_list('knowledge_points', flat=True)
        for kps in qs_questions:
            if not kps:
                unclassified_count += 1
            elif isinstance(kps, list):
                for item in kps:
                    if isinstance(item, dict):
                        for key in (str(item.get('id')), item.get('module')):
                            if key and key != 'None':
                                kp_counts[key] = kp_counts.get(key, 0) + 1
                    elif item:
                        key = str(item)
                        kp_counts[key] = kp_counts.get(key, 0) + 1
    except Exception as e:
        logger.warning('Failed to aggregate question counts: %s', e)

    # Query knowledge points
    qs = KnowledgePoint.objects.all()
    if db_subject:
        qs = qs.filter(subject=db_subject)
    if db_stages:
        qs = qs.filter(stage__in=db_stages)

    # Order: up (上学期) before down (下学期)
    qs = qs.order_by('grade_index', 'term', 'chapter', 'node_type')

    # Build tree structure: grade -> term(up first) -> chapter -> knowledge_points
    tree = {}
    for kp in qs:
        grade_key = kp.grade_name or '未分类'
        term_display = TERM_DISPLAY.get(kp.term, kp.term)
        chapter_key = kp.chapter or '未分类'

        if grade_key not in tree:
            tree[grade_key] = {'_idx': kp.grade_index, 'semesters': {}}
        if term_display not in tree[grade_key]['semesters']:
            tree[grade_key]['semesters'][term_display] = {'_order': 0 if kp.term == 'up' else 1, 'chapters': {}}
        if chapter_key not in tree[grade_key]['semesters'][term_display]['chapters']:
            tree[grade_key]['semesters'][term_display]['chapters'][chapter_key] = []

        tree[grade_key]['semesters'][term_display]['chapters'][chapter_key].append({
            'id': kp.id,
            'name': kp.module if kp.module else kp.chapter,
            'question_count': kp_counts.get(str(kp.id), 0) or kp_counts.get(kp.module, 0),
        })

    # Convert to list format, sort semesters so 上学期 comes before 下学期
    result = []
    for grade_name in sorted(tree.keys(), key=lambda g: tree[g].get('_idx', 99)):
        grade_data = tree[grade_name]
        grade_obj = {'name': grade_name, 'semesters': [], 'question_count': 0}
        # Sort semesters: 上学期 (_order=0) before 下学期 (_order=1)
        sorted_semesters = sorted(grade_data['semesters'].items(), key=lambda x: x[1].get('_order', 99))
        for sem_name, sem_data in sorted_semesters:
            sem_obj = {'name': sem_name, 'chapters': [], 'question_count': 0}
            # Sort chapters by chapter number (extract numeric part)
            sorted_chapters = sorted(sem_data['chapters'].items(), key=lambda x: _chapter_sort_key(x[0]))
            for ch_name, kps in sorted_chapters:
                kps = _deduplicate_knowledge_points(kps)
                ch_question_count = sum(kp.get('question_count', 0) for kp in kps)
                ch_obj = {'name': ch_name, 'knowledge_points': kps, 'question_count': ch_question_count}
                sem_obj['chapters'].append(ch_obj)
                sem_obj['question_count'] += ch_question_count

            # Ensure "未分类" chapter always exists under each semester
            has_unclassified = any(ch['name'] == '未分类' for ch in sem_obj['chapters'])
            if not has_unclassified:
                sem_obj['chapters'].append({
                    'name': '未分类',
                    'knowledge_points': [{'id': -1, 'name': '未分类', 'question_count': unclassified_count}],
                    'question_count': unclassified_count,
                })

            grade_obj['semesters'].append(sem_obj)
            grade_obj['question_count'] += sem_obj['question_count']
        result.append(grade_obj)

    data = {'grades': result}
    if scope is not None:
        data.update({
            'allowed_subjects': list(scope.subjects),
            'allowed_stages': list(scope.stages),
            'selected_subject': scope.selected_subject,
            'scope_configured': True,
        })
    return Response({'success': True, 'data': data})
