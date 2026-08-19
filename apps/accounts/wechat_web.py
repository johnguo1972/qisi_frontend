"""Secure server-side boundary for WeChat web OAuth login."""

from dataclasses import dataclass
from datetime import timedelta
import secrets
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import UserAccount, WechatWebIdentity
from .roles import VALID_ROLES
from .services import RoleNotGranted, login_with_trusted_mobile as _trusted_mobile_login


WEB_LOGIN_TTL_SECONDS = 300
WECHAT_WEB_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_WEB_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/qrconnect"


class WebLoginStateError(Exception):
    """Raised when a web OAuth state is invalid, expired, or already used."""


class WebAuthorizationError(Exception):
    """Raised when WeChat cannot produce a trusted web authorization."""


class WebConfigurationError(Exception):
    """Raised when the required WeChat web OAuth settings are unavailable."""


class WebBindingError(Exception):
    """Raised when a web identity binding or its ticket is invalid."""


@dataclass(frozen=True)
class WebLoginState:
    value: str
    expires_in: int
    requested_role: str
    browser_session_id: str


@dataclass(frozen=True)
class WebIdentity:
    """The standard identity returned by a WeChat web OAuth exchange."""

    openid: str
    unionid: str


@dataclass(frozen=True)
class WebBindingSession:
    """A browser-bound, server-side web identity waiting for MP confirmation."""

    value: str
    expires_in: int
    requested_role: str
    browser_session_id: str


@dataclass(frozen=True)
class WebBindingStatus:
    bound: bool
    ticket: str | None = None


def create_web_login_state(
    requested_role: str, browser_session_id: str
) -> WebLoginState:
    """Create a short-lived, one-time state bound to its initiating browser."""
    if not isinstance(requested_role, str) or not isinstance(browser_session_id, str):
        raise WebLoginStateError("state_invalid")
    if not requested_role or not browser_session_id:
        raise WebLoginStateError("state_invalid")

    value = secrets.token_urlsafe(32)
    payload = {
        "requested_role": requested_role,
        "browser_session_id": browser_session_id,
    }
    try:
        stored = cache.set(_state_key(value), payload, timeout=WEB_LOGIN_TTL_SECONDS)
    except Exception:
        raise WebLoginStateError("state_cache_failed") from None
    if stored is False:
        raise WebLoginStateError("state_cache_failed")
    return WebLoginState(
        value=value,
        expires_in=WEB_LOGIN_TTL_SECONDS,
        requested_role=requested_role,
        browser_session_id=browser_session_id,
    )


def consume_web_login_state(
    value: str, browser_session_id: str
) -> WebLoginState:
    """Consume a state once, then verify it belongs to the requesting browser."""
    if not isinstance(value, str) or not isinstance(browser_session_id, str):
        raise WebLoginStateError("state_invalid_or_expired")
    payload = _consume_state_payload(value)
    requested_role = payload.get("requested_role")
    stored_browser_session_id = payload.get("browser_session_id")
    if (
        not isinstance(requested_role, str)
        or not requested_role
        or not isinstance(stored_browser_session_id, str)
        or not stored_browser_session_id
        or not secrets.compare_digest(stored_browser_session_id, browser_session_id)
    ):
        raise WebLoginStateError("state_invalid_or_expired")
    return WebLoginState(
        value=value,
        expires_in=WEB_LOGIN_TTL_SECONDS,
        requested_role=requested_role,
        browser_session_id=stored_browser_session_id,
    )


def exchange_web_identity(
    code: str, *, http_client: httpx.Client | Any | None = None
) -> WebIdentity:
    """Exchange an OAuth code for the standard Web WeChat identity fields."""
    if not isinstance(code, str) or not code:
        raise WebAuthorizationError("wechat_web_authorization_failed")
    appid, app_secret = _get_wechat_web_configuration()
    owns_client = http_client is None
    client = http_client or httpx.Client()
    try:
        token_payload = _get_json(
            client,
            WECHAT_WEB_TOKEN_URL,
            {
                "appid": appid,
                "secret": app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
    finally:
        if owns_client:
            client.close()

    access_token = token_payload.get("access_token")
    openid = token_payload.get("openid")
    unionid = token_payload.get("unionid", "")
    if (
        not isinstance(access_token, str)
        or not access_token
        or not isinstance(openid, str)
        or not openid
        or not isinstance(unionid, str)
    ):
        raise WebAuthorizationError("wechat_web_authorization_failed")
    return WebIdentity(openid=openid, unionid=unionid)


def build_web_authorization_url(state: str) -> str:
    """Build the standard QR OAuth URL from server-only configuration."""
    if not isinstance(state, str) or not state:
        raise WebLoginStateError("state_invalid")
    appid, _ = _get_wechat_web_configuration()
    redirect_uri = getattr(settings, "WECHAT_WEB_REDIRECT_URI", "")
    parsed_redirect = urlsplit(redirect_uri) if isinstance(redirect_uri, str) else None
    if (
        not parsed_redirect
        or parsed_redirect.scheme != "https"
        or not parsed_redirect.netloc
    ):
        raise WebConfigurationError("wechat_web_not_configured")
    query = urlencode(
        {
            "appid": appid,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_login",
            "state": state,
        }
    )
    return f"{WECHAT_WEB_AUTHORIZE_URL}?{query}#wechat_redirect"


def create_web_binding_session(
    identity: WebIdentity,
    requested_role: str,
    browser_session_id: str,
    *,
    session_id: str | None = None,
) -> WebBindingSession:
    """Store a verified web identity for binding by the original browser only."""
    if (
        not isinstance(identity, WebIdentity)
        or not isinstance(identity.openid, str)
        or not identity.openid
        or not isinstance(identity.unionid, str)
        or requested_role not in VALID_ROLES
        or not isinstance(browser_session_id, str)
        or not browser_session_id
    ):
        raise WebBindingError("binding_session_invalid")

    appid, _ = _get_wechat_web_configuration()
    if session_id is not None and (not isinstance(session_id, str) or not session_id):
        raise WebBindingError("binding_session_invalid")
    value = session_id or secrets.token_urlsafe(32)
    payload = {
        "appid": appid,
        "openid": identity.openid,
        "unionid": identity.unionid,
        "requested_role": requested_role,
        "browser_session_id": browser_session_id,
        "expires_at": (timezone.now() + timedelta(seconds=WEB_LOGIN_TTL_SECONDS)).timestamp(),
    }
    _set_binding_cache(_binding_session_key(value), payload)
    return WebBindingSession(
        value=value,
        expires_in=WEB_LOGIN_TTL_SECONDS,
        requested_role=requested_role,
        browser_session_id=browser_session_id,
    )


@transaction.atomic
def prepare_web_login_session(
    identity: WebIdentity,
    requested_role: str,
    browser_session_id: str,
    *,
    session_id: str,
) -> WebBindingStatus:
    """Create the browser-bound H5 session and complete known identities only.

    A standard web OAuth response proves the web identity, not a trusted mobile.
    Unknown identities therefore remain pending for the mini-program binding flow.
    """
    session = create_web_binding_session(
        identity,
        requested_role,
        browser_session_id,
        session_id=session_id,
    )
    appid, _ = _get_wechat_web_configuration()
    known_identity = WechatWebIdentity.objects.select_for_update().filter(
        appid=appid, openid=identity.openid
    ).select_related("user").first()
    if known_identity is None:
        return WebBindingStatus(bound=False)
    if known_identity.unionid and identity.unionid and known_identity.unionid != identity.unionid:
        raise WebBindingError("binding_identity_conflict")
    known_identity.last_login_at = timezone.now()
    known_identity.save(update_fields=["last_login_at"])
    return _mark_binding_session_bound(session.value, known_identity.user)


@transaction.atomic
def bind_web_identity_from_miniprogram(
    web_session_id: str, authenticated_user: UserAccount
) -> WebBindingStatus:
    """Bind an OAuth web identity using only the authenticated MP account.

    The phone number is deliberately read from the persisted authenticated
    account and never accepted as a function argument or browser payload.
    """
    session = _get_binding_session(web_session_id)
    if not isinstance(authenticated_user, UserAccount) or not authenticated_user.pk:
        raise WebBindingError("binding_authentication_invalid")
    try:
        user = UserAccount.objects.select_for_update().get(pk=authenticated_user.pk)
    except UserAccount.DoesNotExist:
        raise WebBindingError("binding_authentication_invalid") from None
    if not isinstance(user.mobile, str) or not user.mobile:
        raise WebBindingError("binding_trusted_mobile_missing")

    appid = session["appid"]
    openid = session["openid"]
    unionid = session["unionid"]
    identity = WechatWebIdentity.objects.select_for_update().filter(
        appid=appid, openid=openid
    ).first()
    if identity is not None and identity.user_id != user.id:
        raise WebBindingError("binding_identity_conflict")
    if identity is not None and identity.user.mobile != user.mobile:
        raise WebBindingError("binding_mobile_conflict")
    if unionid:
        union_conflict = WechatWebIdentity.objects.select_for_update().filter(
            appid=appid, unionid=unionid
        ).exclude(user_id=user.id)
        if union_conflict.exists():
            raise WebBindingError("binding_identity_conflict")
    try:
        if identity is None:
            identity = WechatWebIdentity.objects.create(
                user=user,
                appid=appid,
                openid=openid,
                unionid=unionid,
                last_login_at=timezone.now(),
            )
        else:
            if identity.unionid and unionid and identity.unionid != unionid:
                raise WebBindingError("binding_identity_conflict")
            identity.unionid = identity.unionid or unionid
            identity.last_login_at = timezone.now()
            identity.save(update_fields=["unionid", "last_login_at"])
    except IntegrityError:
        raise WebBindingError("binding_identity_conflict") from None

    return _mark_binding_session_bound(web_session_id, user)


def _mark_binding_session_bound(
    web_session_id: str, user: UserAccount
) -> WebBindingStatus:
    """Create the normal one-time completion ticket for a verified account."""
    session = _get_binding_session(web_session_id)
    ticket = secrets.token_urlsafe(32)
    ticket_payload = {
        "user_id": str(user.id),
        "requested_role": session["requested_role"],
        "browser_session_id": session["browser_session_id"],
        "web_session_id": web_session_id,
        "expires_at": session["expires_at"],
    }
    _set_binding_cache(_binding_ticket_key(ticket), ticket_payload)
    session["ticket"] = ticket
    session["bound_user_id"] = str(user.id)
    _set_binding_cache(_binding_session_key(web_session_id), session)
    return WebBindingStatus(bound=True, ticket=ticket)


def get_web_binding_status(
    web_session_id: str, browser_session_id: str
) -> WebBindingStatus:
    """Return only the original browser's opaque, still-valid completion ticket."""
    session = _get_binding_session(web_session_id)
    _require_browser_session(session, browser_session_id)
    ticket = session.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        return WebBindingStatus(bound=False)
    try:
        ticket_payload = cache.get(_binding_ticket_key(ticket))
    except Exception:
        raise WebBindingError("binding_cache_failed") from None
    if not isinstance(ticket_payload, dict):
        return WebBindingStatus(bound=False)
    return WebBindingStatus(bound=True, ticket=ticket)


def complete_web_binding(
    ticket: str, browser_session_id: str, requested_role: str | None = None
) -> tuple[UserAccount, dict]:
    """Consume a browser-bound completion ticket and issue the normal JWT pair."""
    payload = _consume_binding_ticket(ticket)
    stored_role = payload.get("requested_role")
    if not isinstance(stored_role, str) or stored_role not in VALID_ROLES:
        raise WebBindingError("binding_role_conflict")
    if requested_role is None:
        requested_role = stored_role
    if (
        not isinstance(requested_role, str)
        or requested_role not in VALID_ROLES
        or not secrets.compare_digest(stored_role, requested_role)
    ):
        raise WebBindingError("binding_role_conflict")
    _require_browser_session(payload, browser_session_id)
    user_id = payload.get("user_id")
    try:
        user = UserAccount.objects.get(pk=user_id)
    except (UserAccount.DoesNotExist, TypeError, ValueError):
        raise WebBindingError("binding_user_invalid") from None
    try:
        trusted_user, tokens = _trusted_mobile_login(user.mobile, requested_role)
    except (RoleNotGranted, ValueError):
        raise WebBindingError("binding_role_conflict") from None
    if trusted_user.id != user.id:
        raise WebBindingError("binding_mobile_conflict")
    return trusted_user, tokens


def login_with_trusted_mobile(mobile: str, requested_role: str) -> tuple[UserAccount, dict]:
    """Expose the common trusted-mobile login policy to web binding callers."""
    try:
        return _trusted_mobile_login(mobile, requested_role)
    except (RoleNotGranted, ValueError):
        raise WebBindingError("binding_role_conflict") from None


def _consume_state_payload(value: str) -> dict[str, Any]:
    key = _state_key(value)
    try:
        payload = cache.get(key)
        deleted = cache.delete(key)
    except Exception:
        raise WebLoginStateError("state_cache_failed") from None
    if deleted is False:
        raise WebLoginStateError("state_cache_failed")
    if not isinstance(payload, dict):
        raise WebLoginStateError("state_invalid_or_expired")
    return payload


def _get_wechat_web_configuration() -> tuple[str, str]:
    values = (
        getattr(settings, "WECHAT_WEB_APP_ID", ""),
        getattr(settings, "WECHAT_WEB_APP_SECRET", ""),
    )
    if not all(isinstance(value, str) and value for value in values):
        raise WebConfigurationError("wechat_web_not_configured")
    return values


def _get_json(client: Any, url: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        response = client.get(url, params=params, timeout=10.0)
        payload = response.json()
    except (httpx.HTTPError, TypeError, ValueError):
        raise WebAuthorizationError("wechat_web_authorization_failed") from None
    if not isinstance(payload, dict):
        raise WebAuthorizationError("wechat_web_authorization_failed")
    return payload


def _state_key(value: str) -> str:
    return f"wechat_web:state:{value}"


def _binding_session_key(value: str) -> str:
    return f"wechat_web:binding_session:{value}"


def _binding_ticket_key(value: str) -> str:
    return f"wechat_web:binding_ticket:{value}"


def _set_binding_cache(key: str, payload: dict[str, Any]) -> None:
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        raise WebBindingError("binding_cache_failed")
    timeout = int(expires_at - timezone.now().timestamp())
    if timeout <= 0:
        raise WebBindingError("binding_session_invalid")
    try:
        stored = cache.set(key, payload, timeout=timeout)
    except Exception:
        raise WebBindingError("binding_cache_failed") from None
    if stored is False:
        raise WebBindingError("binding_cache_failed")


def _get_binding_session(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise WebBindingError("binding_session_invalid")
    try:
        payload = cache.get(_binding_session_key(value))
    except Exception:
        raise WebBindingError("binding_cache_failed") from None
    if not isinstance(payload, dict) or any(
        not isinstance(payload.get(field), str) or not payload.get(field)
        for field in ("appid", "openid", "requested_role", "browser_session_id")
    ) or not isinstance(payload.get("unionid"), str):
        raise WebBindingError("binding_session_invalid")
    expires_at = payload.get("expires_at")
    if (
        not isinstance(expires_at, (int, float))
        or expires_at <= timezone.now().timestamp()
    ):
        raise WebBindingError("binding_session_invalid")
    if payload["requested_role"] not in VALID_ROLES:
        raise WebBindingError("binding_session_invalid")
    return dict(payload)


def _consume_binding_ticket(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise WebBindingError("binding_ticket_invalid")
    key = _binding_ticket_key(value)
    try:
        payload = cache.get(key)
        deleted = cache.delete(key)
    except Exception:
        raise WebBindingError("binding_cache_failed") from None
    if deleted is False:
        raise WebBindingError("binding_cache_failed")
    if not isinstance(payload, dict):
        raise WebBindingError("binding_ticket_invalid")
    return payload


def _require_browser_session(payload: dict[str, Any], browser_session_id: str) -> None:
    expected = payload.get("browser_session_id")
    if (
        not isinstance(browser_session_id, str)
        or not browser_session_id
        or not isinstance(expected, str)
        or not expected
        or not secrets.compare_digest(expected, browser_session_id)
    ):
        raise WebBindingError("binding_browser_mismatch")
