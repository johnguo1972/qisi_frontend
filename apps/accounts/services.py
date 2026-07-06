"""Authentication services: SMS code, JWT token generation, verification."""
import random
from datetime import datetime
import logging

from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserAccount

logger = logging.getLogger(__name__)


def generate_verify_code(mobile: str) -> str:
    """Generate and cache a 6-digit verification code."""
    code = f"{random.randint(100000, 999999)}"
    cache.set(f"sms_code:{mobile}", code, timeout=180)  # 3 min TTL (matches SMS template)
    return code


def send_sms_code(mobile: str, verify_code: str, scene: str = 'login') -> dict:
    """Send SMS verification code via Tencent Cloud SMS.

    Returns:
        dict with 'success' boolean and optional error message
    """
    from django.conf import settings
    from .sms_service import TencentSMSService

    # Dev mode 1: 环境变量明确开启
    if settings.SMS_DEV_MODE:
        logger.info(f"[DEV MODE] SMS code for {mobile}: {verify_code}")
        return {'success': True}

    # Dev mode 2: 未配置密钥
    if not settings.TENCENT_SMS_SECRET_ID or not settings.TENCENT_SMS_SECRET_KEY:
        logger.info(f"[DEV] SMS code for {mobile}: {verify_code}")
        return {'success': True}

    try:
        service = TencentSMSService()
        result = service.send_verify_code(mobile, verify_code, scene)
        # 余额不足等账户错误 → 自动退化为 dev 模式
        if not result.get('success'):
            error_code = result.get('code', '')
            if 'InsufficientBalance' in str(error_code):
                logger.warning(f"Tencent SMS balance insufficient, falling back to dev mode for {mobile}")
                return {'success': True}
        return result
    except Exception as e:
        logger.error(f"SMS send error: {e}")
        return {'success': False, 'message': str(e)}


def verify_code(mobile: str, code: str) -> bool:
    """Verify the SMS code."""
    cached = cache.get(f"sms_code:{mobile}")
    return cached == code


def get_or_create_user(mobile: str, role_type: str = 'student') -> UserAccount:
    """Get or create user by mobile, updating role_type on each login."""
    user, created = UserAccount.objects.get_or_create(
        mobile=mobile,
        defaults={
            'role_type': role_type,
            'display_name': f"User{mobile[-4:]}",
            'status': 'active',
        },
    )
    # Update role_type on each login (user selected a different role tab)
    if user.role_type != role_type:
        user.role_type = role_type
        user.save(update_fields=['role_type'])
    user.last_login = datetime.now()
    user.save(update_fields=['last_login'])
    return user


def generate_tokens(user: UserAccount) -> dict:
    """Generate JWT access and refresh tokens."""
    refresh = RefreshToken.for_user(user)
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }
