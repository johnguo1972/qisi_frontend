"""课程管理 REST API Views"""
import os
import uuid
import logging
import mimetypes
from django.conf import settings
from django.db import models as db_models
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from .models import Course, CourseMaterial, CourseTree, CourseQuestionLink, VariantTask
from .serializers import (
    CourseSerializer,
    CourseMaterialSerializer,
    CourseTreeSerializer,
    CourseTreeNestedSerializer,
    VariantTaskSerializer,
    CourseQuestionLinkSerializer,
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
    """获取课程，不存在或已删除则抛 404"""
    try:
        return Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound(f'课程 {course_id} 不存在')


# ============================================================
# 课程 CRUD
# ============================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def course_list_or_create(request):
    """课程列表（GET）和创建（POST）"""
    if request.method == 'GET':
        courses = Course.objects.filter(
            teacher=request.user,
            is_deleted=False
        ).order_by('-created_at')
        serializer = CourseSerializer(courses, many=True, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    # POST - 创建课程
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


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def course_detail_update_delete(request, course_id):
    """课程详情（GET）、更新（PUT）、软删除（DELETE）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    if request.method == 'GET':
        serializer = CourseSerializer(course, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    if request.method == 'PUT':
        serializer = CourseSerializer(course, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        course = serializer.save()
        return Response({'success': True, 'data': CourseSerializer(course, context={'request': request}).data, 'message': '课程更新成功'})

    # DELETE - 软删除
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
    """预览课程资料（所有类型直接返回文件内容，Word自动转为PDF）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    full_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
    if not os.path.exists(full_path):
        raise NotFound('文件不存在')

    # Word文档（.doc/.docx）转为PDF再预览
    word_extensions = ['doc', 'docx', 'word']
    preview_path = full_path
    content_type = material.mime_type
    filename = material.name

    if material.file_type.lower() in word_extensions:
        from .convert_service import convert_word_to_pdf
        pdf_path = convert_word_to_pdf(full_path)
        if pdf_path:
            preview_path = pdf_path
            content_type = 'application/pdf'
            filename = os.path.splitext(material.name)[0] + '.pdf'
        else:
            # 转换失败，返回下载链接让用户下载后用Office打开
            preview_url = f'/api/v1/courses/{course_id}/materials/{material_id}/download/'
            return Response({
                'success': False,
                'message': 'Word文档预览不可用，请下载后用Office/WPS打开',
                'data': {'download_url': preview_url},
            })

    # 返回文件内容（inline 方式让浏览器直接显示）
    response = FileResponse(
        open(preview_path, 'rb'),
        content_type=content_type,
    )
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['Access-Control-Allow-Origin'] = '*'
    return response


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

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tree_list_or_create(request, course_id):
    """目录树列表（GET）和新增节点（POST）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    if request.method == 'GET':
        root_nodes = CourseTree.objects.filter(
            course=course,
            parent=None,
        ).order_by('sort_order')
        serializer = CourseTreeNestedSerializer(root_nodes, many=True, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    # POST - 新增树节点
    parent_id = request.data.get('parent')
    if parent_id:
        try:
            parent = CourseTree.objects.get(id=parent_id, course=course)
        except CourseTree.DoesNotExist:
            raise NotFound(f'父节点 {parent_id} 不存在或不属于此课程')

    data = request.data.copy()
    data['course'] = course_id

    # 自动分配 sort_order（同级节点中最大值 + 1）
    if not data.get('sort_order'):
        siblings = CourseTree.objects.filter(course=course, parent_id=parent_id)
        max_order = siblings.aggregate(db_models.Max('sort_order'))['sort_order__max']
        data['sort_order'] = (max_order or 0) + 1

    serializer = CourseTreeSerializer(data=data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    node = serializer.save()
    return Response(
        {'success': True, 'data': CourseTreeSerializer(node, context={'request': request}).data, 'message': '节点创建成功'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def tree_node_update_or_delete(request, course_id, node_id):
    """修改树节点（PUT）或递归删除（DELETE）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        node = CourseTree.objects.get(id=node_id, course=course)
    except CourseTree.DoesNotExist:
        raise NotFound(f'节点 {node_id} 不存在')

    if request.method == 'PUT':
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

    # DELETE - 递归删除树节点及其子节点
    def collect_descendants(n):
        ids = [n.id]
        for child in n.children.all():
            ids.extend(collect_descendants(child))
        return ids

    node_ids = collect_descendants(node)

    # 软删除关联的 CourseQuestionLink（保留 is_deleted=False 过滤的一致性）
    from .models import CourseQuestionLink
    CourseQuestionLink.objects.filter(tree_node_id__in=node_ids).update(is_deleted=True)

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


# ============================================================
# 习题管理
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request, course_id):
    """课程习题列表（按 tree_node_id 筛选）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    links = CourseQuestionLink.objects.filter(
        course=course,
        is_deleted=False,
    ).select_related('question').order_by('-created_at')

    # 按 tree_node_id 筛选
    tree_node_id = request.query_params.get('tree_node_id')
    if tree_node_id:
        links = links.filter(tree_node_id=tree_node_id)

    serializer = CourseQuestionLinkSerializer(links, many=True, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_import(request, course_id):
    """从题库引入习题"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids')
    tree_node_id = request.data.get('tree_node_id')

    if not question_ids or not isinstance(question_ids, list):
        raise ValidationError('question_ids 必须是非空数组')

    # 验证题目存在
    from apps.parser.models import ExamQuestion
    existing_questions = ExamQuestion.objects.filter(id__in=question_ids)
    existing_ids = set(existing_questions.values_list('id', flat=True))

    missing_ids = set(question_ids) - existing_ids
    if missing_ids:
        raise ValidationError(f'以下题目不存在: {", ".join(map(str, missing_ids))}')

    # 验证 tree_node 存在（如果提供）
    tree_node = None
    if tree_node_id:
        try:
            tree_node = CourseTree.objects.get(id=tree_node_id, course=course)
        except CourseTree.DoesNotExist:
            raise NotFound(f'树节点 {tree_node_id} 不存在或不属于此课程')

    # 批量创建关联（已通过上方验证，所有 question_ids 均存在）
    imported_count = 0
    for qid in question_ids:
        _, created = CourseQuestionLink.objects.get_or_create(
            course=course,
            question_id=qid,
            defaults={
                'tree_node': tree_node,
                'source': 'import',
            }
        )
        if created:
            imported_count += 1

    return Response({
        'success': True,
        'data': {'imported_count': imported_count},
        'message': f'成功引入 {imported_count} 道习题',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_batch_delete(request, course_id):
    """批量从课程移除习题（软删除 CourseQuestionLink）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids')
    if not question_ids or not isinstance(question_ids, list):
        raise ValidationError('question_ids 必须是非空数组')

    # 软删除关联
    updated = CourseQuestionLink.objects.filter(
        course=course,
        question_id__in=question_ids,
        is_deleted=False,
    ).update(is_deleted=True)

    return Response({
        'success': True,
        'data': {'removed_count': updated},
        'message': f'已移除 {updated} 道习题',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_batch_move(request, course_id):
    """批量移动习题所属节点"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids')
    target_node_id = request.data.get('target_node_id')

    if not question_ids or not isinstance(question_ids, list):
        raise ValidationError('question_ids 必须是非空数组')
    if target_node_id is None:
        raise ValidationError('target_node_id 不能为空')

    # 验证目标节点存在且属于此课程
    try:
        target_node = CourseTree.objects.get(id=target_node_id, course=course)
    except CourseTree.DoesNotExist:
        raise NotFound(f'目标节点 {target_node_id} 不存在或不属于此课程')

    # 批量更新 tree_node_id
    updated = CourseQuestionLink.objects.filter(
        course=course,
        question_id__in=question_ids,
        is_deleted=False,
    ).update(tree_node=target_node)

    return Response({
        'success': True,
        'data': {'moved_count': updated},
        'message': f'已移动 {updated} 道习题',
    })


# ============================================================
# AI 处理（复用 review API）
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_ai_process(request, course_id):
    """AI处理习题（委托给 review 模块的 view 函数）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    # 提取 question_id 并验证属于课程
    question_id = request.data.get('question_id')
    if not question_id:
        raise ValidationError('question_id 不能为空')

    question_id = int(question_id)
    if not CourseQuestionLink.objects.filter(
        course=course, question_id=question_id, is_deleted=False
    ).exists():
        raise NotFound('题目不在课程中')

    # 从 body 移除 question_id（review view 从 URL kwargs 获取）
    if hasattr(request.data, '_mutable'):
        request.data._mutable = True
    if 'question_id' in request.data:
        del request.data['question_id']

    # 委托给 review 模块的 ai_process_question view
    request.resolver_match = type(
        'ResolverMatch', (), {'kwargs': {'question_id': question_id}}
    )()
    from apps.review.views import ai_process_question as review_process
    return review_process(request, question_id)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_ai_confirm(request, course_id, question_id):
    """AI答案确认（委托给 review 模块）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    mode = request.data.get('mode', '').upper()
    if mode not in ('A', 'B', 'C'):
        raise ValidationError('mode 必须是 A、B 或 C')

    # 验证题目属于该课程
    if not CourseQuestionLink.objects.filter(
        course=course, question_id=question_id, is_deleted=False
    ).exists():
        raise NotFound('题目不在课程中')

    # 委托给 review 模块的 ai_confirm_answer
    from apps.review.views import ai_confirm_answer as review_ai_confirm

    return review_ai_confirm(request, question_id, mode)


# ============================================================
# 变式题生成
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_generate_variant(request, course_id, question_id):
    """发起变式题生成任务"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    from apps.parser.models import ExamQuestion
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'题目 {question_id} 不存在')

    # 检查题目 review_status
    if question.review_status != 'confirmed':
        raise ValidationError(f'题目 review_status 为 "{question.review_status}"，必须为 "confirmed" 才能生成变式题')

    variant_mode = request.data.get('variant_mode')
    tree_node_id = request.data.get('tree_node_id')

    if not variant_mode:
        raise ValidationError('variant_mode 不能为空')

    # 调用 Celery 任务
    from .tasks import generate_variant_task as celery_generate_variant
    task = celery_generate_variant.delay(
        question_id=question_id,
        variant_mode=variant_mode,
        tree_node_id=tree_node_id,
    )

    return Response({
        'success': True,
        'data': {'task_id': task.id, 'status': 'pending', 'question_id': question_id},
        'message': '变式题生成任务已提交',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_batch_generate_variant(request, course_id):
    """批量生成变式题"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids')
    variant_mode = request.data.get('variant_mode')
    tree_node_id = request.data.get('tree_node_id')

    if not question_ids or not isinstance(question_ids, list):
        raise ValidationError('question_ids 必须是非空数组')
    if not variant_mode:
        raise ValidationError('variant_mode 不能为空')

    from .tasks import batch_generate_variants_task as celery_batch_generate
    task = celery_batch_generate.delay(
        question_ids=question_ids,
        variant_mode=variant_mode,
        tree_node_id=tree_node_id,
    )

    return Response({
        'success': True,
        'data': {'task_id': task.id, 'status': 'pending', 'question_count': len(question_ids)},
        'message': f'已提交 {len(question_ids)} 道变式题生成任务',
    })


# ============================================================
# 变式题确认/驳回
# ============================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def variant_task_confirm(request, course_id, task_id):
    """确认变式题入库"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        task = VariantTask.objects.get(id=task_id, original_question__course_links__course=course)
    except VariantTask.DoesNotExist:
        raise NotFound(f'变式任务 {task_id} 不存在或不属于此课程')

    if task.status != 'success':
        raise ValidationError(f'变式任务状态为 "{task.status}"，只有成功状态的任务可以确认')

    if not task.generated_question:
        return Response({
            'success': False,
            'error': '任务没有生成结果',
        }, status=400)

    # Celery 任务已保存 ExamQuestion（review_status='need_review'），此处更新为 confirmed
    from apps.parser.models import ExamQuestion, QuestionOption

    # 查找已保存的变式题（通过 question_no 前缀匹配）
    try:
        variant_q = ExamQuestion.objects.get(
            question_no=f"VAR-{task.id}",
            original_question=task.original_question,
        )
    except ExamQuestion.DoesNotExist:
        # 如果未找到，说明 Celery 任务尚未保存或失败，手动保存
        try:
            variant_q = _save_variant_as_question(task, task.generated_question)
        except Exception as e:
            logger.exception(f"Failed to save variant for task {task_id}")
            return Response({
                'success': False,
                'error': f'保存变式题失败: {str(e)}',
            }, status=500)

    # 更新 review_status 为 confirmed
    variant_q.review_status = 'confirmed'
    variant_q.need_review = False
    variant_q.save(update_fields=['review_status', 'need_review'])

    task.status = 'confirmed'
    task.completed_at = task.completed_at or timezone.now()
    task.save(update_fields=['status', 'completed_at'])

    return Response({
        'success': True,
        'data': {'question_id': variant_q.id},
        'message': '变式题已确认入库',
    })


def _save_variant_as_question(task, variant_data):
    """将生成的变式题保存为 ExamQuestion 记录。"""
    from apps.parser.models import ExamQuestion, QuestionOption

    original = task.original_question

    # 检查是否已保存过（通过 system_id 前缀判断）
    variant_q = ExamQuestion.objects.create(
        paper=original.paper,
        question_no=f"VAR-{task.id}",
        question_type=variant_data.get('question_type', original.question_type),
        subject=original.subject,
        stem=variant_data.get('stem', ''),
        answer=variant_data.get('answer', ''),
        analysis=variant_data.get('analysis', ''),
        solution=variant_data.get('solution', ''),
        difficulty=variant_data.get('difficulty', original.difficulty),
        knowledge_points=variant_data.get('knowledge_points', original.knowledge_points),
        original_question=original,
        confidence=0.8,
        need_review=False,
        review_status='confirmed',
        parse_status='auto_parsed',
    )

    # 保存选项（如果是选择题）
    options = variant_data.get('options', [])
    if options and isinstance(options, list):
        for idx, opt in enumerate(options):
            if isinstance(opt, dict):
                QuestionOption.objects.create(
                    question=variant_q,
                    option_label=opt.get('label', ''),
                    content=opt.get('content', ''),
                    sort_order=idx,
                )

    return variant_q


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def variant_task_reject(request, course_id, task_id):
    """驳回变式题"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        task = VariantTask.objects.get(id=task_id, original_question__course_links__course=course)
    except VariantTask.DoesNotExist:
        raise NotFound(f'变式任务 {task_id} 不存在或不属于此课程')

    reason = request.data.get('reason', '')

    # 更新任务状态
    task.status = 'failed'
    task.error_message = f'驳回: {reason}' if reason else '已驳回'
    task.completed_at = timezone.now()
    task.save(update_fields=['status', 'error_message', 'completed_at'])

    return Response({
        'success': True,
        'message': '变式题已驳回',
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_mission(request, course_id):
    """从课程目录节点批量生成任务关卡"""
    from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
    from apps.accounts.models import UserAccount

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    node_ids = request.data.get('node_ids', [])
    mission_name = request.data.get('mission_name', f'{course.name} - 任务')
    level_type = request.data.get('level_type', 'practice')
    pass_rule = request.data.get('pass_rule', {'correct_rate': 0.6})

    if not node_ids:
        raise ValidationError('未选择目录节点')

    # 创建任务
    mission = LearningMission.objects.create(
        mission_name=mission_name,
        creator_teacher_id=request.user,
        status='draft',
    )

    created_levels = []
    for idx, node_id in enumerate(node_ids, 1):
        try:
            node = CourseTree.objects.get(id=node_id, course=course)
        except CourseTree.DoesNotExist:
            continue

        # 创建关卡
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=idx,
            level_name=node.name,
            level_type=level_type,
            pass_rule_json=pass_rule,
        )

        # 关联节点下的习题
        question_links = CourseQuestionLink.objects.filter(
            course=course, tree_node=node, is_deleted=False
        )
        for sort_no, link in enumerate(question_links, 1):
            MissionQuestionRel.objects.create(
                mission=mission,
                level=level,
                question_id=link.question_id,
                sort_no=sort_no,
                source_type='course_sync',
            )

        created_levels.append(level.id)

    return Response({
        'success': True,
        'data': {
            'mission_id': mission.id,
            'mission_no': mission.mission_no,
            'level_ids': created_levels,
            'level_count': len(created_levels),
        },
        'message': f'任务创建成功，共 {len(created_levels)} 个关卡',
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_pages(request, course_id, material_id):
    """获取资料文档的页面图片列表（用于预览）"""
    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    full_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
    if not os.path.exists(full_path):
        raise NotFound('文件不存在')

    # 确保输出目录存在
    pages_dir = os.path.join(settings.MEDIA_ROOT, 'courses', str(course_id), 'materials', f'{material_id}_pages')
    os.makedirs(pages_dir, exist_ok=True)

    page_images = []

    try:
        if material.file_type.lower() in ['pdf']:
            # PDF 直接转图片
            from apps.parser.services.convert_service import pdf_to_images
            images = pdf_to_images(full_path, output_dir=pages_dir)
            for img_path in images:
                rel_path = os.path.relpath(img_path, settings.MEDIA_ROOT)
                page_images.append({
                    'url': f'{settings.MEDIA_URL}{rel_path}',
                    'page': len(page_images) + 1,
                })
        elif material.file_type.lower() in ['word', 'docx', 'doc']:
            # Word 先转 PDF 再转图片
            from apps.parser.services.convert_service import word_to_pdf, pdf_to_images
            pdf_path = word_to_pdf(full_path, output_dir=pages_dir)
            if pdf_path:
                images = pdf_to_images(pdf_path, output_dir=pages_dir)
                for img_path in images:
                    rel_path = os.path.relpath(img_path, settings.MEDIA_ROOT)
                    page_images.append({
                        'url': f'{settings.MEDIA_URL}{rel_path}',
                        'page': len(page_images) + 1,
                    })
        elif material.file_type.lower().startswith('image'):
            # 图片直接返回
            rel_path = os.path.relpath(full_path, settings.MEDIA_ROOT)
            page_images.append({
                'url': f'{settings.MEDIA_URL}{rel_path}',
                'page': 1,
            })
    except Exception as e:
        logger.error(f'文档转图片失败: {e}')
        raise ValidationError(f'文档转换失败: {str(e)}')

    return Response({
        'success': True,
        'data': {
            'material_id': material.id,
            'material_name': material.name,
            'pages': page_images,
        },
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def material_ai_recognize(request, course_id, material_id):
    """框选区域 AI 识别（qwen3.7-plus 多模态）"""
    from apps.common.ai_service import AIReviewService

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    # 获取请求参数
    image_url = request.data.get('image_url', '')
    page = request.data.get('page', 1)

    if not image_url:
        raise ValidationError('未提供图片 URL')

    # 构建图片完整路径
    if image_url.startswith(settings.MEDIA_URL):
        rel_path = image_url[len(settings.MEDIA_URL):]
        image_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    else:
        image_path = image_url

    if not os.path.exists(image_path):
        raise NotFound('图片文件不存在')

    # 调用 AI 识别
    try:
        ai_service = AIReviewService()
        # 使用 qwen3.7-plus 模型进行多模态识别
        prompt = """请识别图片中的试题内容，并以 JSON 格式返回：
{
  "question_type": "single_choice|multiple_choice|fill_blank|solution",
  "stem": "题干内容（支持 LaTeX 公式）",
  "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
  "answer": "正确答案",
  "analysis": "解析",
  "difficulty": 3,
  "knowledge_points": ["知识点1", "知识点2"],
  "images": [{"description": "图片描述", "url": "图片路径"}]
}
如果图片中没有试题，返回 {"error": "未识别到试题"}"""

        # 读取图片并发送给 AI
        with open(image_path, 'rb') as f:
            import base64
            img_data = base64.b64encode(f.read()).decode('utf-8')

        # 使用视觉模型识别
        response_text = ai_service._call_ai(
            system_prompt="你是试题识别专家，请准确识别图片中的试题内容。",
            user_prompt=prompt,
            model='qwen3.7-plus',
            images=[f'data:image/png;base64,{img_data}'],
        )

        import json
        result = json.loads(response_text) if response_text else {}

        if 'error' in result:
            return Response({
                'success': False,
                'message': result['error'],
            })

        return Response({
            'success': True,
            'data': result,
        })

    except json.JSONDecodeError:
        raise ValidationError('AI 返回格式错误')
    except Exception as e:
        logger.error(f'AI 识别失败: {e}')
        raise ValidationError(f'AI 识别失败: {str(e)}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_question(request, course_id):
    """保存从课程资料导入的题目"""
    from apps.parser.models import ExamQuestion, QuestionImage

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    # 获取题目数据
    question_data = request.data.get('question', {})
    tree_node_id = request.data.get('tree_node_id')

    if not question_data.get('stem'):
        raise ValidationError('题干不能为空')

    # 创建题目
    question = ExamQuestion.objects.create(
        question_no=request.data.get('question_no', 'imported'),
        question_type=question_data.get('question_type', 'single_choice'),
        subject=course.subject,
        stem=question_data.get('stem', ''),
        stem_html=question_data.get('stem_html', ''),
        answer=question_data.get('answer', ''),
        analysis=question_data.get('analysis', ''),
        solution=question_data.get('solution', ''),
        difficulty=question_data.get('difficulty', 3),
        knowledge_points=question_data.get('knowledge_points', []),
        review_status='unreviewed',
        parse_status='auto_parsed',
    )

    # 创建选项
    options = question_data.get('options', {})
    for label, content in options.items():
        if content:
            from apps.parser.models import QuestionOption
            QuestionOption.objects.create(
                question=question,
                option_label=label,
                content=content,
            )

    # 关联到课程目录节点
    if tree_node_id:
        CourseQuestionLink.objects.create(
            course=course,
            tree_node_id=tree_node_id,
            question=question,
            source='imported_from_material',
            source_course_name=course.name,
        )

    return Response({
        'success': True,
        'data': {
            'question_id': question.id,
        },
        'message': '题目导入成功',
    }, status=status.HTTP_201_CREATED)
