import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, ProfileSerializer, RefreshTokenSerializer
from .services import (
    verify_code, get_or_create_user, generate_tokens,
    generate_verify_code, send_sms_code,
)


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """AUTH-01: Login with mobile + verification code."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mobile = serializer.validated_data['mobile']
    code = serializer.validated_data['verify_code']

    if not verify_code(mobile, code):
        return Response({
            'code': 4001, 'message': '验证码错误或已过期', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    # Use role_type from request data for new user creation (defaults to 'student')
    role_type = request.data.get('role_type', 'student')
    user = get_or_create_user(mobile, role_type=role_type)
    tokens = generate_tokens(user)

    return Response({
        'code': 0,
        'message': '登录成功',
        'data': {
            **tokens,
            'user': ProfileSerializer(user).data,
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
        new_access = str(token.access_token)
        return Response({
            'code': 0,
            'message': '刷新成功',
            'data': {'access_token': new_access},
            'trace_id': make_trace_id(),
        })
    except Exception:
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_me(request):
    """AUTH-06: Get current user profile."""
    return Response({
        'code': 0, 'message': 'success',
        'data': ProfileSerializer(request.user).data,
        'trace_id': make_trace_id(),
    })
