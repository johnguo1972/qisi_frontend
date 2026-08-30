"""课程管理 REST API Views"""
import os
import uuid
import logging
import mimetypes
from django.conf import settings
from django.db import models as db_models, transaction
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from apps.accounts.roles import has_user_role
from apps.common.subject_codes import normalize_subject_codes
from apps.institutions.models import Institution, InstitutionMember
from apps.knowledge.models import KnowledgePoint
from apps.parser.models import ExamQuestion
from apps.study.models import QuestionTagRelation
from apps.study.question_views import _keyword_tokens
from apps.study.serializers import QuestionListSerializer

from .models import (
    Course,
    CourseAuditLog,
    CourseCollaborator,
    CourseMaterial,
    CourseTree,
    CourseQuestionLink,
    VariantTask,
)
from .serializers import (
    CourseSerializer,
    CourseMaterialSerializer,
    CourseTreeSerializer,
    CourseTreeNestedSerializer,
    VariantTaskSerializer,
)

logger = logging.getLogger(__name__)


def generate_variant_task_dispatch(**kwargs):
    """Dispatch a single variant task through the existing Celery signature."""
    from .tasks import generate_variant_task

    return generate_variant_task.delay(**kwargs)


def batch_variant_task_dispatch(**kwargs):
    """Dispatch a batch variant task through the existing Celery signature."""
    from .tasks import batch_generate_variants_task

    return batch_generate_variants_task.delay(**kwargs)


def _dispatch_material_conversion(material_id):
    """Queue conversion after the material row has been committed."""
    from .tasks import convert_course_material

    try:
        convert_course_material.delay(str(material_id))
    except Exception as exc:
        CourseMaterial.objects.filter(id=material_id).update(
            conversion_status=CourseMaterial.ConversionStatus.FAILED,
            conversion_error=str(exc)[:2000],
            conversion_completed_at=timezone.now(),
        )
        logger.exception('Failed to dispatch course material conversion: %s', material_id)


def create_variant_task_and_dispatch(*, question, variant_mode, tree_node_id=None):
    """Create the database task before dispatching Celery.

    The status/confirm APIs address VariantTask UUIDs, while Celery returns a
    different execution UUID. Creating the record first prevents a race and
    ensures the ID returned to the frontend is queryable immediately.
    """
    task = VariantTask.objects.create(
        original_question=question,
        variant_mode=variant_mode,
        status='pending',
    )
    try:
        result = generate_variant_task_dispatch(
            question_id=str(question.id),
            variant_mode=variant_mode,
            tree_node_id=tree_node_id,
            variant_task_id=str(task.id),
        )
        task.generator_result = {'celery_task_id': str(result.id)}
        task.save(update_fields=['generator_result'])
    except Exception as exc:
        task.status = 'failed'
        task.error_message = f'任务提交失败: {exc}'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'error_message', 'completed_at'])
        raise
    return task


def material_vision_component_factory():
    """Construct the shared vision component for course material recognition."""
    from apps.common.ai.components.vision_parser import VisionParserComponent

    return VisionParserComponent()


def _recognize_course_material_image(image_path, crop_region):
    """Recognize a material image without retaining sensitive failure locals."""
    failed = False
    result = None
    image_source = image_path
    img = None
    cropped = None
    buffer = None
    original_size = None
    cropped_size = None
    component = None
    try:
        if crop_region:
            import base64
            import io
            from PIL import Image

            with Image.open(image_path) as img:
                x1 = max(0, min(crop_region.get('x1', 0), img.width))
                y1 = max(0, min(crop_region.get('y1', 0), img.height))
                x2 = max(0, min(crop_region.get('x2', 0), img.width))
                y2 = max(0, min(crop_region.get('y2', 0), img.height))
                if x2 > x1 and y2 > y1:
                    cropped = img.crop((x1, y1, x2, y2))
                    buffer = io.BytesIO()
                    cropped.save(buffer, format='PNG')
                    image_source = (
                        'data:image/png;base64,'
                        + base64.b64encode(buffer.getvalue()).decode('ascii')
                    )
                    original_size = img.size
                    cropped_size = cropped.size

        if original_size is not None:
            logger.info(
                'Cropped course material image from %s to %s',
                original_size,
                cropped_size,
            )
        component = material_vision_component_factory()
        result = component.recognize_course_material([image_source])
    except Exception as error:
        logger.error(
            'Course material AI recognition failed: %s',
            error.__class__.__name__,
        )
        failed = True
    finally:
        close = getattr(component, 'close', None)
        if callable(close):
            close()
        image_path = ''
        crop_region = {}
        image_source = ''
        img = None
        cropped = None
        buffer = None
        original_size = None
        cropped_size = None
        component = None

    if failed:
        raise ValidationError('AI 识别失败')
    return result


# ============================================================
# 权限辅助函数
# ============================================================

def _course_stage(grade_level):
    """将课程年级统一归类为教师配置使用的学段名称。"""
    value = (grade_level or '').strip()
    if value in {'小学', '初中', '高中'}:
        return value
    if value.startswith('高'):
        return '高中'
    if value.endswith('年级'):
        chinese_numbers = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9,
        }
        try:
            number = chinese_numbers.get(value[:-2])
            if number is None:
                number = int(value[:-2])
        except ValueError:
            return None
        if 1 <= number <= 6:
            return '小学'
        if 7 <= number <= 9:
            return '初中'
    return None


def _active_role(user):
    """Return the role selected for this authenticated request when present."""
    return getattr(user, '_active_role', None) or getattr(user, 'role_type', None)


def _is_teacher(user):
    active_role = getattr(user, '_active_role', None)
    if active_role is None:
        return getattr(user, 'role_type', None) == 'teacher' and has_user_role(user, 'teacher')
    return active_role == 'teacher' and has_user_role(user, 'teacher')


def _is_admin(user):
    active_role = getattr(user, '_active_role', None)
    if active_role is None:
        return has_user_role(user, 'admin')
    return active_role == 'admin' and has_user_role(user, 'admin')


def _teacher_institution_ids(user):
    return list(
        InstitutionMember.objects.filter(
            user=user,
            role__in=['admin', 'teacher'],
            status='active',
        ).values_list('institution_id', flat=True).distinct()
    )


def _resolve_course_institution(request, *, required=True):
    """Resolve and authorize the institution used for a course operation."""
    requested = request.query_params.get('institution_id') or request.data.get('institution_id')
    if requested:
        if _is_admin(request.user):
            try:
                return Institution.objects.get(id=requested, status='active')
            except Institution.DoesNotExist:
                raise ValidationError('机构不存在或已停用')
        membership = InstitutionMember.objects.filter(
            institution_id=requested,
            user=request.user,
            role__in=['admin', 'teacher'],
            status='active',
        ).select_related('institution').first()
        if membership is None:
            raise PermissionDenied('您不是该机构的有效教师')
        return membership.institution

    institution_ids = _teacher_institution_ids(request.user)
    if len(institution_ids) == 1:
        return Institution.objects.get(id=institution_ids[0])
    if required and len(institution_ids) == 0:
        raise PermissionDenied('教师尚未加入有效机构')
    if required and len(institution_ids) > 1:
        raise ValidationError('您属于多个机构，请先指定 institution_id')
    return None


def _course_subjects(user):
    return normalize_subject_codes(user.subjects or user.subject)


def _same_scope_course(course, user):
    if not _is_teacher(user) or not course.institution_id:
        return False
    if not InstitutionMember.objects.filter(
        institution_id=course.institution_id,
        user=user,
        role__in=['admin', 'teacher'],
        status='active',
    ).exists():
        return False
    return (
        course.subject in _course_subjects(user)
        and _course_stage(course.grade_level) in (user.stages or [])
    )


def _active_course_collaborator(course, user):
    if not _is_teacher(user) or not course.institution_id:
        return None
    if not InstitutionMember.objects.filter(
        institution_id=course.institution_id,
        user=user,
        role='teacher',
        status='active',
    ).exists():
        return None
    return CourseCollaborator.objects.filter(
        course=course, user=user, status='active',
    ).first()


def _can_access_shared_course(course, user):
    """Apply one consistent read rule to course and all child resources."""
    if _is_admin(user):
        return True
    if course.teacher_id == user.id:
        return True
    if _active_course_collaborator(course, user) is not None:
        return True
    return _same_scope_course(course, user)


def _can_edit_course(course, user):
    if _is_admin(user) or course.teacher_id == user.id:
        return True
    collaborator = _active_course_collaborator(course, user)
    if collaborator and collaborator.role == 'editor':
        return True
    # Existing business behavior allows same-institution subject/stage peers
    # to collaborate.  Explicit viewer grants remain read-only.
    return _same_scope_course(course, user)


def _audit(course, actor, action, target_user=None, metadata=None):
    CourseAuditLog.objects.create(
        course=course,
        actor=actor,
        action=action,
        target_user=target_user,
        metadata=metadata or {},
    )


def _check_course_owner(course, user):
    """验证用户是否可以协作操作课程。"""
    if not _can_edit_course(course, user):
        raise PermissionDenied('您没有权限操作此课程')


def _check_course_access(course, user):
    if not _can_access_shared_course(course, user):
        raise PermissionDenied('您没有权限访问此课程')


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
        if _is_admin(request.user):
            courses = Course.objects.filter(is_deleted=False)
            institution_id = request.query_params.get('institution_id')
            if institution_id:
                courses = courses.filter(institution_id=institution_id)
            courses = courses.order_by('-created_at')
        else:
            if not _is_teacher(request.user):
                raise PermissionDenied('只有教师或管理员可以访问课程管理')
            institution = _resolve_course_institution(request, required=False)
            institution_ids = [institution.id] if institution else _teacher_institution_ids(request.user)
            stages = request.user.stages or []
            subjects = _course_subjects(request.user)
            grade_levels = [
                grade for grade in Course.objects.values_list('grade_level', flat=True).distinct()
                if _course_stage(grade) in stages
            ]
            courses = Course.objects.filter(is_deleted=False).filter(
                db_models.Q(teacher=request.user)
                | db_models.Q(
                    collaborators__user=request.user,
                    collaborators__status='active',
                    institution_id__in=institution_ids,
                )
                | db_models.Q(
                    institution_id__in=institution_ids,
                    subject__in=subjects,
                    grade_level__in=grade_levels,
                )
            ).distinct().order_by('-created_at')
        serializer = CourseSerializer(courses, many=True, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    if not (_is_teacher(request.user) or _is_admin(request.user)):
        raise PermissionDenied('只有教师或管理员可以创建课程')
    course_institution = _resolve_course_institution(request, required=True)
    serializer = CourseSerializer(
        data=request.data,
        context={'request': request, 'course_institution': course_institution},
    )
    serializer.is_valid(raise_exception=True)
    course = serializer.save()
    _audit(course, request.user, 'course.create')
    return Response(
        {'success': True, 'data': CourseSerializer(course, context={'request': request}).data, 'message': '课程创建成功'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def course_detail_update_delete(request, course_id):
    """课程详情（GET）、更新（PUT）、软删除（DELETE）"""
    course = _get_course_or_404(course_id)

    if request.method == 'GET':
        _check_course_access(course, request.user)
        serializer = CourseSerializer(course, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    _check_course_owner(course, request.user)

    if request.method == 'PUT':
        serializer = CourseSerializer(course, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        course = serializer.save()
        _audit(course, request.user, 'course.update')
        return Response({'success': True, 'data': CourseSerializer(course, context={'request': request}).data, 'message': '课程更新成功'})

    # DELETE - 软删除
    course.is_deleted = True
    course.save(update_fields=['is_deleted'])
    _audit(course, request.user, 'course.delete')
    return Response({'success': True, 'message': '课程已删除'})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def course_collaborators(request, course_id):
    """List or grant explicit read/edit access to teachers in the course institution."""
    course = _get_course_or_404(course_id)
    _check_course_access(course, request.user)

    if request.method == 'GET':
        items = list(
            CourseCollaborator.objects.filter(course=course, status='active')
            .select_related('user')
            .values('user_id', 'user__display_name', 'user__mobile', 'role', 'created_at')
        )
        return Response({'success': True, 'data': items})

    if not (_is_admin(request.user) or course.teacher_id == request.user.id):
        raise PermissionDenied('只有课程创建者或管理员可以管理协作者')
    target_id = request.data.get('user_id')
    role = request.data.get('role', 'viewer')
    if role not in {'viewer', 'editor'}:
        raise ValidationError('协作者权限必须是 viewer 或 editor')
    if not target_id or not course.institution_id:
        raise ValidationError('课程必须归属机构且必须提供协作者 user_id')
    target_membership = InstitutionMember.objects.filter(
        institution_id=course.institution_id,
        user_id=target_id,
        role='teacher',
        status='active',
    ).first()
    if target_membership is None:
        raise ValidationError('协作者必须是课程所属机构的有效教师')
    collaborator, _ = CourseCollaborator.objects.update_or_create(
        course=course,
        user_id=target_id,
        defaults={'role': role, 'status': 'active', 'granted_by': request.user},
    )
    _audit(
        course,
        request.user,
        'course.collaborator.grant',
        target_user=collaborator.user,
        metadata={'role': role},
    )
    return Response({
        'success': True,
        'data': {
            'user_id': collaborator.user_id,
            'role': collaborator.role,
            'status': collaborator.status,
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def course_collaborator_delete(request, course_id, user_id):
    course = _get_course_or_404(course_id)
    _check_course_access(course, request.user)
    if not (_is_admin(request.user) or course.teacher_id == request.user.id):
        raise PermissionDenied('只有课程创建者或管理员可以管理协作者')
    collaborator = CourseCollaborator.objects.filter(
        course=course, user_id=user_id, status='active',
    ).first()
    if collaborator is None:
        raise NotFound('协作者不存在')
    collaborator.status = 'revoked'
    collaborator.save(update_fields=['status', 'updated_at'])
    _audit(course, request.user, 'course.collaborator.revoke', target_user=collaborator.user)
    return Response({'success': True, 'message': '协作者权限已撤销'})


# ============================================================
# 课程资料
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_list(request, course_id):
    """课程资料列表（排除软删除）"""
    course = _get_course_or_404(course_id)
    _check_course_access(course, request.user)
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
    is_word = file_type in {'doc', 'docx'}
    material = CourseMaterial.objects.create(
        course=course,
        name=uploaded_file.name,
        file_path=f'courses/{course_id}/materials/{filename}',
        file_type=file_type,
        file_size=uploaded_file.size,
        mime_type=mime_type,
        uploaded_by=request.user,
        conversion_status=(
            CourseMaterial.ConversionStatus.PENDING
            if is_word else CourseMaterial.ConversionStatus.NOT_REQUIRED
        ),
    )
    if is_word:
        transaction.on_commit(lambda material_id=material.id: _dispatch_material_conversion(material_id))

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
    _check_course_access(course, request.user)

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
    _check_course_access(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    word_extensions = {'doc', 'docx', 'word'}
    is_word = material.file_type.lower() in word_extensions
    if is_word:
        if material.conversion_status in {
            CourseMaterial.ConversionStatus.PENDING,
            CourseMaterial.ConversionStatus.CONVERTING,
        }:
            return Response({
                'success': False,
                'code': 'conversion_in_progress',
                'message': '格式转换中，请稍后再预览',
            }, status=status.HTTP_409_CONFLICT)
        if material.conversion_status == CourseMaterial.ConversionStatus.FAILED:
            return Response({
                'success': False,
                'code': 'conversion_failed',
                'message': '格式转换失败，请下载原文件后使用 Office/WPS 打开',
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Legacy Word materials are upgraded lazily, but preview never blocks.
        if material.conversion_status != CourseMaterial.ConversionStatus.COMPLETED:
            material.conversion_status = CourseMaterial.ConversionStatus.PENDING
            material.conversion_error = ''
            material.save(update_fields=['conversion_status', 'conversion_error'])
            transaction.on_commit(lambda material_id=material.id: _dispatch_material_conversion(material_id))
            return Response({
                'success': False,
                'code': 'conversion_in_progress',
                'message': '格式转换中，请稍后再预览',
            }, status=status.HTTP_409_CONFLICT)

        if not material.converted_pdf_path:
            return Response({
                'success': False,
                'code': 'conversion_failed',
                'message': '转换后的 PDF 不存在，请重新上传该文件',
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        preview_path = os.path.join(settings.MEDIA_ROOT, material.converted_pdf_path)
        content_type = 'application/pdf'
        filename = os.path.splitext(material.name)[0] + '.pdf'
    else:
        preview_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
        content_type = material.mime_type
        filename = material.name

    if not os.path.exists(preview_path):
        raise NotFound('预览文件不存在')

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
    if request.method == 'GET':
        _check_course_access(course, request.user)
        root_nodes = CourseTree.objects.filter(
            course=course,
            parent=None,
        ).order_by('sort_order')
        serializer = CourseTreeNestedSerializer(root_nodes, many=True, context={'request': request})
        return Response({'success': True, 'data': serializer.data})

    _check_course_owner(course, request.user)

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
    _check_course_access(course, request.user)

    try:
        task = VariantTask.objects.get(id=task_id)
    except VariantTask.DoesNotExist:
        raise NotFound(f'变式任务 {task_id} 不存在')

    serializer = VariantTaskSerializer(task, context={'request': request})
    return Response({'success': True, 'data': serializer.data})


# ============================================================
# 习题管理
# ============================================================

def apply_course_question_filters(queryset, params):
    """Apply the question-bank's card filters to a course-node queryset."""
    difficulty = params.get('difficulty')
    question_type = params.get('question_type')
    keyword = (params.get('keyword') or '').strip()
    tag = (params.get('tag') or '').strip()
    knowledge_point_id = params.get('knowledge_point_id') or ''

    if difficulty:
        diff_values = [value.strip() for value in difficulty.split(',') if value.strip()]
        try:
            diff_values = [float(value) for value in diff_values]
            if len(diff_values) == 1:
                queryset = queryset.filter(difficulty=diff_values[0])
            elif diff_values:
                queryset = queryset.filter(difficulty__in=diff_values)
        except (TypeError, ValueError):
            pass
    if question_type:
        question_types = [value.strip() for value in question_type.split(',') if value.strip()]
        if len(question_types) == 1:
            queryset = queryset.filter(question_type=question_types[0])
        elif question_types:
            queryset = queryset.filter(question_type__in=question_types)
    if tag:
        tag_question_ids = QuestionTagRelation.objects.filter(tag__name=tag).values('question_id')
        queryset = queryset.filter(Q(tags__contains=[tag]) | Q(id__in=tag_question_ids))

    keyword_tokens = _keyword_tokens(keyword)
    if keyword_tokens:
        queryset = queryset.annotate(uuid_text=Cast('id', output_field=CharField()))
        for token in keyword_tokens:
            queryset = queryset.filter(
                Q(stem__icontains=token)
                | Q(stem_html__icontains=token)
                | Q(question_no__icontains=token)
                | Q(paper_question_no__icontains=token)
                | Q(system_id__icontains=token)
                | Q(options__content__icontains=token)
                | Q(uuid_text__icontains=token)
            )
        queryset = queryset.distinct()

    if knowledge_point_id:
        kp_values = [value.strip() for value in knowledge_point_id.split(',') if value.strip()]
        if '-1' in kp_values:
            queryset = queryset.filter(Q(knowledge_points__isnull=True) | Q(knowledge_points=[]))
        else:
            kp_query = Q()
            for value in kp_values:
                kp_query |= (
                    Q(knowledge_points__contains=[{'id': value}])
                    | Q(ai_knowledge_enrichment__contains={
                        'knowledge_points': [{'id': value}]
                    })
                )
                try:
                    kp_id = int(value)
                    kp_query |= (
                        Q(knowledge_points__contains=[{'id': kp_id}])
                        | Q(knowledge_points__contains=[{'id': str(kp_id)}])
                        | Q(ai_knowledge_enrichment__contains=[{'id': kp_id}])
                    )
                    try:
                        kp = KnowledgePoint.objects.get(pk=kp_id)
                        kp_query |= Q(knowledge_points__contains=[{'module': kp.module}])
                    except KnowledgePoint.DoesNotExist:
                        pass
                except (TypeError, ValueError):
                    try:
                        kp = KnowledgePoint.objects.get(pk=value)
                        kp_query |= Q(knowledge_points__contains=[{'module': kp.module}])
                    except (KnowledgePoint.DoesNotExist, TypeError, ValueError):
                        continue
            if kp_query:
                queryset = queryset.filter(kp_query)
    return queryset


def paginate_question_queryset(queryset, request):
    """Use the question-bank's page validation and response shape."""
    try:
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(max(int(request.query_params.get('page_size', 20)), 1), 100)
    except (TypeError, ValueError):
        raise ValidationError('page/page_size 参数无效')

    total = queryset.count()
    start = (page - 1) * page_size
    items = queryset.order_by('sort_order', 'id')[start:start + page_size]
    return {
        'items': QuestionListSerializer(items, many=True).data,
        'total': total,
        'page_no': page,
        'page_size': page_size,
    }

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request, course_id):
    """List paginated questions linked to one selected course-tree node."""
    course = _get_course_or_404(course_id)
    _check_course_access(course, request.user)

    tree_node_id = request.query_params.get('tree_node_id')
    if not tree_node_id:
        raise ValidationError('tree_node_id is required')
    try:
        tree_node_uuid = uuid.UUID(str(tree_node_id))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('tree_node_id is invalid')
    if not CourseTree.objects.filter(id=tree_node_uuid, course=course).exists():
        raise ValidationError('tree_node_id does not belong to this course')

    links = CourseQuestionLink.objects.filter(
        course=course,
        tree_node_id=tree_node_uuid,
        is_deleted=False,
    )
    queryset = ExamQuestion.objects.select_related('paper').filter(
        id__in=links.values('question_id'),
    )
    queryset = apply_course_question_filters(queryset, request.query_params)
    return Response({'success': True, 'data': paginate_question_queryset(queryset, request)})


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

    try:
        question_id = str(uuid.UUID(str(question_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('question_id must be a valid UUID')
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
    if not CourseQuestionLink.objects.filter(
        course=course, question_id=question_id, is_deleted=False
    ).exists():
        raise NotFound('题目不在课程中')
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

    task = create_variant_task_and_dispatch(
        question=question,
        variant_mode=variant_mode,
        tree_node_id=tree_node_id,
    )

    return Response({
        'success': True,
        'data': {'task_id': str(task.id), 'status': task.status, 'question_id': str(question_id)},
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

    course_question_ids = set(CourseQuestionLink.objects.filter(
        course=course, question_id__in=question_ids, is_deleted=False
    ).values_list('question_id', flat=True))
    missing_course_questions = set(question_ids) - {str(question_id) for question_id in course_question_ids}
    if missing_course_questions:
        raise NotFound('存在不属于当前课程的题目')

    from apps.parser.models import ExamQuestion
    questions = list(ExamQuestion.objects.filter(id__in=question_ids))
    if len(questions) != len(set(question_ids)):
        raise NotFound('存在不存在的题目')
    if any(question.review_status != 'confirmed' for question in questions):
        raise ValidationError('所有题目必须先确认后才能生成变式题')

    tasks = [create_variant_task_and_dispatch(
        question=question,
        variant_mode=variant_mode,
        tree_node_id=tree_node_id,
    ) for question in questions]

    return Response({
        'success': True,
        'data': {
            'task_ids': [str(task.id) for task in tasks],
            'status': 'pending',
            'question_count': len(tasks),
        },
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
    from django.utils import timezone as tz

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    node_ids = request.data.get('node_ids', [])
    mission_name = request.data.get('mission_name', f'{course.name} - 任务')
    level_type = request.data.get('level_type', 'practice')
    pass_rule = request.data.get('pass_rule', {'correct_rate': 0.6})
    class_id = request.data.get('class_id')
    deadline = request.data.get('deadline')

    if not node_ids:
        # 如果未选择节点，使用课程下所有根节点
        node_ids = list(CourseTree.objects.filter(
            course=course, parent=None
        ).values_list('id', flat=True))
        if not node_ids:
            raise ValidationError('课程目录为空，请先创建目录节点')

    # 创建任务
    mission = LearningMission.objects.create(
        mission_name=mission_name,
        creator_teacher_id=request.user,
        status='draft',
        class_obj_id=class_id if class_id else None,
        end_at=deadline if deadline else None,
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
    _check_course_access(course, request.user)

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
        file_type = material.file_type.lower()
        logger.info(f'文档类型：{file_type}, 文件路径：{full_path}')

        if file_type == 'pdf':
            # PDF 直接转图片
            from apps.parser.services.convert_service import pdf_to_images
            images = pdf_to_images(full_path, output_dir=pages_dir)
            for img in images:
                # img is a dict with keys: page_no, path, width, height
                img_path = img.get('path') if isinstance(img, dict) else img
                # Convert Windows backslashes to forward slashes for URL
                img_path = img_path.replace('\\', '/')
                page_images.append({
                    'url': f'{settings.MEDIA_URL}{img_path}',
                    'page': img.get('page_no', len(page_images) + 1) if isinstance(img, dict) else len(page_images) + 1,
                })
        elif file_type in ['word', 'docx', 'doc']:
            # Word 先转 PDF 再转图片
            from apps.parser.services.convert_service import word_to_pdf, pdf_to_images
            pdf_path = word_to_pdf(full_path, output_dir=pages_dir)
            if pdf_path:
                # parser.word_to_pdf returns a path relative to MEDIA_ROOT;
                # pdf_to_images requires a filesystem path.
                pdf_full_path = pdf_path
                if not os.path.isabs(pdf_full_path):
                    pdf_full_path = os.path.join(settings.MEDIA_ROOT, pdf_full_path)
                images = pdf_to_images(pdf_full_path, output_dir=pages_dir)
                for img in images:
                    img_path = img.get('path') if isinstance(img, dict) else img
                    img_path = img_path.replace('\\', '/')
                    page_images.append({
                        'url': f'{settings.MEDIA_URL}{img_path}',
                        'page': img.get('page_no', len(page_images) + 1) if isinstance(img, dict) else len(page_images) + 1,
                    })
        elif file_type in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']:
            # 图片直接返回
            rel_path = os.path.relpath(full_path, settings.MEDIA_ROOT).replace('\\', '/')
            page_images.append({
                'url': f'{settings.MEDIA_URL}{rel_path}',
                'page': 1,
            })
        else:
            raise ValidationError(f'不支持的文件类型：{file_type}，仅支持 PDF、Word 和图片格式')
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
    """框选区域 AI 识别，内部统一走公共视觉组件。"""

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    try:
        material = CourseMaterial.objects.get(id=material_id, course=course, is_deleted=False)
    except CourseMaterial.DoesNotExist:
        raise NotFound(f'资料 {material_id} 不存在')

    # 获取请求参数
    image_url = request.data.get('image_url', '')
    page = request.data.get('page', 1)
    crop_region = request.data.get('crop_region')  # {x1, y1, x2, y2}

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

    # 调用公共 AI 视觉组件；页面参数继续接受以保持接口兼容。
    del page
    try:
        result = _recognize_course_material_image(image_path, crop_region)
    except ValidationError:
        return Response(
            {'detail': 'AI 识别失败'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if result.get('error'):
        return Response({
            'success': False,
            'message': result['error'],
        })

    return Response({
        'success': True,
        'data': result,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_question(request, course_id):
    """保存从课程资料导入的题目"""
    from apps.parser.models import ExamQuestion, ExamPaper, QuestionImage, QuestionOption

    course = _get_course_or_404(course_id)
    _check_course_owner(course, request.user)

    # 获取题目数据
    question_data = request.data.get('question', {})
    tree_node_id = request.data.get('tree_node_id')

    if not question_data.get('stem'):
        raise ValidationError('题干不能为空')

    # 创建或获取试卷（导入的题目需要一个关联的试卷）
    paper, _ = ExamPaper.objects.get_or_create(
        title=f'课程导入 - {course.name}',
        defaults={
            'subject': course.subject,
            'grade_level': course.grade_level or '',
            'status': 'published',
        }
    )

    # 创建题目
    question = ExamQuestion.objects.create(
        paper=paper,
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
            source='import',
            source_course_name=course.name,
        )

    return Response({
        'success': True,
        'data': {
            'question_id': question.id,
        },
        'message': '题目导入成功',
    }, status=status.HTTP_201_CREATED)
