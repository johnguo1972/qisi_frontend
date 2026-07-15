"""学生知识掌握度：按知识点聚合作答正确率，含树形结构。"""
import uuid
from collections import defaultdict
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.permissions import IsStudent
from .models import AnswerAttempt


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def knowledge_mastery(request):
    """GET /api/v1/student/knowledge-mastery
    返回每个知识点的 attempt/correct/accuracy（排除主观题待批阅）。弱项在前。
    新增 tree 字段：学科→学段→年级→知识点 的树形结构。
    """
    attempts = AnswerAttempt.objects.filter(
        student_user_id=request.user, is_subjective_pending=False
    )
    qids = [a.question_id for a in attempts]
    q_map = {q.id: q for q in ExamQuestion.objects.filter(id__in=qids)}

    agg = defaultdict(lambda: {'attempt': 0, 'correct': 0})
    for a in attempts:
        q = q_map.get(a.question_id)
        if not q:
            continue
        for kp in (q.knowledge_points or []):
            label = (kp.get('module') if isinstance(kp, dict) else str(kp)) or '未分类'
            agg[label]['attempt'] += 1
            if a.is_correct:
                agg[label]['correct'] += 1

    items = []
    for label, v in agg.items():
        acc = round(v['correct'] / max(v['attempt'], 1) * 100, 1)
        items.append({
            'knowledge': label,
            'attempt': v['attempt'],
            'correct': v['correct'],
            'accuracy': acc,
            'mastery': 'mastered' if acc >= 85 else ('reviewing' if acc >= 60 else 'weak'),
        })
    items.sort(key=lambda x: x['accuracy'])  # 弱项在前

    # 新增：组织树形结构（按 knowledge_points 表层级）
    from apps.knowledge.models import KnowledgePoint
    kp_names = [item['knowledge'] for item in items]
    kp_records = KnowledgePoint.objects.filter(
        module__in=kp_names
    ).values('module', 'subject', 'stage', 'grade_index', 'grade_name', 'chapter')
    kp_map = {r['module']: r for r in kp_records}

    # 构建树：subject -> stage -> grade -> [knowledge items]
    tree = {}
    kp_label_map = dict(KnowledgePoint.SUBJECT_CHOICES)
    stage_label_map = KnowledgePoint.STAGE_LABELS
    grade_label_map = KnowledgePoint.GRADE_LABELS

    for item in items:
        kp = kp_map.get(item['knowledge'])
        if not kp:
            continue
        subj = kp['subject']
        stage = kp['stage']
        grade_key = f"{kp['grade_index']}_{kp['grade_name']}"

        # 学科层
        if subj not in tree:
            tree[subj] = {
                'name': kp_label_map.get(subj, subj),
                'type': 'subject',
                'children': {},
            }
        # 学段层
        stage_node = tree[subj]['children']
        if stage not in stage_node:
            stage_node[stage] = {
                'name': stage_label_map.get(stage, stage),
                'type': 'stage',
                'children': {},
            }
        # 年级层
        grade_node = stage_node[stage]['children']
        if grade_key not in grade_node:
            grade_node[grade_key] = {
                'name': grade_label_map.get(kp['grade_index'], kp['grade_name']),
                'type': 'grade',
                'children': [],
            }
        grade_node[grade_key]['children'].append({
            'name': item['knowledge'],
            'type': 'knowledge',
            'accuracy': item['accuracy'],
            'mastery': item['mastery'],
            'attempt': item['attempt'],
            'correct': item['correct'],
        })

    # 扁平化树
    def flatten(node):
        if isinstance(node, dict) and 'children' in node:
            children = node['children']
            if isinstance(children, dict):
                node['children'] = [flatten(v) for v in children.values()]
            elif isinstance(children, list):
                node['children'] = [flatten(c) for c in children]
        return node

    tree_data = [flatten(v) for v in tree.values()]

    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {
                         'items': items,        # 列表（保持原有）
                         'tree': tree_data,     # 树形（新增）
                         'total': len(items),
                     }})
