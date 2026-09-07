"""Direct Mini Program login using WeChat's trusted phone authorization."""

from django.db import IntegrityError, transaction

from .models import UserAccount, WechatIdentity
from .roles import VALID_ROLES
from .services import (
    RoleNotGranted,
    generate_tokens,
    login_with_trusted_mobile,
)
from .wechat_device import (
    DeviceLoginError,
    MiniProgramIdentity,
    exchange_miniprogram_login_code,
    exchange_miniprogram_phone_code,
)


class MiniProgramLoginError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def login_with_miniprogram_phone(
    login_code: str, phone_code: str, requested_role: str
) -> tuple[UserAccount, dict]:
    """Exchange both one-time WeChat credentials and issue the normal JWT pair."""
    if requested_role not in VALID_ROLES:
        raise MiniProgramLoginError("INVALID_ROLE")
    try:
        identity = exchange_miniprogram_login_code(login_code)
        mobile = exchange_miniprogram_phone_code(phone_code)
    except DeviceLoginError as error:
        raise MiniProgramLoginError(error.code) from None

    try:
        return _link_identity_and_login(identity, mobile, requested_role)
    except RoleNotGranted:
        raise MiniProgramLoginError("ROLE_NOT_GRANTED") from None
    except (IntegrityError, ValueError):
        raise MiniProgramLoginError("WECHAT_IDENTITY_CONFLICT") from None


@transaction.atomic
def _link_identity_and_login(
    identity: MiniProgramIdentity, mobile: str, requested_role: str
) -> tuple[UserAccount, dict]:
    """Bind one MP identity to the phone account without overwriting identities."""
    existing_identity = (
        WechatIdentity.objects.select_for_update()
        .select_related("user")
        .filter(appid=identity.appid, openid=identity.openid)
        .first()
    )

    if existing_identity is not None:
        if (
            existing_identity.unionid
            and identity.unionid
            and existing_identity.unionid != identity.unionid
        ):
            raise ValueError("wechat identity conflict")
        if existing_identity.user.mobile != mobile:
            raise ValueError("wechat identity mobile conflict")
        user, _ = login_with_trusted_mobile(
            mobile,
            requested_role,
            issue_tokens=False,
            grant_source="wechat_mp",
        )
        if user.pk != existing_identity.user_id:
            raise ValueError("wechat identity mobile conflict")
    else:
        user, _ = login_with_trusted_mobile(
            mobile,
            requested_role,
            issue_tokens=False,
            grant_source="wechat_mp",
        )
        if WechatIdentity.objects.select_for_update().filter(user=user).exists():
            raise ValueError("user already has a different wechat identity")
        if (
            identity.unionid
            and WechatIdentity.objects.select_for_update()
            .filter(appid=identity.appid, unionid=identity.unionid)
            .exclude(user=user)
            .exists()
        ):
            raise ValueError("wechat unionid conflict")
        WechatIdentity.objects.create(
            user=user,
            appid=identity.appid,
            openid=identity.openid,
            unionid=identity.unionid,
        )

    return user, generate_tokens(user, requested_role)
