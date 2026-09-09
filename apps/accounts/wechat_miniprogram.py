"""Direct Mini Program login using WeChat's trusted phone authorization."""

import logging

from django.db import IntegrityError, transaction

from .models import UserAccount, WechatIdentity
from .roles import VALID_ROLES
from .services import (
    RoleNotGranted,
    generate_tokens,
    login_with_trusted_mobile,
    validate_active_role,
)
from .wechat_device import (
    DeviceLoginError,
    MiniProgramIdentity,
    exchange_miniprogram_login_code,
    exchange_miniprogram_phone_code,
)


logger = logging.getLogger(__name__)


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
    """Resolve the trusted phone first, then reconcile its MP identity.

    The phone returned by WeChat is the account key for direct login.  A user
    may have logged in with SMS before, or may have replaced their WeChat
    account since the previous binding.  In both cases the verified phone
    account remains the same and its MP identity can be updated atomically.
    """
    identity_by_openid = (
        WechatIdentity.objects.select_for_update()
        .select_related("user")
        .filter(appid=identity.appid, openid=identity.openid)
        .first()
    )
    identity_by_unionid = None
    if identity.unionid:
        identity_by_unionid = (
            WechatIdentity.objects.select_for_update()
            .select_related("user")
            .filter(appid=identity.appid, unionid=identity.unionid)
            .first()
        )

    identity_matches = [
        item
        for item in (identity_by_openid, identity_by_unionid)
        if item is not None
    ]
    identity_owner_ids = {item.user_id for item in identity_matches}
    if len(identity_owner_ids) > 1:
        # The same incoming identity points at two accounts in historical
        # data.  This is genuinely ambiguous and must be reviewed manually.
        raise ValueError("wechat identity points to multiple users")

    user = (
        UserAccount.objects.select_for_update()
        .filter(mobile=mobile)
        .first()
    )

    if user is None and identity_matches:
        # The WeChat identity is already authoritative, while the newly
        # returned phone is not registered in the platform.  Keep the user
        # account only when the trusted phone still matches it; otherwise the
        # identity and phone belong to different accounts and must not be
        # silently crossed.
        user = UserAccount.objects.select_for_update().get(
            pk=identity_matches[0].user_id
        )
        if user.mobile != mobile:
            raise ValueError("wechat identity mobile conflict")
        validate_active_role(user, requested_role)
        bound_identity = identity_matches[0]
        if (
            bound_identity.appid != identity.appid
            or bound_identity.openid != identity.openid
            or bound_identity.unionid != identity.unionid
        ):
            bound_identity.appid = identity.appid
            bound_identity.openid = identity.openid
            bound_identity.unionid = identity.unionid
            bound_identity.save(
                update_fields=["appid", "openid", "unionid", "updated_at"]
            )
        return user, generate_tokens(user, requested_role)

    if user is None:
        # This path creates only the roles allowed by the trusted-mobile
        # login policy (student and parent for a new account).
        user, _ = login_with_trusted_mobile(
            mobile,
            requested_role,
            issue_tokens=False,
            grant_source="wechat_mp",
        )
        user = UserAccount.objects.select_for_update().get(pk=user.pk)
    else:
        # Reuse the existing account's role rules (including the established
        # parent-login compatibility behavior) before changing its identity.
        user, _ = login_with_trusted_mobile(
            mobile,
            requested_role,
            issue_tokens=False,
            grant_source="wechat_mp",
        )
        user = UserAccount.objects.select_for_update().get(pk=user.pk)

    user_identity = (
        WechatIdentity.objects.select_for_update()
        .filter(user=user)
        .first()
    )
    foreign_identity = identity_matches[0] if identity_matches else None

    if foreign_identity is not None and foreign_identity.user_id != user.pk:
        # The verified phone identifies the destination account.  Move the
        # old binding to that account instead of blocking a legitimate login.
        # If the destination already has an older identity, replace it in the
        # same transaction so the one-identity-per-user invariant remains.
        if user_identity is not None and user_identity.pk != foreign_identity.pk:
            logger.info(
                "Replacing old WeChat identity for user=%s during phone login",
                user.pk,
            )
            user_identity.delete()
        foreign_identity.user = user
        foreign_identity.appid = identity.appid
        foreign_identity.openid = identity.openid
        foreign_identity.unionid = identity.unionid
        foreign_identity.save(
            update_fields=["user", "appid", "openid", "unionid", "updated_at"]
        )
    elif user_identity is not None:
        # The account exists and the incoming identity is new or has a new
        # openid under the same unionid.  Keep the account and refresh its
        # current binding.
        changed = (
            user_identity.appid != identity.appid
            or user_identity.openid != identity.openid
            or user_identity.unionid != identity.unionid
        )
        if changed:
            logger.info(
                "Updating WeChat identity for user=%s during phone login",
                user.pk,
            )
            user_identity.appid = identity.appid
            user_identity.openid = identity.openid
            user_identity.unionid = identity.unionid
            user_identity.save(
                update_fields=["appid", "openid", "unionid", "updated_at"]
            )
    else:
        WechatIdentity.objects.create(
            user=user,
            appid=identity.appid,
            openid=identity.openid,
            unionid=identity.unionid,
        )

    # The phone account is resolved before binding, so the selected role is
    # checked against that account and the returned token uses that account's
    # current role grants.
    validate_active_role(user, requested_role)
    return user, generate_tokens(user, requested_role)
