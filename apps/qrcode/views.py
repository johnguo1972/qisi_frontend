import base64
import json
import os
import secrets
import string
import uuid
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import StudentParentBind, UserAccount, WechatIdentity
from apps.accounts.auth import get_request_role
from apps.accounts.permissions import IsTeacherSession
from apps.accounts.roles import VALID_ROLES, has_user_role
from apps.accounts.serializers import serialize_user_session
from apps.accounts.services import (
    RoleNotGranted,
    ensure_parent_role_for_login,
    ensure_student_role_for_login,
    generate_tokens,
    get_or_create_user,
    verify_code,
)
from apps.institutions.models import ClassStudent, ClassTeacher
from apps.missions.models import LearningMission
from apps.study.models import AnswerAttempt
from apps.common.media import media_url
from apps.study.permissions import IsNotParentSession

from .models import AttemptImage, MissionShortCode, PaperScanBatch, PaperScanPage, StudentClassShortCode, WrongbookPracticeSheet
from .services import (
    analyze_image_blur, cache_wechat_pending, ensure_mission_short_code,
    ensure_student_short_code, ensure_mission_short_codes, mission_qr_url, paper_qr_url, qr_png, wxacode_png, wechat_url_link,
)


def trace_id():
    return uuid.uuid4().hex[:16]


def effective_student(request):
    active_role = get_request_role(request)
    if (
        active_role == 'student'
        and request.user.status == 'active'
        and has_user_role(request.user, 'student')
    ):
        return request.user
    if (
        active_role != 'parent'
        or request.user.status != 'active'
        or not has_user_role(request.user, 'parent')
    ):
        return None
    child_id = cache.get(f'parent_context:{request.user.id}')
    if not child_id:
        return None
    if str(child_id) == str(request.user.id) and has_user_role(request.user, 'student'):
        return request.user
    relation = StudentParentBind.objects.filter(
        parent_user_id=request.user, student_user_id=child_id, bind_status='active',
    ).select_related('student_user_id').first()
    if not relation or relation.student_user_id.status != 'active':
        return None
    return relation.student_user_id


def _is_platform_admin(request):
    return (
        get_request_role(request) == 'admin'
        and has_user_role(request.user, 'admin')
    )


def _is_related_teacher(request, student):
    return (
        get_request_role(request) == 'teacher'
        and has_user_role(request.user, 'teacher')
        and ClassTeacher.objects.filter(
            teacher=request.user,
            class_obj__class_students__student=student,
            class_obj__class_students__status='active',
        ).exists()
    )


def _can_access_student(request, student):
    owner = effective_student(request)
    return (
        (owner is not None and owner.id == student.id)
        or _is_platform_admin(request)
        or _is_related_teacher(request, student)
    )


def _expired(code):
    if code.status != 'active':
        return True
    if code.expires_at and timezone.now() > code.expires_at:
        if code.status != 'expired':
            code.status = 'expired'
            code.save(update_fields=['status', 'updated_at'])
        return True
    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_qrcode(request, mission_id):
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    class_id = request.query_params.get('class_id')
    class_obj = None
    if class_id:
        assignment = mission.class_assignments.filter(
            class_obj_id=class_id, status='active',
        ).select_related('class_obj').first()
        if assignment:
            class_obj = assignment.class_obj
        elif str(mission.class_obj_id or '') != str(class_id):
            return Response({'code': 404, 'message': '班级任务不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    code = ensure_mission_short_code(mission, class_obj=class_obj)
    try:
        size = max(180, min(800, int(request.query_params.get('size', 300))))
    except (TypeError, ValueError):
        size = 300
    return HttpResponse(qr_png(mission_qr_url(code.short_code), size), content_type='image/png')


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_qrcode_info(request, mission_id):
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    codes = ensure_mission_short_codes(mission)
    code = codes[0]
    image_data = base64.b64encode(qr_png(mission_qr_url(code.short_code), 300)).decode('ascii')
    return Response({'code': 0, 'message': 'success', 'data': {
        'short_code': code.short_code, 'url': mission_qr_url(code.short_code),
        'class_codes': [{'class_id': str(item.class_obj_id) if item.class_obj_id else None, 'short_code': item.short_code, 'url': mission_qr_url(item.short_code)} for item in codes],
        'status': code.status, 'expires_at': code.expires_at,
        'image_data': f'data:image/png;base64,{image_data}',
    }, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([AllowAny])
def short_code_info(request, short_code):
    code = MissionShortCode.objects.select_related('mission', 'class_obj').filter(short_code=short_code.upper()).first()
    if not code:
        return Response({'code': 404, 'message': '作业码不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    if _expired(code):
        return Response({'code': 4101, 'message': '作业码已过期', 'data': None, 'trace_id': trace_id()}, status=410)
    mission = code.mission
    if mission.status != 'published':
        return Response({'code': 4004, 'message': '作业尚未发布', 'data': None, 'trace_id': trace_id()}, status=400)
    return Response({'code': 0, 'message': 'success', 'data': {
        'mission_id': mission.id, 'mission_name': mission.mission_name,
        'class_id': code.class_obj_id, 'class_name': getattr(code.class_obj, 'class_name', None),
        'end_at': mission.end_at, 'short_code': code.short_code,
    }, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def enter_mission(request, short_code):
    code = MissionShortCode.objects.select_related('mission').filter(short_code=short_code.upper()).first()
    if not code or _expired(code):
        return Response({'code': 4101, 'message': '作业码无效或已过期', 'data': None, 'trace_id': trace_id()}, status=410)
    mission = code.mission
    if mission.status != 'published':
        return Response({'code': 4004, 'message': '作业尚未发布', 'data': None, 'trace_id': trace_id()}, status=400)
    effective_user = effective_student(request)
    if not effective_user:
        return Response({'code': 4002, 'message': '请先选择要代理的孩子', 'data': None, 'trace_id': trace_id()}, status=400)
    student_id = effective_user.id
    allowed = set(str(v) for v in (mission.target_student_ids or []))
    if code.class_obj_id:
        allowed_class = ClassStudent.objects.filter(class_obj_id=code.class_obj_id, student=effective_user, status='active').exists()
        if not allowed_class and str(student_id) not in allowed:
            return Response({'code': 403, 'message': '无权进入该作业', 'data': None, 'trace_id': trace_id()}, status=403)
    elif allowed and str(student_id) not in allowed:
        return Response({'code': 403, 'message': '无权进入该作业', 'data': None, 'trace_id': trace_id()}, status=403)
    from apps.study.models import StudentMissionProgress
    StudentMissionProgress.objects.get_or_create(mission=mission, student_user_id=effective_user)
    MissionShortCode.objects.filter(pk=code.pk).update(scan_count=code.scan_count + 1)
    return Response({'code': 0, 'message': 'success', 'data': {'mission_id': mission.id, 'redirect_url': f'/pages/student/mission?id={mission.id}'}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def upload_attempt_image(request, attempt_id):
    owner = effective_student(request)
    if not owner:
        return Response({'code': 4002, 'message': '请先选择要代理的孩子', 'data': None, 'trace_id': trace_id()}, status=400)
    try:
        attempt = AnswerAttempt.objects.get(pk=attempt_id, student_user_id=owner)
    except AnswerAttempt.DoesNotExist:
        return Response({'code': 404, 'message': '作答记录不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    image = request.FILES.get('image')
    if not image:
        return Response({'code': 400, 'message': '缺少图片', 'data': None, 'trace_id': trace_id()}, status=400)
    page_no = int(request.data.get('page_no') or 1)
    directory = Path(settings.MEDIA_ROOT) / 'attempts' / str(attempt.id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f'{page_no}_{uuid.uuid4().hex}{Path(image.name).suffix.lower() or ".jpg"}'
    destination = directory / filename
    with destination.open('wb') as target:
        for chunk in image.chunks():
            target.write(chunk)
    relative = f'attempts/{attempt.id}/{filename}'
    blur_score, is_blurry = analyze_image_blur(image)
    item, _ = AttemptImage.objects.update_or_create(
        attempt=attempt, page_no=page_no,
        defaults={'student': owner, 'question_id': attempt.question_id, 'image_url': relative, 'file_size': image.size,
                  'blur_score': blur_score, 'is_blurry': is_blurry, 'upload_status': 'completed'},
    )
    attempt.image_count = AttemptImage.objects.filter(attempt=attempt).count()
    attempt.submit_source = 'photo'
    attempt.save(update_fields=['image_count', 'submit_source'])
    return Response({'code': 0, 'message': '上传成功', 'data': {'id': item.id, 'url': media_url(item.image_url), 'page_no': item.page_no, 'image_count': attempt.image_count}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([AllowAny])
def wechat_login(request):
    code = str(request.data.get('code') or '').strip()
    if not code:
        return Response({'code': 400, 'message': '缺少微信登录 code', 'data': None, 'trace_id': trace_id()}, status=400)
    appid = getattr(settings, 'WECHAT_MP_APPID', '')
    secret = getattr(settings, 'WECHAT_MP_APPSECRET', '')
    if not appid or not secret:
        return Response({'code': 503, 'message': '微信登录服务未配置', 'data': None, 'trace_id': trace_id()}, status=503)
    import requests
    try:
        result = requests.get('https://api.weixin.qq.com/sns/jscode2session', params={'appid': appid, 'secret': secret, 'js_code': code, 'grant_type': 'authorization_code'}, timeout=8).json()
    except requests.RequestException:
        return Response({'code': 502, 'message': '微信服务暂不可用', 'data': None, 'trace_id': trace_id()}, status=502)
    if result.get('errcode') or not result.get('openid'):
        return Response({'code': 400, 'message': result.get('errmsg', '微信登录失败'), 'data': None, 'trace_id': trace_id()}, status=400)
    identity = WechatIdentity.objects.select_related('user').filter(appid=appid, openid=result['openid']).first()
    if identity:
        user = identity.user
        active_role = request.data.get('role_type') or user.role_type
        if active_role not in VALID_ROLES:
            return Response({'code': 'INVALID_ROLE', 'message': 'Invalid role', 'data': None, 'trace_id': trace_id()}, status=400)
        if user.status != 'active':
            return Response({'code': 'ACCOUNT_INACTIVE', 'message': 'Account is inactive', 'data': None, 'trace_id': trace_id()}, status=403)
        if active_role == 'parent':
            try:
                user = ensure_parent_role_for_login(user)
            except RoleNotGranted:
                return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
        elif active_role == 'student' and has_user_role(user, 'teacher'):
            try:
                user = ensure_student_role_for_login(user)
            except RoleNotGranted:
                return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
        elif not has_user_role(user, active_role):
            return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
        return Response({'code': 0, 'message': '登录成功', 'data': {**generate_tokens(user, active_role), 'user': serialize_user_session(user, active_role)}, 'trace_id': trace_id()})
    return Response({'code': 1001, 'message': '请先绑定手机号', 'data': {'bind_token': cache_wechat_pending(appid, result['openid'], result.get('unionid', ''))}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([AllowAny])
def wechat_bind(request):
    pending_key = f"wechat_pending:{request.data.get('bind_token', '')}"
    pending = cache.get(pending_key)
    mobile = str(request.data.get('mobile') or '')
    verify = str(request.data.get('verify_code') or '')
    if not pending or not mobile or not verify_code(mobile, verify):
        return Response({'code': 4001, 'message': '绑定信息无效或验证码错误', 'data': None, 'trace_id': trace_id()}, status=400)
    existing_user = UserAccount.objects.filter(mobile=mobile).first()
    active_role = request.data.get('role_type') or (
        existing_user.role_type if existing_user is not None else 'student'
    )
    if active_role not in VALID_ROLES:
        return Response({'code': 'INVALID_ROLE', 'message': 'Invalid role', 'data': None, 'trace_id': trace_id()}, status=400)
    if existing_user is None and active_role not in ('student', 'parent'):
        return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
    if existing_user is not None:
        if existing_user.status != 'active':
            return Response({'code': 'ACCOUNT_INACTIVE', 'message': 'Account is inactive', 'data': None, 'trace_id': trace_id()}, status=403)
        if active_role == 'parent':
            try:
                existing_user = ensure_parent_role_for_login(existing_user)
            except RoleNotGranted:
                return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
        elif active_role == 'student' and has_user_role(existing_user, 'teacher'):
            try:
                existing_user = ensure_student_role_for_login(existing_user)
            except RoleNotGranted:
                return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
        elif not has_user_role(existing_user, active_role):
            return Response({'code': 'ROLE_NOT_GRANTED', 'message': 'Role is not granted', 'data': None, 'trace_id': trace_id()}, status=403)
    user, _ = get_or_create_user(
        mobile, initial_role=active_role, grant_source='self_login'
    )
    identity, _ = WechatIdentity.objects.update_or_create(user=user, defaults={'appid': pending['appid'], 'openid': pending['openid'], 'unionid': pending.get('unionid', '')})
    cache.delete(pending_key)
    return Response({'code': 0, 'message': '绑定成功', 'data': {**generate_tokens(user, active_role), 'user': serialize_user_session(user, active_role)}, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_children(request):
    if (
        get_request_role(request) != 'parent'
        or not has_user_role(request.user, 'parent')
        or request.user.status != 'active'
    ):
        return Response({'code': 403, 'message': 'parent role required'}, status=403)
    children = StudentParentBind.objects.filter(parent_user_id=request.user, bind_status='active').select_related('student_user_id')
    data = [{
        'id': b.student_user_id_id,
        'display_name': b.student_user_id.display_name,
        'grade_level': b.student_user_id.grade_level,
        'is_self': False,
        'relation_type': b.relation_type,
    } for b in children]
    if has_user_role(request.user, 'student'):
        data.insert(0, {
            'id': request.user.id,
            'display_name': request.user.display_name,
            'grade_level': request.user.grade_level,
            'is_self': True,
            'relation_type': 'self',
        })
    return Response({'code': 0, 'message': 'success', 'data': data, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def parent_context(request):
    child_id = request.data.get('student_id')
    is_self_student = (
        str(child_id) == str(request.user.id)
        and get_request_role(request) == 'parent'
        and has_user_role(request.user, 'parent')
        and has_user_role(request.user, 'student')
        and request.user.status == 'active'
    )
    if not is_self_student and (
        get_request_role(request) != 'parent'
        or not has_user_role(request.user, 'parent')
        or request.user.status != 'active'
        or not StudentParentBind.objects.filter(
            parent_user_id=request.user,
            student_user_id=child_id,
            bind_status='active',
        ).exists()
    ):
        return Response({'code': 403, 'message': '孩子未绑定或无权切换', 'data': None, 'trace_id': trace_id()}, status=403)
    cache.set(f'parent_context:{request.user.id}', str(child_id), timeout=1800)
    return Response({'code': 0, 'message': '代理对象已切换', 'data': {'student_id': child_id}, 'trace_id': trace_id()})


PARENT_BIND_CODE_TTL = 3600


def _parent_bind_code_key(code):
    return f'parent_bind_code:{code}'


def _parent_bind_code_owner_key(student_id):
    return f'parent_bind_code_owner:{student_id}'


def _new_parent_bind_code():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


def _is_student_session(request):
    return (
        get_request_role(request) == 'student'
        and has_user_role(request.user, 'student')
        and request.user.status == 'active'
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_parent_bind_code(request):
    """Create a short-lived code that identifies the authenticated student."""
    if not _is_student_session(request):
        return Response({
            'code': 'STUDENT_ROLE_REQUIRED',
            'message': '请先以学生身份进入家长绑定',
            'data': None,
            'trace_id': trace_id(),
        }, status=403)

    previous_code = cache.get(_parent_bind_code_owner_key(request.user.id))
    if previous_code:
        cache.delete(_parent_bind_code_key(previous_code))

    code = _new_parent_bind_code()
    while cache.get(_parent_bind_code_key(code)):
        code = _new_parent_bind_code()
    cache.set(
        _parent_bind_code_key(code),
        {'student_id': str(request.user.id)},
        timeout=PARENT_BIND_CODE_TTL,
    )
    cache.set(
        _parent_bind_code_owner_key(request.user.id),
        code,
        timeout=PARENT_BIND_CODE_TTL,
    )
    return Response({
        'code': 0,
        'message': '申请码已生成',
        'data': {'bind_code': code, 'expires_in': PARENT_BIND_CODE_TTL},
        'trace_id': trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_parent_bind_request(request):
    """Create a pending parent-child request from a parent account."""
    if (
        get_request_role(request) != 'parent'
        or not has_user_role(request.user, 'parent')
        or request.user.status != 'active'
    ):
        return Response({
            'code': 'PARENT_ROLE_REQUIRED',
            'message': '请先以家长身份登录',
            'data': None,
            'trace_id': trace_id(),
        }, status=403)

    code = str(request.data.get('bind_code') or '').strip().upper()
    relation_type = str(request.data.get('relation_type') or 'guardian').strip().lower()
    if relation_type not in ('father', 'mother', 'guardian'):
        return Response({
            'code': 'INVALID_RELATION',
            'message': '关系类型不正确',
            'data': None,
            'trace_id': trace_id(),
        }, status=400)
    payload = cache.get(_parent_bind_code_key(code)) if code else None
    if not payload:
        return Response({
            'code': 'BIND_CODE_INVALID',
            'message': '申请码无效或已过期',
            'data': None,
            'trace_id': trace_id(),
        }, status=400)

    student_id = payload.get('student_id') if isinstance(payload, dict) else payload
    try:
        student = UserAccount.objects.get(pk=student_id, status='active')
    except (UserAccount.DoesNotExist, ValueError, TypeError):
        cache.delete(_parent_bind_code_key(code))
        return Response({
            'code': 'STUDENT_NOT_FOUND',
            'message': '学生账号不存在或已停用',
            'data': None,
            'trace_id': trace_id(),
        }, status=404)
    if not has_user_role(student, 'student'):
        return Response({
            'code': 'INVALID_STUDENT_BINDING',
            'message': '申请码对应的账号不是学生账号',
            'data': None,
            'trace_id': trace_id(),
        }, status=400)
    if student.id == request.user.id:
        return Response({
            'code': 'SELF_BINDING_NOT_ALLOWED',
            'message': '家长账号不能绑定自己，请使用其他学生账号生成申请码',
            'data': None,
            'trace_id': trace_id(),
        }, status=400)

    relation = StudentParentBind.objects.filter(
        parent_user_id=request.user,
        student_user_id=student,
    ).first()
    if relation and relation.bind_status == 'active':
        return Response({
            'code': 'ALREADY_BOUND',
            'message': '该学生已经绑定',
            'data': None,
            'trace_id': trace_id(),
        }, status=409)
    if relation:
        relation.relation_type = relation_type
        relation.bind_status = 'pending'
        relation.save(update_fields=['relation_type', 'bind_status'])
    else:
        relation = StudentParentBind.objects.create(
            parent_user_id=request.user,
            student_user_id=student,
            relation_type=relation_type,
            bind_status='pending',
        )
    cache.delete(_parent_bind_code_key(code))
    cache.delete(_parent_bind_code_owner_key(student.id))
    return Response({
        'code': 0,
        'message': '绑定申请已提交，等待学生确认',
        'data': {
            'id': str(relation.id),
            'student_id': str(student.id),
            'student_name': student.display_name,
            'bind_status': relation.bind_status,
        },
        'trace_id': trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_bind_requests(request):
    if get_request_role(request) != 'parent' or not has_user_role(request.user, 'parent'):
        return Response({'code': 'PARENT_ROLE_REQUIRED', 'message': '请先以家长身份登录', 'data': None, 'trace_id': trace_id()}, status=403)
    rows = StudentParentBind.objects.filter(
        parent_user_id=request.user,
        bind_status='pending',
    ).select_related('student_user_id').order_by('-bound_at')
    return Response({
        'code': 0,
        'message': 'success',
        'data': [{
            'id': str(row.id),
            'student_id': str(row.student_user_id_id),
            'student_name': row.student_user_id.display_name,
            'relation_type': row.relation_type,
            'bind_status': row.bind_status,
        } for row in rows],
        'trace_id': trace_id(),
    })


def _student_bind_requests_response(request):
    if not _is_student_session(request):
        return Response({'code': 'STUDENT_ROLE_REQUIRED', 'message': '请先以学生身份登录', 'data': None, 'trace_id': trace_id()}, status=403)
    rows = StudentParentBind.objects.filter(
        student_user_id=request.user,
        bind_status='pending',
    ).select_related('parent_user_id').order_by('-bound_at')
    return Response({
        'code': 0,
        'message': 'success',
        'data': [{
            'id': str(row.id),
            'parent_id': str(row.parent_user_id_id),
            'parent_name': row.parent_user_id.display_name,
            'parent_mobile': row.parent_user_id.mobile,
            'relation_type': row.relation_type,
            'bind_status': row.bind_status,
        } for row in rows],
        'trace_id': trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_parent_bind_requests(request):
    return _student_bind_requests_response(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def student_parent_bind_decision(request, bind_id):
    if not _is_student_session(request):
        return Response({'code': 'STUDENT_ROLE_REQUIRED', 'message': '请先以学生身份登录', 'data': None, 'trace_id': trace_id()}, status=403)
    decision = str(request.data.get('decision') or '').strip().lower()
    if decision not in ('approve', 'reject'):
        return Response({'code': 'INVALID_DECISION', 'message': '确认操作不正确', 'data': None, 'trace_id': trace_id()}, status=400)
    relation = StudentParentBind.objects.filter(
        id=bind_id,
        student_user_id=request.user,
        bind_status='pending',
    ).first()
    if relation is None:
        return Response({'code': 'BIND_REQUEST_NOT_FOUND', 'message': '绑定申请不存在或已处理', 'data': None, 'trace_id': trace_id()}, status=404)
    relation.bind_status = 'active' if decision == 'approve' else 'rejected'
    relation.save(update_fields=['bind_status'])
    return Response({
        'code': 0,
        'message': '绑定已确认' if decision == 'approve' else '绑定申请已拒绝',
        'data': {'id': str(relation.id), 'bind_status': relation.bind_status},
        'trace_id': trace_id(),
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def remove_parent_bind(request, bind_id):
    if get_request_role(request) != 'parent' or not has_user_role(request.user, 'parent'):
        return Response({'code': 'PARENT_ROLE_REQUIRED', 'message': '请先以家长身份登录', 'data': None, 'trace_id': trace_id()}, status=403)
    relation = StudentParentBind.objects.filter(
        id=bind_id,
        parent_user_id=request.user,
        bind_status='active',
    ).first()
    if relation is None:
        return Response({'code': 'BIND_NOT_FOUND', 'message': '绑定关系不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    relation.bind_status = 'removed'
    relation.save(update_fields=['bind_status'])
    cache.delete(f'parent_context:{request.user.id}')
    return Response({'code': 0, 'message': '绑定已解除', 'data': None, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def create_scan_batch(request):
    try:
        mission = LearningMission.objects.get(
            pk=request.data.get('mission_id'),
            creator_teacher_id=request.user,
        )
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    batch = PaperScanBatch.objects.create(mission=mission, operator=request.user, expected_count=int(request.data.get('expected_count') or 0))
    return Response({'code': 0, 'message': 'success', 'data': {'batch_id': batch.id}, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def class_student_codes(request, class_id):
    from apps.institutions.models import Class, ClassTeacher
    try:
        class_obj = Class.objects.get(pk=class_id)
    except Class.DoesNotExist:
        return Response({'code': 404, 'message': '班级不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    allowed = ClassTeacher.objects.filter(
        class_obj=class_obj,
        teacher=request.user,
    ).exists()
    if not allowed:
        return Response({'code': 403, 'message': '无权查看班级学生码', 'data': None, 'trace_id': trace_id()}, status=403)
    rows = []
    for link in ClassStudent.objects.filter(class_obj=class_obj, status='active').select_related('student'):
        code = ensure_student_short_code(link.student, class_obj)
        rows.append({'student_id': link.student_id, 'student_name': link.student.display_name, 'student_code': code.short_code})
    return Response({'code': 0, 'message': 'success', 'data': rows, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def upload_scan_page(request, batch_id):
    from .models import StudentClassShortCode
    try:
        batch = PaperScanBatch.objects.select_related('mission').get(pk=batch_id, operator=request.user)
    except PaperScanBatch.DoesNotExist:
        return Response({'code': 404, 'message': '扫描批次不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    image = request.FILES.get('image')
    student_code = str(request.data.get('student_code') or '').strip().upper()
    mission_code = str(request.data.get('mission_code') or '').strip().upper()
    page_no = int(request.data.get('page_no') or 1)
    total_pages = int(request.data.get('total_pages') or 1)
    short = StudentClassShortCode.objects.select_related('student').filter(short_code=student_code, status='active').first()
    mission_short = MissionShortCode.objects.filter(mission=batch.mission, short_code=mission_code, status='active').first()
    if not short or not mission_short or not image:
        return Response({'code': 400, 'message': '二维码、任务或图片无效', 'data': None, 'trace_id': trace_id()}, status=400)
    directory = Path(settings.MEDIA_ROOT) / 'paper-scan' / str(batch.id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid.uuid4().hex}{Path(image.name).suffix.lower() or ".jpg"}'
    destination = directory / filename
    with destination.open('wb') as target:
        for chunk in image.chunks(): target.write(chunk)
    page, created = PaperScanPage.objects.get_or_create(
        batch=batch, student=short.student, page_no=page_no,
        defaults={'student_code': student_code, 'mission_code': mission_code, 'total_pages': total_pages, 'image_url': f'paper-scan/{batch.id}/{filename}'},
    )
    if not created:
        page.status = 'duplicate'
        page.save(update_fields=['status'])
    return Response({'code': 0, 'message': '页面已上传', 'data': {'page_id': page.id, 'status': page.status, 'duplicate': not created}, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def scan_batch_summary(request, batch_id):
    try:
        batch = PaperScanBatch.objects.get(pk=batch_id, operator=request.user)
    except PaperScanBatch.DoesNotExist:
        return Response({'code': 404, 'message': '扫描批次不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    pages = batch.pages.all()
    students = {str(page.student_id) for page in pages}
    duplicates = pages.filter(status='duplicate').count()
    return Response({'code': 0, 'message': 'success', 'data': {'student_count': len(students), 'received_pages': pages.count(), 'duplicate_pages': duplicates, 'unknown_codes': 0, 'missing_pages': 0}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def complete_scan_batch(request, batch_id):
    try:
        batch = PaperScanBatch.objects.get(pk=batch_id, operator=request.user)
    except PaperScanBatch.DoesNotExist:
        return Response({'code': 404, 'message': '扫描批次不存在', 'data': None, 'trace_id': trace_id()}, status=404)
    if batch.pages.filter(status__in=['duplicate']).exists():
        return Response({'code': 400, 'message': '存在重复页，不能归档', 'data': None, 'trace_id': trace_id()}, status=400)
    batch.status = 'completed'
    batch.completed_at = timezone.now()
    batch.save(update_fields=['status', 'completed_at'])
    batch.pages.filter(status='uploaded').update(status='archived')
    return Response({'code': 0, 'message': '扫描批次已归档', 'data': {'status': batch.status}, 'trace_id': trace_id()})
# QR follow-up endpoints are defined below.

def _mission_students(mission, requested_id=None):
    from apps.institutions.models import ClassStudent
    if requested_id:
        link = ClassStudent.objects.filter(
            Q(class_obj=mission.class_obj) | Q(class_obj__mission_assignments__mission=mission, class_obj__mission_assignments__status='active'),
            student_id=requested_id, status='active',
        ).select_related('student').first()
        return [link.student] if link else []
    assignment_class_ids = list(mission.class_assignments.filter(status='active').values_list('class_obj_id', flat=True))
    if mission.class_obj_id:
        assignment_class_ids.append(mission.class_obj_id)
    if assignment_class_ids:
        return list(UserAccount.objects.filter(
            student_classes__class_obj_id__in=assignment_class_ids,
            student_classes__status='active',
        ).distinct())
    ids = [str(value) for value in (mission.target_student_ids or [])]
    return list(UserAccount.objects.filter(
        id__in=ids,
        role_grants__role='student',
        role_grants__status='active',
    ).distinct())


def _mission_student_class(mission, student):
    """Pick the student's active class for a multi-class paper."""
    class_ids = list(mission.class_assignments.filter(status='active').values_list('class_obj_id', flat=True))
    if mission.class_obj_id:
        class_ids.append(mission.class_obj_id)
    return ClassStudent.objects.filter(
        class_obj_id__in=class_ids, student=student, status='active',
    ).select_related('class_obj').first().class_obj if ClassStudent.objects.filter(
        class_obj_id__in=class_ids, student=student, status='active',
    ).exists() else mission.class_obj


def _paper_pdf(mission, students, mission_code):
    import io
    import textwrap
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from apps.missions.models import MissionQuestionRel
    from apps.parser.models import ExamQuestion
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    count = MissionQuestionRel.objects.filter(mission=mission).count()
    for student in students:
        student_class = _mission_student_class(mission, student)
        student_code = ensure_student_short_code(student, student_class).short_code
        student_mission_code = ensure_mission_short_code(mission, student_class).short_code
        qr = ImageReader(io.BytesIO(qr_png(paper_qr_url(student_code, student_mission_code, 1), 240)))
        pdf.setFont('Helvetica-Bold', 18)
        pdf.drawCentredString(width / 2, height - 45, str(mission.mission_name))
        pdf.setFont('Helvetica', 11)
        pdf.drawString(45, height - 75, f'Student: {student.display_name or student.login_name}')
        pdf.drawString(45, height - 95, f'Paper code: {student_code}-{student_mission_code}')
        pdf.drawImage(qr, width - 160, height - 170, width=110, height=110, preserveAspectRatio=True, mask='auto')
        pdf.drawString(45, height - 140, f'Questions: {count}')
        pdf.line(45, height - 180, width - 45, height - 180)
        pdf.drawString(45, height - 205, 'Scan the QR code after completing this paper to upload pages.')
        y = height - 235
        pdf.setFont('Helvetica', 10)
        relations = MissionQuestionRel.objects.filter(mission=mission).order_by('sort_no')
        questions = {str(q.id): q for q in ExamQuestion.objects.filter(id__in=relations.values_list('question_id', flat=True))}
        for number, relation in enumerate(relations, 1):
            question = questions.get(str(relation.question_id))
            if not question:
                continue
            lines = textwrap.wrap(str(question.stem or ''), width=78) or ['']
            for line_no, line in enumerate(lines):
                if y < 55:
                    pdf.showPage()
                    pdf.setFont('Helvetica', 10)
                    y = height - 50
                pdf.drawString(45, y, f'{number}. ' + line if line_no == 0 else '    ' + line)
                y -= 15
            y -= 8
        pdf.showPage()
    pdf.save()
    return output.getvalue()


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_wxacode(request, mission_id):
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found', 'data': None, 'trace_id': trace_id()}, status=404)
    code = ensure_mission_short_code(mission)
    try:
        content = wxacode_png(code.short_code)
    except RuntimeError as exc:
        return Response({'code': 503, 'message': str(exc), 'data': None, 'trace_id': trace_id()}, status=503)
    return HttpResponse(content, content_type='image/png')


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_paper_pdf(request, mission_id):
    if (
        get_request_role(request) != 'teacher'
        or not has_user_role(request.user, 'teacher')
    ):
        return Response({'code': 403, 'message': 'teacher role required', 'data': None, 'trace_id': trace_id()}, status=403)
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found', 'data': None, 'trace_id': trace_id()}, status=404)
    students = _mission_students(mission, request.query_params.get('student_id'))
    if not students or not (mission.class_obj_id or mission.class_assignments.filter(status='active').exists()):
        return Response({'code': 400, 'message': 'mission has no printable class students', 'data': None, 'trace_id': trace_id()}, status=400)
    code = ensure_mission_short_code(mission)
    response = HttpResponse(_paper_pdf(mission, students, code.short_code), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="paper-{mission.mission_no}.pdf"'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def paper_entry(request, student_code, mission_code, page_no):
    student_code = str(student_code).upper()
    mission_code = str(mission_code).upper()
    student_row = StudentClassShortCode.objects.select_related('student', 'class_obj').filter(short_code=student_code, status='active').first()
    mission_row = MissionShortCode.objects.select_related('mission', 'class_obj').filter(short_code=mission_code).first()
    if not student_row or not mission_row or _expired(mission_row):
        return Response({'code': 404, 'message': 'paper code not found or expired', 'data': None, 'trace_id': trace_id()}, status=404)
    if mission_row.class_obj_id and mission_row.class_obj_id != student_row.class_obj_id:
        return Response({'code': 403, 'message': 'student is not in mission class', 'data': None, 'trace_id': trace_id()}, status=403)
    if page_no < 1:
        return Response({'code': 400, 'message': 'page number must be positive', 'data': None, 'trace_id': trace_id()}, status=400)
    return Response({'code': 0, 'message': 'success', 'data': {'student_id': student_row.student_id, 'student_name': student_row.student.display_name, 'mission_id': mission_row.mission_id, 'mission_name': mission_row.mission.mission_name, 'student_code': student_code, 'mission_code': mission_code, 'page_no': page_no}, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def practice_sheet_info(request, sheet_code):
    sheet = WrongbookPracticeSheet.objects.select_related('student').filter(sheet_code=str(sheet_code).upper()).first()
    if not sheet:
        return Response({'code': 404, 'message': 'practice sheet not found', 'data': None, 'trace_id': trace_id()}, status=404)
    if not _can_access_student(request, sheet.student):
        return Response({'code': 403, 'message': 'no permission', 'data': None, 'trace_id': trace_id()}, status=403)
    return Response({'code': 0, 'message': 'success', 'data': {'sheet_id': sheet.id, 'sheet_code': sheet.sheet_code, 'student_id': sheet.student_id, 'student_name': sheet.student.display_name, 'mode': sheet.mode, 'status': sheet.status, 'original_question_id': sheet.original_question_id, 'variant_question_ids': sheet.variant_question_ids, 'wrong_reason_hint': sheet.wrong_reason_hint}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def create_practice_sheet(request):
    from apps.wrongbook.models import WrongBookItem
    from apps.wrongbook.services import find_variant_questions
    try:
        item = WrongBookItem.objects.get(pk=request.data.get('wrong_item_id'))
    except WrongBookItem.DoesNotExist:
        return Response({'code': 404, 'message': 'wrong book item not found', 'data': None, 'trace_id': trace_id()}, status=404)
    if not _can_access_student(request, item.student_user_id):
        return Response({'code': 403, 'message': 'no permission', 'data': None, 'trace_id': trace_id()}, status=403)
    requested_student_id = request.data.get('student_id')
    if requested_student_id and str(requested_student_id) != str(item.student_user_id_id):
        return Response({'code': 400, 'message': 'student_id must match wrong item owner', 'data': None, 'trace_id': trace_id()}, status=400)
    code = uuid.uuid4().hex[:6].upper()
    while WrongbookPracticeSheet.objects.filter(sheet_code=code).exists():
        code = uuid.uuid4().hex[:6].upper()
    variants = find_variant_questions(item.question_id, limit=3)
    sheet = WrongbookPracticeSheet.objects.create(student_id=item.student_user_id_id, wrong_item=item, original_question_id=item.question_id, variant_question_ids=[str(q['id']) for q in variants], wrong_reason_hint=item.wrong_reason_type or '', sheet_code=code, mode=str(request.data.get('mode') or 'online'))
    return Response({'code': 0, 'message': 'success', 'data': {'sheet_code': sheet.sheet_code, 'sheet_id': sheet.id}}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def submit_practice_sheet(request, sheet_code):
    sheet = WrongbookPracticeSheet.objects.filter(sheet_code=str(sheet_code).upper()).first()
    owner = effective_student(request)
    if not sheet or not owner or sheet.student_id != owner.id:
        return Response({'code': 403, 'message': 'no permission', 'data': None, 'trace_id': trace_id()}, status=403)
    sheet.answers_json = request.data.get('answers') or {}
    sheet.submit_source = str(request.data.get('submit_source') or 'online')
    sheet.status = 'submitted'
    sheet.submitted_at = timezone.now()
    sheet.save(update_fields=['answers_json', 'submit_source', 'status', 'submitted_at', 'updated_at'])
    return Response({'code': 0, 'message': 'success', 'data': {'status': sheet.status, 'submitted_at': sheet.submitted_at}, 'trace_id': trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def practice_sheet_qrcode(request, sheet_code):
    sheet = WrongbookPracticeSheet.objects.filter(sheet_code=str(sheet_code).upper()).first()
    if not sheet:
        return Response({'code': 404, 'message': 'practice sheet not found', 'data': None, 'trace_id': trace_id()}, status=404)
    url = f"{getattr(settings, 'PUBLIC_WEB_URL', '').rstrip('/')}/practice/{sheet.sheet_code}"
    return HttpResponse(qr_png(url), content_type='image/png')
def _validate_image_file(image):
    allowed = {'image/jpeg', 'image/png', 'image/webp'}
    return image and image.content_type in allowed and image.size <= 5 * 1024 * 1024


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def upload_attempt_images(request, attempt_id):
    owner = effective_student(request)
    if not owner:
        return Response({'code': 4002, 'message': 'select a child first', 'data': None, 'trace_id': trace_id()}, status=400)
    try:
        attempt = AnswerAttempt.objects.get(pk=attempt_id, student_user_id=owner)
    except AnswerAttempt.DoesNotExist:
        return Response({'code': 404, 'message': 'attempt not found', 'data': None, 'trace_id': trace_id()}, status=404)
    images = request.FILES.getlist('images') or request.FILES.getlist('image')
    if not images:
        return Response({'code': 400, 'message': 'images are required', 'data': None, 'trace_id': trace_id()}, status=400)
    start_page = int(request.data.get('page_no') or 1)
    directory = Path(settings.MEDIA_ROOT) / 'attempts' / str(attempt.id)
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for offset, image in enumerate(images):
        if not _validate_image_file(image):
            return Response({'code': 400, 'message': 'only jpeg/png/webp under 5MB is allowed', 'data': None, 'trace_id': trace_id()}, status=400)
        page_no = start_page + offset
        filename = f'{page_no}_{uuid.uuid4().hex}{Path(image.name).suffix.lower() or ".jpg"}'
        destination = directory / filename
        with destination.open('wb') as target:
            for chunk in image.chunks():
                target.write(chunk)
        score, blurry = analyze_image_blur(image)
        item, _ = AttemptImage.objects.update_or_create(
            attempt=attempt, page_no=page_no,
            defaults={'student': owner, 'question_id': attempt.question_id, 'image_url': f'attempts/{attempt.id}/{filename}', 'file_size': image.size, 'blur_score': score, 'is_blurry': blurry, 'upload_status': 'completed'},
        )
        result.append({'id': item.id, 'page_no': page_no, 'url': media_url(item.image_url), 'blur_score': item.blur_score, 'is_blurry': item.is_blurry})
    attempt.image_count = AttemptImage.objects.filter(attempt=attempt).count()
    attempt.submit_source = 'photo'
    attempt.save(update_fields=['image_count', 'submit_source'])
    return Response({'code': 0, 'message': 'success', 'data': {'items': result, 'image_count': attempt.image_count}, 'trace_id': trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotParentSession])
def attempt_image_check(request):
    image = request.FILES.get('image')
    if not _validate_image_file(image):
        return Response({'code': 400, 'message': 'only jpeg/png/webp under 5MB is allowed', 'data': None, 'trace_id': trace_id()}, status=400)
    score, blurry = analyze_image_blur(image)
    return Response({'code': 0, 'message': 'success', 'data': {'blur_score': score, 'is_blurry': blurry, 'threshold': 50}, 'trace_id': trace_id()})
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_practice_sheet(request, mission_id):
    from apps.wrongbook.models import WrongBookItem
    from apps.wrongbook.services import find_variant_questions
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found', 'data': None, 'trace_id': trace_id()}, status=404)
    student_id = request.data.get('student_id')
    item_ids = request.data.get('wrong_item_ids') or ([request.data.get('wrong_item_id')] if request.data.get('wrong_item_id') else [])
    items = WrongBookItem.objects.filter(id__in=item_ids, student_user_id_id=student_id)[:20]
    if not items:
        return Response({'code': 400, 'message': 'wrong_item_ids are required for the selected student', 'data': None, 'trace_id': trace_id()}, status=400)
    sheets = []
    for item in items:
        code = uuid.uuid4().hex[:6].upper()
        while WrongbookPracticeSheet.objects.filter(sheet_code=code).exists():
            code = uuid.uuid4().hex[:6].upper()
        variants = find_variant_questions(item.question_id, limit=3)
        sheet = WrongbookPracticeSheet.objects.create(student_id=student_id, class_obj=mission.class_obj, wrong_item=item, original_question_id=item.question_id, variant_question_ids=[str(q['id']) for q in variants], wrong_reason_hint=item.wrong_reason_type or '', sheet_code=code, mode=str(request.data.get('mode') or 'online'))
        sheets.append({'sheet_id': sheet.id, 'sheet_code': sheet.sheet_code})
    return Response({'code': 0, 'message': 'success', 'data': {'items': sheets}}, status=201)
@api_view(['GET'])
@permission_classes([AllowAny])
def short_code_url_link(request, short_code):
    code = MissionShortCode.objects.filter(short_code=str(short_code).upper()).first()
    if not code or _expired(code):
        return Response({'code': 404, 'message': 'mission code not found or expired', 'data': None, 'trace_id': trace_id()}, status=404)
    try:
        link = wechat_url_link(code.short_code)
    except RuntimeError as exc:
        return Response({'code': 503, 'message': str(exc), 'data': None, 'trace_id': trace_id()}, status=503)
    return Response({'code': 0, 'message': 'success', 'data': {'url_link': link, 'short_code': code.short_code}, 'trace_id': trace_id()})
