"""Authentication services: SMS code, JWT token generation, verification."""
import logging
import random

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserAccount
from .roles import grant_user_role, has_user_role

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


class RoleNotGranted(Exception):
    """Raised when a session role has no active grant."""

    def __init__(self, role: str):
        self.role = role
        super().__init__(f"role not granted: {role}")


@transaction.atomic
def get_or_create_user(
    mobile: str, initial_role: str = 'student'
) -> tuple[UserAccount, bool]:
    """Create a new account with one safe initial grant; never change an existing account's roles."""
    user = UserAccount.objects.filter(mobile=mobile).first()
    if user is None:
        display_name = f"User{mobile[-4:]}"
        user = UserAccount.objects.create(
            mobile=mobile,
            role_type=initial_role,
            display_name=display_name,
            status='active',
            password='',
        )
        grant_user_role(user, initial_role)
        created = True
    else:
        created = False

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    return user, created


def generate_tokens(user: UserAccount, active_role: str) -> dict:
    """Generate a JWT pair bound to one currently authorized role."""
    try:
        granted = has_user_role(user, active_role)
    except ValueError as exc:
        raise RoleNotGranted(active_role) from exc
    if not granted:
        raise RoleNotGranted(active_role)

    refresh = RefreshToken.for_user(user)
    refresh['active_role'] = active_role
    return {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
    }
