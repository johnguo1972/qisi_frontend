"""Authentication services: SMS code, JWT token generation, verification."""
import logging
import random

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.conf import settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserAccount, UserRole
from .roles import grant_user_role, has_user_role

logger = logging.getLogger(__name__)

TEST_ACCOUNT_ROLES = ("admin", "teacher", "parent", "student")


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


def is_fixed_test_account_code(mobile: str, code: str) -> bool:
    """Return whether an explicitly enabled fixed test credential was used."""
    return bool(
        settings.TEST_LOGIN_ENABLED
        and settings.TEST_LOGIN_PHONE
        and settings.TEST_LOGIN_CODE
        and mobile == settings.TEST_LOGIN_PHONE
        and code == settings.TEST_LOGIN_CODE
    )


@transaction.atomic
def ensure_fixed_test_account(mobile: str) -> UserAccount:
    """Create the configured test user and idempotently grant every app role."""
    user, _ = get_or_create_user(mobile, initial_role="student")
    for role in TEST_ACCOUNT_ROLES:
        grant_user_role(user, role)
    return user


class RoleNotGranted(Exception):
    """Raised when a session role has no active grant."""

    def __init__(self, role: str):
        self.role = role
        super().__init__(f"role not granted: {role}")


@transaction.atomic
def login_with_trusted_mobile(
    mobile: str, active_role: str, *, issue_tokens: bool = True
) -> tuple[UserAccount, dict]:
    """Create or sign in an account from a server-verified phone number.

    Callers must obtain ``mobile`` from a trusted server-side identity.  This
    function deliberately has no SMS dependency: it only applies the same
    first-role and existing-role rules as the verified mobile login flow.
    """
    if not isinstance(mobile, str) or not mobile:
        raise ValueError("trusted mobile is required")
    if active_role not in ("admin", "teacher", "parent", "student"):
        raise ValueError("invalid role")

    user = UserAccount.objects.filter(mobile=mobile).first()
    if user is None:
        if active_role not in ("student", "parent"):
            raise RoleNotGranted(active_role)
        user, _ = get_or_create_user(
            mobile, initial_role=active_role, grant_source="wechat_web"
        )
    else:
        if not has_user_role(user, active_role):
            raise RoleNotGranted(active_role)
        user, _ = get_or_create_user(
            mobile, initial_role=active_role, grant_source="wechat_web"
        )

    return user, generate_tokens(user, active_role) if issue_tokens else {}


@transaction.atomic
def ensure_parent_role_for_login(user: UserAccount) -> UserAccount:
    """Grant the first parent role after verified login, but never restore a revoke."""
    locked_user = UserAccount.objects.select_for_update().get(pk=user.pk)
    if locked_user.status != "active":
        raise RoleNotGranted("parent")

    grant = UserRole.objects.select_for_update().filter(
        user=locked_user, role="parent"
    ).first()
    if grant is not None:
        if grant.status != "active":
            raise RoleNotGranted("parent")
        return locked_user

    grant_user_role(locked_user, "parent", grant_source="self_login")
    return locked_user


@transaction.atomic
def get_or_create_user(
    mobile: str, initial_role: str = 'student', grant_source: str = 'business'
) -> tuple[UserAccount, bool]:
    """Create a new account with one safe initial grant; never change an existing account's roles."""
    user = UserAccount.objects.select_for_update().filter(mobile=mobile).first()
    if user is None:
        display_name = f"User{mobile[-4:]}"
        try:
            with transaction.atomic():
                user = UserAccount.objects.create(
                    mobile=mobile,
                    role_type=initial_role,
                    display_name=display_name,
                    status='active',
                    password='',
                )
                grant_user_role(user, initial_role, grant_source=grant_source)
            created = True
        except IntegrityError:
            user = UserAccount.objects.select_for_update().get(mobile=mobile)
            created = False
    else:
        created = False

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    return user, created


def generate_tokens(user: UserAccount, active_role: str) -> dict:
    """Generate a JWT pair bound to one currently authorized role."""
    if user.status != "active":
        raise RoleNotGranted(active_role)
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
