import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import get_request_role
from .models import UserAccount
from .roles import VALID_ROLES, has_user_role
from .serializers import (
    LoginSerializer,
    ProfileUpdateSerializer,
    RefreshTokenSerializer,
    WebBindingCompleteSerializer,
    WebBindingSessionSerializer,
    serialize_user_session,
)
from .services import (
    verify_code, get_or_create_user, generate_tokens,
    generate_verify_code, send_sms_code, ensure_fixed_test_account,
    is_fixed_test_account_code,
)
from .wechat_web import (
    WebBindingError,
    bind_web_identity_from_miniprogram,
    complete_web_binding,
    get_web_binding_status,
)


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def role_error(code, message, http_status):
    return Response({
        'code': code,
        'message': message,
        'data': None,
        'trace_id': make_trace_id(),
    }, status=http_status)


def binding_error(code, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({
        'code': code,
        'message': '微信网页绑定无效或已过期',
        'data': None,
        'trace_id': make_trace_id(),
    }, status=http_status)


def browser_session_id(request):
    """Get the server-managed browser session identifier, never a client field."""
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """AUTH-01: Login with mobile + verification code."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mobile = serializer.validated_data['mobile']
    code = serializer.validated_data['verify_code']

    fixed_test_login = is_fixed_test_account_code(mobile, code)
    if not fixed_test_login and not verify_code(mobile, code):
        return Response({
            'code': 4001, 'message': '验证码错误或已过期', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    active_role = request.data.get('role_type', 'student')
    if active_role not in VALID_ROLES:
        return role_error('INVALID_ROLE', 'Invalid role', status.HTTP_400_BAD_REQUEST)

    if fixed_test_login:
        user = ensure_fixed_test_account(mobile)
    else:
        user = UserAccount.objects.filter(mobile=mobile).first()
        if user is None:
            # Student and parent accounts can be self-created after SMS
            # verification.  Teacher/admin accounts still require an
            # existing business grant and cannot be created from login.
            if active_role not in ('student', 'parent'):
                return role_error(
                    'ROLE_NOT_GRANTED', 'Role is not granted', status.HTTP_403_FORBIDDEN
                )
            user, _ = get_or_create_user(mobile, initial_role=active_role)
        else:
            if not has_user_role(user, active_role):
                return role_error(
                    'ROLE_NOT_GRANTED', 'Role is not granted', status.HTTP_403_FORBIDDEN
                )
            user, _ = get_or_create_user(mobile, initial_role=active_role)

    tokens = generate_tokens(user, active_role)

    return Response({
        'code': 0,
        'message': '登录成功',
        'data': {
            **tokens,
            'user': serialize_user_session(user, active_role),
        },
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wechat_web_binding_session(request):
    """Let an authenticated mini-program account bind an OAuth web session."""
    if 'mobile' in request.data:
        return binding_error('BINDING_MOBILE_NOT_ALLOWED')
    serializer = WebBindingSessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        binding = bind_web_identity_from_miniprogram(
            serializer.validated_data['web_session_id'], request.user
        )
    except WebBindingError:
        return binding_error('BINDING_SESSION_INVALID')
    return Response({
        'code': 0,
        'message': '绑定已确认',
        'data': {'bound': binding.bound},
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def wechat_web_binding_status(request):
    """Expose the opaque binding ticket only to its original H5 browser."""
    web_session_id = request.query_params.get('web_session_id', '')
    try:
        binding = get_web_binding_status(
            web_session_id, browser_session_id(request)
        )
    except WebBindingError:
        return binding_error('BINDING_SESSION_INVALID')
    return Response({
        'code': 0,
        'message': 'success',
        'data': {'bound': binding.bound, 'ticket': binding.ticket},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def wechat_web_binding_complete(request):
    """Consume a one-time, browser-bound ticket and return the normal session."""
    if 'mobile' in request.data:
        return binding_error('BINDING_MOBILE_NOT_ALLOWED')
    serializer = WebBindingCompleteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user, tokens = complete_web_binding(
            serializer.validated_data['ticket'],
            browser_session_id(request),
            serializer.validated_data.get('requested_role'),
        )
    except WebBindingError:
        return binding_error('BINDING_TICKET_INVALID')
    active_role = serializer.validated_data.get('requested_role')
    if active_role is None:
        active_role = RefreshToken(tokens['refresh_token'])['active_role']
    return Response({
        'code': 0,
        'message': '登录成功',
        'data': {
            **tokens,
            'user': serialize_user_session(
                user, active_role
            ),
        },
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """AUTH-02: Logout (client-side token discard)."""
    return Response({'code': 0, 'message': '已退出登录', 'data': None, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """AUTH-03: Refresh access token."""
    serializer = RefreshTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    refresh_token = serializer.validated_data['refresh_token']
    try:
        token = RefreshToken(refresh_token)
        user = UserAccount.objects.get(pk=token['user_id'])
        active_role = token['active_role'] if 'active_role' in token else user.role_type
        if active_role not in VALID_ROLES or not has_user_role(user, active_role):
            return role_error(
                'ROLE_NOT_GRANTED', 'Role is not granted', status.HTTP_403_FORBIDDEN
            )
        token['active_role'] = active_role
        new_access = str(token.access_token)
        return Response({
            'code': 0,
            'message': '刷新成功',
            'data': {'access_token': new_access},
            'trace_id': make_trace_id(),
        })
    except (TokenError, KeyError, UserAccount.DoesNotExist, ValueError):
        return Response({
            'code': 4001, 'message': '无效的刷新令牌', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_verify_code(request):
    """AUTH-04: Send SMS verification code."""
    mobile = request.data.get('mobile')
    scene = request.data.get('scene', 'login')  # 'login' or 'register'

    if not mobile:
        return Response({
            'code': 4001, 'message': '手机号不能为空', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    # 检查手机号格式
    if not mobile.isdigit() or len(mobile) != 11:
        return Response({
            'code': 4002, 'message': '手机号格式不正确', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    code = generate_verify_code(mobile)

    # 发送短信
    result = send_sms_code(mobile, code, scene)

    if result.get('success'):
        return Response({
            'code': 0, 'message': '验证码已发送', 'data': None, 'trace_id': make_trace_id()
        })
    else:
        return Response({
            'code': 5001,
            'message': f'验证码发送失败: {result.get("message", "未知错误")}',
            'data': None,
            'trace_id': make_trace_id(),
        }, status=500)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_me(request):
    """AUTH-06: Get or update current user profile.

    GET  — 返回当前用户资料
    PUT/PATCH — 更新 display_name、grade_level、avatar_url
    """
    if request.method == 'GET':
        active_role = get_request_role(request) or request.user.role_type
        return Response({
            'code': 0, 'message': 'success',
            'data': serialize_user_session(request.user, active_role),
            'trace_id': make_trace_id(),
        })

    # PUT / PATCH — 更新资料
    serializer = ProfileUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    user = request.user
    for field, value in serializer.validated_data.items():
        setattr(user, field, value)
    user.save(update_fields=serializer.validated_data.keys())

    return Response({
        'code': 0, 'message': '更新成功',
        'data': serialize_user_session(
            user, get_request_role(request) or request.user.role_type
        ),
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_role(request):
    """Issue a new independent session for another granted account role."""
    active_role = request.data.get('role')
    if active_role not in VALID_ROLES:
        return role_error('INVALID_ROLE', 'Invalid role', status.HTTP_400_BAD_REQUEST)
    if not has_user_role(request.user, active_role):
        return role_error(
            'ROLE_NOT_GRANTED', 'Role is not granted', status.HTTP_403_FORBIDDEN
        )

    tokens = generate_tokens(request.user, active_role)
    return Response({
        'code': 0,
        'message': 'Role switched',
        'data': {
            **tokens,
            'user': serialize_user_session(request.user, active_role),
        },
        'trace_id': make_trace_id(),
    })
