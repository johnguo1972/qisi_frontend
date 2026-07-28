"""标签管理视图。"""
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.study.models import QuestionTag, QuestionTagRelation
from apps.parser.models import ExamQuestion


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tag_list(request):
    """获取标签列表（支持按名称搜索）。"""
    search = request.GET.get('search', '')
    qs = QuestionTag.objects.all()
    if search:
        qs = qs.filter(name__icontains=search)
    qs = qs.order_by('-question_count')

    items = [{
        'id': str(t.id),
        'name': t.name,
        'color': t.color,
        'question_count': t.question_count,
    } for t in qs]

    return Response({'code': 0, 'data': items, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tag_create(request):
    """创建新标签。"""
    name = request.data.get('name', '').strip()
    if not name:
        return Response({'code': 400, 'message': '标签名不能为空', 'data': None, 'trace_id': make_trace_id()}, status=400)

    if QuestionTag.objects.filter(name=name).exists():
        return Response({'code': 409, 'message': '标签已存在', 'data': None, 'trace_id': make_trace_id()}, status=409)

    tag = QuestionTag.objects.create(
        name=name,
        color=request.data.get('color', '#409eff'),
        created_by=request.user,
    )
    return Response({
        'code': 0, 'message': '创建成功',
        'data': {'id': str(tag.id), 'name': tag.name, 'color': tag.color},
        'trace_id': make_trace_id(),
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def tag_update(request, tag_id):
    """更新标签。"""
    try:
        tag = QuestionTag.objects.get(pk=tag_id)
    except QuestionTag.DoesNotExist:
        return Response({'code': 404, 'message': '标签不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    name = request.data.get('name', '').strip()
    if name and name != tag.name:
        if QuestionTag.objects.filter(name=name).exclude(pk=tag_id).exists():
            return Response({'code': 409, 'message': '标签名已被使用', 'data': None, 'trace_id': make_trace_id()}, status=409)
        tag.name = name

    if 'color' in request.data:
        tag.color = request.data['color']

    tag.save()
    return Response({'code': 0, 'message': '更新成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def tag_delete(request, tag_id):
    """删除标签（同时删除关联关系）。"""
    try:
        tag = QuestionTag.objects.get(pk=tag_id)
    except QuestionTag.DoesNotExist:
        return Response({'code': 404, 'message': '标签不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    QuestionTagRelation.objects.filter(tag=tag).delete()
    tag.delete()
    return Response({'code': 0, 'message': '删除成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_tags(request, question_id):
    """获取题目的标签列表。"""
    relations = QuestionTagRelation.objects.filter(question_id=question_id).select_related('tag')
    items = [{
        'id': str(r.tag.id),
        'name': r.tag.name,
        'color': r.tag.color,
    } for r in relations]
    return Response({'code': 0, 'data': items, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_add_tag(request, question_id):
    """给题目添加标签。"""
    tag_id = request.data.get('tag_id')
    tag_name = request.data.get('tag_name', '').strip()

    # 如果提供了tag_name但没有tag_id，自动创建标签
    if not tag_id and tag_name:
        tag, _ = QuestionTag.objects.get_or_create(
            name=tag_name,
            defaults={'created_by': request.user}
        )
        tag_id = tag.id

    if not tag_id:
        return Response({'code': 400, 'message': '缺少tag_id或tag_name', 'data': None, 'trace_id': make_trace_id()}, status=400)

    _, created = QuestionTagRelation.objects.get_or_create(
        question_id=question_id,
        tag_id=tag_id,
    )

    # 更新标签的题目计数
    if created:
        QuestionTag.objects.filter(pk=tag_id).update(
            question_count=QuestionTagRelation.objects.filter(tag_id=tag_id).count()
        )

    return Response({
        'code': 0,
        'message': '已添加' if created else '已在标签中',
        'data': None,
        'trace_id': make_trace_id(),
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def question_remove_tag(request, question_id, tag_id):
    """移除题目的标签。"""
    QuestionTagRelation.objects.filter(question_id=question_id, tag_id=tag_id).delete()
    QuestionTag.objects.filter(pk=tag_id).update(
        question_count=QuestionTagRelation.objects.filter(tag_id=tag_id).count()
    )
    return Response({'code': 0, 'message': '已移除', 'data': None, 'trace_id': make_trace_id()})
