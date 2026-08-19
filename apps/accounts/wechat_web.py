"""Secure server-side boundary for WeChat web OAuth login."""

from dataclasses import dataclass
import secrets
from typing import Any

import httpx
from django.conf import settings
from django.core.cache import cache


WEB_LOGIN_TTL_SECONDS = 300
WECHAT_WEB_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"


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
    requested_role: str
    browser_session_id: str


@dataclass(frozen=True)
class WebIdentity:
    """The standard identity returned by a WeChat web OAuth exchange."""

    openid: str
    unionid: str


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
