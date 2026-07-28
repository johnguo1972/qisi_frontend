"""题目篮子视图：类似购物车，用于批量操作和组卷。"""
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.study.models import QuestionBasket


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def basket_list(request):
    """获取当前用户的题目篮子。"""
    items = QuestionBasket.objects.filter(user=request.user)
    return Response({
        'code': 0, 'message': 'success',
        'data': [{'question_id': str(item.question_id), 'added_at': item.added_at.isoformat()} for item in items],
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def basket_add(request):
    """添加题目到篮子。"""
    question_id = request.data.get('question_id')
    if not question_id:
        return Response({'code': 400, 'message': '缺少question_id', 'data': None, 'trace_id': make_trace_id()}, status=400)

    obj, created = QuestionBasket.objects.get_or_create(
        user=request.user,
        question_id=question_id,
    )
    if not created:
        return Response({'code': 409, 'message': '已在篮子中', 'data': None, 'trace_id': make_trace_id()}, status=409)

    return Response({'code': 0, 'message': '已加入篮子', 'data': None, 'trace_id': make_trace_id()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def basket_remove(request, question_id):
    """从篮子移除题目。"""
    QuestionBasket.objects.filter(user=request.user, question_id=question_id).delete()
    return Response({'code': 0, 'message': '已移除', 'data': None, 'trace_id': make_trace_id()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def basket_clear(request):
    """清空篮子。"""
    count = QuestionBasket.objects.filter(user=request.user).count()
    QuestionBasket.objects.filter(user=request.user).delete()
    return Response({'code': 0, 'message': f'已清空 {count} 题', 'data': None, 'trace_id': make_trace_id()})
