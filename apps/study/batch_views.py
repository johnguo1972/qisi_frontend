"""批量操作视图。"""
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from apps.study.models import QuestionBasket, Favorite


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_update(request):
    """
    批量操作题目。
    action: 'delete' | 'confirm' | 'reject' | 'add_to_favorites' | 'set_difficulty' | 'set_knowledge_point'
    """
    ids = request.data.get('ids', [])
    action = request.data.get('action', '')
    value = request.data.get('value')

    if not ids:
        return Response({'code': 400, 'message': '缺少ids', 'data': None, 'trace_id': make_trace_id()}, status=400)

    if action not in ('delete', 'confirm', 'reject', 'add_to_favorites', 'set_difficulty', 'set_knowledge_point'):
        return Response({'code': 400, 'message': f'不支持的操作: {action}', 'data': None, 'trace_id': make_trace_id()}, status=400)

    success_count = 0
    errors = []

    for qid in ids:
        try:
            if action == 'delete':
                QuestionImage.objects.filter(question_id=qid).delete()
                QuestionOption.objects.filter(question_id=qid).delete()
                ExamQuestion.objects.filter(id=qid).delete()
            elif action == 'confirm':
                ExamQuestion.objects.filter(id=qid).update(review_status='confirmed', need_review=False)
            elif action == 'reject':
                ExamQuestion.objects.filter(id=qid).update(review_status='rejected', need_review=True)
            elif action == 'add_to_favorites':
                Favorite.objects.get_or_create(user=request.user, question_id=qid)
            elif action == 'set_difficulty':
                ExamQuestion.objects.filter(id=qid).update(difficulty=value)
            elif action == 'set_knowledge_point':
                q = ExamQuestion.objects.get(id=qid)
                kps = q.knowledge_points or []
                kps.append(value)
                q.knowledge_points = kps
                q.save(update_fields=['knowledge_points'])

            success_count += 1
        except Exception as e:
            errors.append({'id': str(qid), 'error': str(e)})

    return Response({
        'code': 0,
        'message': f'成功处理 {success_count} 题',
        'data': {'success': success_count, 'errors': errors[:10]},
        'trace_id': make_trace_id(),
    })
