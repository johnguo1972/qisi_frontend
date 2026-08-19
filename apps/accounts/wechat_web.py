"""Secure server-side boundary for WeChat web OAuth login."""

from dataclasses import asdict, dataclass
import secrets
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache


WEB_LOGIN_TTL_SECONDS = 300
WECHAT_WEB_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
WECHAT_WEB_PROFILE_URL = "https://api.weixin.qq.com/sns/userinfo"


class WebLoginStateError(Exception):
    """Raised when a web OAuth state is invalid, expired, or already used."""


class WebAuthorizationError(Exception):
    """Raised when WeChat cannot produce a trusted web authorization."""


class WebConfigurationError(Exception):
    """Raised when the required WeChat web OAuth settings are unavailable."""


@dataclass(frozen=True)
class WebLoginState:
    value: str
    expires_in: int
    requested_role: str = ""
    redirect_path: str = ""


@dataclass(frozen=True)
class WebAuthorization:
    requested_role: str
    redirect_path: str
    appid: str
    openid: str
    unionid: str
    mobile: str
    phone_authorization_confirmed: bool


def create_web_login_state(*, requested_role: str, redirect_path: str) -> WebLoginState:
    """Create a short-lived, one-time state value for a web OAuth redirect."""
    value = secrets.token_urlsafe(32)
    state = WebLoginState(
        value=value,
        expires_in=WEB_LOGIN_TTL_SECONDS,
        requested_role=requested_role,
        redirect_path=redirect_path,
    )
    cache.set(
        _state_key(value),
        {
            "requested_role": requested_role,
            "redirect_path": redirect_path,
        },
        timeout=WEB_LOGIN_TTL_SECONDS,
    )
    return state


def consume_web_login_state(value: str) -> WebLoginState:
    """Atomically claim a state value and return its server-created payload."""
    payload = _consume_cached_payload(_state_key(value), "state_invalid_or_expired")
    requested_role = payload.get("requested_role")
    redirect_path = payload.get("redirect_path")
    if not isinstance(requested_role, str) or not isinstance(redirect_path, str):
        raise WebLoginStateError("state_invalid_or_expired")
    return WebLoginState(
        value=value,
        expires_in=WEB_LOGIN_TTL_SECONDS,
        requested_role=requested_role,
        redirect_path=redirect_path,
    )


def consume_web_callback(
    code: str,
    state: str,
    *,
    http_client: httpx.Client | Any | None = None,
) -> WebAuthorization:
    """Exchange a callback code and accept only a WeChat-confirmed phone number."""
    web_state = consume_web_login_state(state)
    appid, app_secret, redirect_uri = _get_wechat_web_configuration()
    if not isinstance(code, str) or not code:
        raise WebAuthorizationError("wechat_web_authorization_failed")

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
                "redirect_uri": redirect_uri,
            },
        )
        access_token = token_payload.get("access_token")
        openid = token_payload.get("openid")
        if not isinstance(access_token, str) or not isinstance(openid, str) or not openid:
            raise WebAuthorizationError("wechat_web_authorization_failed")

        profile_payload = _get_json(
            client,
            WECHAT_WEB_PROFILE_URL,
            {"access_token": access_token, "openid": openid},
        )
    finally:
        if owns_client:
            client.close()

    profile_openid = profile_payload.get("openid", openid)
    mobile = profile_payload.get("phone_number")
    confirmed = profile_payload.get("phone_authorization_confirmed")
    if (
        profile_openid != openid
        or not isinstance(mobile, str)
        or not mobile
        or confirmed is not True
    ):
        raise WebAuthorizationError("phone_authorization_required")

    unionid = profile_payload.get("unionid", "")
    if not isinstance(unionid, str):
        unionid = ""
    return WebAuthorization(
        requested_role=web_state.requested_role,
        redirect_path=web_state.redirect_path,
        appid=appid,
        openid=openid,
        unionid=unionid,
        mobile=mobile,
        phone_authorization_confirmed=True,
    )


def issue_login_ticket(authorization: WebAuthorization) -> str:
    """Store a trusted server authorization behind a short-lived one-time ticket."""
    if (
        authorization.phone_authorization_confirmed is not True
        or not isinstance(authorization.mobile, str)
        or not authorization.mobile
    ):
        raise WebAuthorizationError("phone_authorization_required")

    ticket = secrets.token_urlsafe(32)
    cache.set(
        _ticket_key(ticket),
        asdict(authorization),
        timeout=WEB_LOGIN_TTL_SECONDS,
    )
    return ticket


def consume_login_ticket(ticket: str) -> WebAuthorization:
    """Consume a login ticket exactly once and reconstruct its authorization."""
    payload = _consume_cached_payload(_ticket_key(ticket), "ticket_invalid_or_expired")
    try:
        authorization = WebAuthorization(**payload)
    except (TypeError, ValueError):
        raise WebAuthorizationError("ticket_invalid_or_expired") from None
    if (
        authorization.phone_authorization_confirmed is not True
        or not isinstance(authorization.mobile, str)
        or not authorization.mobile
    ):
        raise WebAuthorizationError("ticket_invalid_or_expired")
    return authorization


def _get_wechat_web_configuration() -> tuple[str, str, str]:
    values = (
        getattr(settings, "WECHAT_WEB_APP_ID", ""),
        getattr(settings, "WECHAT_WEB_APP_SECRET", ""),
        getattr(settings, "WECHAT_WEB_REDIRECT_URI", ""),
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


def _consume_cached_payload(key: str, error_message: str) -> dict[str, Any]:
    claim_key = f"{key}:consumed"
    if not cache.add(claim_key, "1", timeout=WEB_LOGIN_TTL_SECONDS):
        _raise_cache_error(error_message)
    try:
        payload = cache.get(key)
    finally:
        cache.delete(key)
    if not isinstance(payload, dict):
        _raise_cache_error(error_message)
    return payload


def _raise_cache_error(error_message: str) -> None:
    if error_message == "state_invalid_or_expired":
        raise WebLoginStateError(error_message)
    raise WebAuthorizationError(error_message)


def _state_key(value: str) -> str:
    return f"wechat_web:state:{value}"


def _ticket_key(value: str) -> str:
    return f"wechat_web:ticket:{value}"
