"""学生知识掌握度：按知识点聚合作答正确率。"""
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

    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {'items': items, 'total': len(items)}})
