"""课程管理 REST API Views"""
import os
import uuid
import logging
import mimetypes
from django.conf import settings
from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from .models import Course, CourseMaterial, CourseTree, VariantTask
from .serializers import (
    CourseSerializer,
    CourseMaterialSerializer,
    CourseTreeSerializer,
    CourseTreeNestedSerializer,
    VariantTaskSerializer,
)

logger = logging.getLogger(__name__)


# ============================================================
# 权限辅助函数
# ============================================================

def _check_course_owner(course, user):
    """验证用户是否为课程创建者（老师）"""
    if course.teacher != user:
        raise PermissionDenied('您没有权限操作此课程')


def _get_course_or_404(course_id):
    """获取课程，不存在则抛 404"""
    try:
        return Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        raise NotFound(f'课程 {course_id} 不存在')


# ============================================================
# 课程 CRUD
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_list(request):
    """当前老师的课程列表（is_deleted=False）"""
    courses = Course.objects.filter(
        teacher=request.user,
        is_deleted=False
    ).order_by('-created_at')
    serializer = CourseSerializer(courses, many=True, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def course_create(request):
    """创建课程"""
    serializer = CourseSerializer(
        data=request.data,
        context={'request': request}
    )
    serializer.is_valid(raise_exception=True)
    course = serializer.save()
    return Response(
        {'success': True, 'data': CourseSerializer(course, context={'request': request}).data, 'message': '课程创建成功'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_detail(request, course_id):
    """课程详情"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)
    serializer = CourseSerializer(course, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def course_update(request, course_id):
    """修改课程"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)
    serializer = CourseSerializer(course, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    course = serializer.save()
    return Response({'success': True, 'data': CourseSerializer(course, context={'request': request}).data, 'message': '课程更新成功'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def course_delete(request, course_id):
    """软删除课程"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)
    course.is_deleted = True
    course.save(update_fields=['is_deleted'])
    return Response({'success': True, 'message': '课程已删除'})


# ============================================================
# 课程资料
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_list(request, course_id):
    """课程资料列表（排除软删除）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)
    materials = CourseMaterial.objects.filter(
        course=course,
        is_deleted=False,
    ).order_by('-created_at')
    serializer = CourseMaterialSerializer(materials, many=True, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def material_upload(request, course_id):
    """上传文件到课程资料（50MB 限制）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    if 'file' not in request.FILES:
        raise ValidationError('请求中未包含文件')

    uploaded_file = request.FILES['file']

    # 50MB 限制
    max_size = 50 * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValidationError(f'文件大小超过 50MB 限制（当前: {uploaded_file.size / 1024 / 1024:.1f}MB）')

    # 保存到 MEDIA_ROOT/courses/{course_id}/materials/
    save_dir = os.path.join(settings.MEDIA_ROOT, 'courses', str(course_id), 'materials')
    os.makedirs(save_dir, exist_ok=True)

    # UUID 文件名避免冲突
    ext = os.path.splitext(uploaded_file.name)[1]
    filename = f'{uuid.uuid4().hex}{ext}'
    file_path = os.path.join(save_dir, filename)

    with open(file_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    # 推断 MIME 类型
    mime_type, _ = mimetypes.guess_type(uploaded_file.name)
    if not mime_type:
        mime_type = uploaded_file.content_type or 'application/octet-stream'

    # 获取文件类型（扩展名，不含点）
    file_type = ext.lstrip('.').lower() if ext else 'unknown'

    # 创建资料记录
    material = CourseMaterial.objects.create(
        course=course,
        name=uploaded_file.name,
        file_path=f'courses/{course_id}/materials/{filename}',
        file_type=file_type,
        file_size=uploaded_file.size,
        mime_type=mime_type,
        uploaded_by=request.user,
    )

    serializer = CourseMaterialSerializer(material, context={'request': request})
    return Response(
        {'success': True, 'data': serializer.data, 'message': '文件上传成功'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_download(request, course_id, material_id):
    """下载课程资料"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    full_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
    if not os.path.exists(full_path):
        raise NotFound('文件不存在')

    response = FileResponse(
        open(full_path, 'rb'),
        content_type=material.mime_type,
    )
    response['Content-Disposition'] = f'attachment; filename="{material.name}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_preview(request, course_id, material_id):
    """预览课程资料（图片直出，PDF/Word 返回 URL）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    full_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
    if not os.path.exists(full_path):
        raise NotFound('文件不存在')

    # 图片类型直接返回文件内容
    image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']
    if material.file_type.lower() in image_types:
        response = FileResponse(
            open(full_path, 'rb'),
            content_type=material.mime_type,
        )
        response['Content-Disposition'] = f'inline; filename="{material.name}"'
        return response

    # PDF/Word 等返回 URL
    preview_url = f'{settings.MEDIA_URL}{material.file_path}'
    return Response({
        'success': True,
        'data': {
            'id': material.id,
            'name': material.name,
            'file_type': material.file_type,
            'preview_url': preview_url,
        },
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def material_delete(request, course_id, material_id):
    """软删除课程资料"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    material.is_deleted = True
    material.save(update_fields=['is_deleted'])
    return Response({'success': True, 'message': '资料已删除'})


# ============================================================
# 目录树
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tree_list(request, course_id):
    """嵌套树形结构（根节点 parent=None）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)
    root_nodes = CourseTree.objects.filter(
        course=course,
        parent=None,
    ).order_by('sort_order')
    serializer = CourseTreeNestedSerializer(root_nodes, many=True, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tree_node_create(request, course_id):
    """新增树节点"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    # 验证 parent 是否属于该课程
    parent_id = request.data.get('parent')
    if parent_id:
        try:
            parent = CourseTree.objects.get(id=parent_id, course=course)
        except CourseTree.DoesNotExist:
            raise NotFound(f'父节点 {parent_id} 不存在或不属于此课程')

    data = request.data.copy()
    data['course'] = course_id

    serializer = CourseTreeSerializer(data=data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    node = serializer.save()
    return Response(
        {'success': True, 'data': CourseTreeSerializer(node, context={'request': request}).data, 'message': '节点创建成功'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def tree_node_update(request, course_id, node_id):
    """修改树节点"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        node = CourseTree.objects.get(id=node_id, course=course)
    except CourseTree.DoesNotExist:
        raise NotFound(f'节点 {node_id} 不存在')

    # 验证新的 parent 是否属于该课程且不是自身
    parent_id = request.data.get('parent')
    if parent_id is not None:
        if int(parent_id) == node_id:
            raise ValidationError('节点不能将自身设为父节点')
        try:
            parent = CourseTree.objects.get(id=parent_id, course=course)
        except CourseTree.DoesNotExist:
            raise NotFound(f'父节点 {parent_id} 不存在或不属于此课程')

    serializer = CourseTreeSerializer(node, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    node = serializer.save()
    return Response({'success': True, 'data': CourseTreeSerializer(node, context={'request': request}).data, 'message': '节点更新成功'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def tree_node_delete(request, course_id, node_id):
    """递归删除树节点及其子节点（先删除关联的 CourseQuestionLink）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        node = CourseTree.objects.get(id=node_id, course=course)
    except CourseTree.DoesNotExist:
        raise NotFound(f'节点 {node_id} 不存在')

    # 收集要删除的所有节点（递归子节点）
    def collect_descendants(n):
        ids = [n.id]
        for child in n.children.all():
            ids.extend(collect_descendants(child))
        return ids

    node_ids = collect_descendants(node)

    # 先删除关联的 CourseQuestionLink
    from .models import CourseQuestionLink
    CourseQuestionLink.objects.filter(tree_node_id__in=node_ids).delete()

    # 递归删除节点
    CourseTree.objects.filter(id__in=node_ids).delete()

    return Response({'success': True, 'message': '节点及子节点已删除'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def tree_node_move(request, course_id, node_id):
    """移动树节点（修改 parent 或 sort_order）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        node = CourseTree.objects.get(id=node_id, course=course)
    except CourseTree.DoesNotExist:
        raise NotFound(f'节点 {node_id} 不存在')

    # 验证新的 parent
    new_parent_id = request.data.get('parent')
    if new_parent_id is not None:
        if int(new_parent_id) == node_id:
            raise ValidationError('节点不能将自身设为父节点')
        try:
            new_parent = CourseTree.objects.get(id=new_parent_id, course=course)
            node.parent = new_parent
        except CourseTree.DoesNotExist:
            raise NotFound(f'目标父节点 {new_parent_id} 不存在或不属于此课程')

    # 更新 sort_order
    new_sort = request.data.get('sort_order')
    if new_sort is not None:
        node.sort_order = int(new_sort)

    node.save(update_fields=['parent', 'sort_order'])
    serializer = CourseTreeSerializer(node, context={'request': request})
    return Response({'success': True, 'data': serializer.data, 'message': '节点移动成功'})


# ============================================================
# 变式任务查询
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def variant_task_detail(request, course_id, task_id):
    """查询变式任务状态"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        task = VariantTask.objects.get(id=task_id)
    except VariantTask.DoesNotExist:
        raise NotFound(f'变式任务 {task_id} 不存在')

    serializer = VariantTaskSerializer(task, context={'request': request})
    return Response({'success': True, 'data': serializer.data})
