"""Redis-backed state machine for Mini Program QR device login."""

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import secrets
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import UserAccount, WechatIdentity
from .roles import VALID_ROLES
from .services import (
    RoleNotGranted,
    generate_tokens,
    login_with_trusted_mobile,
    validate_active_role,
)


DEVICE_LOGIN_TTL_SECONDS = 300
DEVICE_LOCK_TTL_SECONDS = 5
DEVICE_LOCK_WAIT_SECONDS = 0.25
WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"


class DeviceLoginError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DeviceLoginSession:
    value: str
    expires_in: int


@dataclass(frozen=True)
class DeviceScanResult:
    status: str
    phone_binding_token: str | None


@dataclass(frozen=True)
class MiniProgramIdentity:
    appid: str
    openid: str
    unionid: str


@dataclass(frozen=True)
class DeviceLoginStatus:
    status: str
    bound: bool
    ticket: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class _ConsumedTicket:
    payload: dict[str, Any]
    raw_value: Any | None
    restore_deadline: float


class _WechatTransportError(Exception):
    """Raised when WeChat cannot return one verified JSON response."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class _WechatHttpClient:
    """Minimal stdlib transport that never emits credential-bearing URLs to logs."""

    def __init__(self):
        self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def get_json(
        self, url: str, *, params: dict[str, str], timeout: float
    ) -> dict[str, Any]:
        return self._request_json("GET", url, params=params, json_body=None, timeout=timeout)

    def post_json(
        self,
        url: str,
        *,
        params: dict[str, str],
        json: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        return self._request_json("POST", url, params=params, json_body=json, timeout=timeout)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        json_body: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        query = urlencode(params)
        request_url = f"{url}?{query}" if query else url
        body = json.dumps(json_body).encode() if json_body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(request_url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status_code = response.getcode()
                if not isinstance(status_code, int) or not 200 <= status_code < 300:
                    raise _WechatTransportError
                raw_payload = response.read()
        except (HTTPError, URLError, OSError, ValueError) as error:
            raise _WechatTransportError from error
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise _WechatTransportError from None
        if not isinstance(payload, dict):
            raise _WechatTransportError
        return payload


def exchange_miniprogram_login_code(
    login_code: str, http_client: Any | None = None
) -> MiniProgramIdentity:
    """Exchange a one-time wx.login code for a server-verified MP identity."""
    error_code = "DEVICE_LOGIN_AUTHORIZATION_FAILED"
    if not isinstance(login_code, str) or not login_code:
        raise DeviceLoginError(error_code)
    appid, app_secret = _get_wechat_miniprogram_configuration(error_code)
    client = http_client or _WechatHttpClient()
    payload = _get_wechat_json(
        client,
        WECHAT_CODE2SESSION_URL,
        {
            "appid": appid,
            "secret": app_secret,
            "js_code": login_code,
            "grant_type": "authorization_code",
        },
        error_code,
    )

    openid = payload.get("openid")
    unionid = payload.get("unionid", "")
    if (
        not isinstance(openid, str)
        or not openid
        or not isinstance(unionid, str)
    ):
        raise DeviceLoginError(error_code)
    return MiniProgramIdentity(appid=appid, openid=openid, unionid=unionid)


def exchange_miniprogram_phone_code(
    phone_code: str, http_client: Any | None = None
) -> str:
    """Exchange a user-authorized MP phone code for WeChat's trusted mobile."""
    error_code = "DEVICE_PHONE_AUTHORIZATION_FAILED"
    if not isinstance(phone_code, str) or not phone_code:
        raise DeviceLoginError(error_code)
    appid, app_secret = _get_wechat_miniprogram_configuration(error_code)
    client = http_client or _WechatHttpClient()
    token_payload = _get_wechat_json(
        client,
        WECHAT_TOKEN_URL,
        {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": app_secret,
        },
        error_code,
    )
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise DeviceLoginError(error_code)
    phone_payload = _post_wechat_json(
        client,
        WECHAT_PHONE_URL,
        params={"access_token": access_token},
        json_body={"code": phone_code},
        error_code=error_code,
    )

    if not isinstance(phone_payload, dict):
        raise DeviceLoginError(error_code)
    phone_info = phone_payload.get("phone_info")
    mobile = phone_info.get("phoneNumber") if isinstance(phone_info, dict) else None
    if not isinstance(mobile, str) or not mobile:
        raise DeviceLoginError(error_code)
    return mobile


def create_device_login_session(
    requested_role: str, browser_session_id: str
) -> DeviceLoginSession:
    """Create the browser-bound session that starts one QR login attempt."""
    if (
        not isinstance(requested_role, str)
        or requested_role not in VALID_ROLES
        or not isinstance(browser_session_id, str)
        or not browser_session_id
    ):
        raise DeviceLoginError("DEVICE_SESSION_INVALID")

    value = secrets.token_urlsafe(32)
    expires_at = timezone.now().timestamp() + DEVICE_LOGIN_TTL_SECONDS
    _cache_set(
        _session_key(value),
        {
            "requested_role": requested_role,
            "browser_session_id": browser_session_id,
            "status": "pending",
            "expires_at": expires_at,
        },
        expires_at,
    )
    return DeviceLoginSession(value=value, expires_in=DEVICE_LOGIN_TTL_SECONDS)


def get_or_create_device_bridge(web_session_id: str, browser_session_id: str) -> str:
    """Return the one short QR scene code for this still-live browser session."""
    with _session_lock(web_session_id):
        session = _load_session(web_session_id)
        _require_browser(session, browser_session_id)
        bridge_code = session.get("bridge_code")
        if isinstance(bridge_code, str) and bridge_code:
            return bridge_code

        bridge_code = secrets.token_urlsafe(18)
        _cache_set(
            _bridge_key(bridge_code),
            {"web_session_id": web_session_id, "expires_at": session["expires_at"]},
            session["expires_at"],
        )
        session["bridge_code"] = bridge_code
        _save_session(web_session_id, session)
        return bridge_code


def confirm_device_identity(
    bridge_code: str, identity: MiniProgramIdentity
) -> DeviceScanResult:
    """Consume a QR bridge and either bind a known account or request phone auth.

    This step deliberately creates no JWT.  The original browser can only mint
    credentials after it consumes the resulting completion ticket.
    """
    _validate_identity(identity)
    web_session_id = _consume_bridge(bridge_code)
    with _session_lock(web_session_id):
        session = _load_session(web_session_id)
        if session["status"] != "pending":
            raise DeviceLoginError("DEVICE_BRIDGE_INVALID")

        known_identity = (
            WechatIdentity.objects.select_related("user")
            .filter(appid=identity.appid, openid=identity.openid)
            .first()
        )
        if known_identity is not None:
            if (
                known_identity.unionid
                and identity.unionid
                and not secrets.compare_digest(known_identity.unionid, identity.unionid)
            ):
                raise DeviceLoginError("DEVICE_IDENTITY_CONFLICT")
            _require_user_role(known_identity.user, session["requested_role"])
            _mark_session_bound(web_session_id, known_identity.user, session)
            return DeviceScanResult(status="login_confirmed", phone_binding_token=None)

        phone_binding_token = secrets.token_urlsafe(32)
        _cache_set(
            _phone_token_key(phone_binding_token),
            {
                "web_session_id": web_session_id,
                "appid": identity.appid,
                "openid": identity.openid,
                "unionid": identity.unionid,
                "expires_at": session["expires_at"],
            },
            session["expires_at"],
        )
        session["status"] = "phone_authorization_required"
        session["phone_binding_token"] = phone_binding_token
        _save_session(web_session_id, session)
        return DeviceScanResult(
            status="phone_authorization_required", phone_binding_token=phone_binding_token
        )


@transaction.atomic
def bind_device_identity_phone(phone_binding_token: str, mobile: str) -> None:
    """Bind a phone-authorized account to an otherwise unknown MP identity."""
    phone_payload = _consume_phone_token(phone_binding_token)
    web_session_id = phone_payload["web_session_id"]
    with _session_lock(web_session_id):
        session = _load_session(web_session_id)
        if (
            session["status"] != "phone_authorization_required"
            or not secrets.compare_digest(
                session.get("phone_binding_token", ""), phone_binding_token
            )
        ):
            raise DeviceLoginError("DEVICE_PHONE_TOKEN_INVALID")

        try:
            user, _ = login_with_trusted_mobile(
                mobile, session["requested_role"], issue_tokens=False
            )
        except (RoleNotGranted, ValueError):
            raise DeviceLoginError("DEVICE_ROLE_CONFLICT") from None

        user = UserAccount.objects.select_for_update().get(pk=user.pk)
        _bind_identity_to_user(phone_payload, user)
        _mark_session_bound(web_session_id, user, session)


def get_device_login_status(
    web_session_id: str, browser_session_id: str
) -> DeviceLoginStatus:
    """Return an opaque completion ticket to the initiating browser only."""
    session = _load_session(web_session_id)
    _require_browser(session, browser_session_id)
    ticket = session.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        return DeviceLoginStatus(status=session["status"], bound=False)
    ticket_payload = _cache_get(_ticket_key(ticket))
    if not isinstance(ticket_payload, dict) or _is_expired(ticket_payload):
        return DeviceLoginStatus(status=session["status"], bound=False)
    return DeviceLoginStatus(status=session["status"], bound=True, ticket=ticket)


def complete_device_login(
    ticket: str, browser_session_id: str, requested_role: str
) -> tuple[UserAccount, dict]:
    """Consume a browser-bound ticket before issuing the normal JWT pair."""
    with _ticket_lock(ticket):
        ticket_payload = _load_ticket(ticket)
        stored_role = ticket_payload.get("requested_role")
        if (
            not isinstance(requested_role, str)
            or requested_role not in VALID_ROLES
            or not isinstance(stored_role, str)
            or not secrets.compare_digest(stored_role, requested_role)
        ):
            raise DeviceLoginError("DEVICE_TICKET_INVALID")
        try:
            _require_browser(ticket_payload, browser_session_id)
            user = UserAccount.objects.get(pk=ticket_payload.get("user_id"))
        except (UserAccount.DoesNotExist, TypeError, ValueError, DeviceLoginError):
            raise DeviceLoginError("DEVICE_TICKET_INVALID") from None
        _require_user_role(user, requested_role)
        consumed_ticket = _consume_ticket_for_completion(ticket)
        try:
            return user, generate_tokens(user, requested_role)
        except RoleNotGranted:
            _restore_ticket(ticket, consumed_ticket)
            raise DeviceLoginError("DEVICE_ROLE_CONFLICT") from None


def _bind_identity_to_user(phone_payload: dict[str, Any], user: UserAccount) -> None:
    appid = phone_payload["appid"]
    openid = phone_payload["openid"]
    unionid = phone_payload["unionid"]
    existing = WechatIdentity.objects.select_for_update().filter(
        appid=appid, openid=openid
    ).first()
    if existing is not None:
        raise DeviceLoginError("DEVICE_IDENTITY_CONFLICT")
    if WechatIdentity.objects.select_for_update().filter(user=user).exists():
        raise DeviceLoginError("DEVICE_IDENTITY_CONFLICT")
    if unionid and WechatIdentity.objects.select_for_update().filter(
        appid=appid, unionid=unionid
    ).exclude(user=user).exists():
        raise DeviceLoginError("DEVICE_IDENTITY_CONFLICT")
    try:
        WechatIdentity.objects.create(
            user=user, appid=appid, openid=openid, unionid=unionid
        )
    except IntegrityError:
        raise DeviceLoginError("DEVICE_IDENTITY_CONFLICT") from None


def _mark_session_bound(
    web_session_id: str, user: UserAccount, session: dict[str, Any]
) -> None:
    ticket = secrets.token_urlsafe(32)
    _cache_set(
        _ticket_key(ticket),
        {
            "user_id": str(user.id),
            "requested_role": session["requested_role"],
            "browser_session_id": session["browser_session_id"],
            "web_session_id": web_session_id,
            "expires_at": session["expires_at"],
        },
        session["expires_at"],
    )
    session["status"] = "login_confirmed"
    session["ticket"] = ticket
    session["bound_user_id"] = str(user.id)
    session.pop("phone_binding_token", None)
    _save_session(web_session_id, session)


def _load_session(value: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    payload = _cache_get(_session_key(value))
    if not isinstance(payload, dict) or _is_expired(payload):
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    required = ("requested_role", "browser_session_id", "status")
    if any(not isinstance(payload.get(field), str) or not payload[field] for field in required):
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    if payload["requested_role"] not in VALID_ROLES:
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    return dict(payload)


def _save_session(value: str, payload: dict[str, Any]) -> None:
    _cache_set(_session_key(value), payload, payload["expires_at"])


def _consume_bridge(bridge_code: str) -> str:
    payload = _consume(_bridge_key(bridge_code), "DEVICE_BRIDGE_INVALID")
    web_session_id = payload.get("web_session_id")
    if not isinstance(web_session_id, str) or not web_session_id:
        raise DeviceLoginError("DEVICE_BRIDGE_INVALID")
    return web_session_id


def _consume_phone_token(phone_binding_token: str) -> dict[str, Any]:
    payload = _consume(_phone_token_key(phone_binding_token), "DEVICE_PHONE_TOKEN_INVALID")
    if any(
        not isinstance(payload.get(field), str) or not payload[field]
        for field in ("web_session_id", "appid", "openid")
    ) or not isinstance(payload.get("unionid"), str):
        raise DeviceLoginError("DEVICE_PHONE_TOKEN_INVALID")
    return payload


def _consume_ticket(ticket: str) -> dict[str, Any]:
    payload = _consume(_ticket_key(ticket), "DEVICE_TICKET_INVALID")
    if any(
        not isinstance(payload.get(field), str) or not payload[field]
        for field in ("user_id", "requested_role", "browser_session_id")
    ):
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    return payload


def _consume_ticket_for_completion(ticket: str) -> _ConsumedTicket:
    consumed_at = time.monotonic()
    payload, raw_value, ttl_millis = _atomic_consume_with_ttl(
        _ticket_key(ticket), "DEVICE_TICKET_INVALID"
    )
    if (
        not isinstance(payload, dict)
        or _is_expired(payload)
        or not isinstance(ttl_millis, int)
        or ttl_millis <= 0
    ):
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    return _ConsumedTicket(
        payload=payload,
        raw_value=raw_value,
        restore_deadline=consumed_at + ttl_millis / 1000,
    )


def _consume(key: str, error_code: str) -> dict[str, Any]:
    payload = _atomic_consume(key, error_code)
    if not isinstance(payload, dict) or _is_expired(payload):
        raise DeviceLoginError(error_code)
    return payload


def _load_ticket(ticket: str) -> dict[str, Any]:
    if not isinstance(ticket, str) or not ticket:
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    payload = _cache_get(_ticket_key(ticket))
    if not isinstance(payload, dict) or _is_expired(payload):
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    if any(
        not isinstance(payload.get(field), str) or not payload[field]
        for field in ("user_id", "requested_role", "browser_session_id")
    ):
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    return payload


def _atomic_consume(key: str, error_code: str) -> Any:
    consume = getattr(cache, "atomic_consume", None)
    if callable(consume):
        try:
            return consume(key)
        except Exception:
            raise DeviceLoginError(error_code) from None

    redis_parts = _redis_parts()
    if redis_parts is None:
        raise DeviceLoginError(error_code)
    client, redis_key, serializer = redis_parts
    try:
        raw = client.eval(
            "local value = redis.call('GET', KEYS[1]); "
            "if value then redis.call('DEL', KEYS[1]); end; return value",
            1,
            redis_key(key),
        )
        return None if raw is None else serializer.loads(raw)
    except Exception:
        raise DeviceLoginError(error_code) from None


def _atomic_consume_with_ttl(
    key: str, error_code: str
) -> tuple[Any, Any | None, int]:
    consume = getattr(cache, "atomic_consume_with_ttl", None)
    if callable(consume):
        try:
            consumed = consume(key)
        except Exception:
            raise DeviceLoginError(error_code) from None
        if not isinstance(consumed, tuple) or len(consumed) != 2:
            raise DeviceLoginError(error_code)
        payload, ttl_millis = consumed
        return payload, None, ttl_millis

    redis_parts = _redis_parts()
    if redis_parts is None:
        raise DeviceLoginError(error_code)
    client, redis_key, serializer = redis_parts
    try:
        raw_value, ttl_millis = client.eval(
            "local value = redis.call('GET', KEYS[1]); "
            "if not value then return {false, -2}; end; "
            "local ttl = redis.call('PTTL', KEYS[1]); "
            "redis.call('DEL', KEYS[1]); return {value, ttl}",
            1,
            redis_key(key),
        )
        if raw_value is None:
            return None, None, int(ttl_millis)
        return serializer.loads(raw_value), raw_value, int(ttl_millis)
    except Exception:
        raise DeviceLoginError(error_code) from None


def _restore_ticket(ticket: str, consumed_ticket: _ConsumedTicket) -> None:
    remaining_millis = math.floor(
        (consumed_ticket.restore_deadline - time.monotonic()) * 1000
    )
    if remaining_millis <= 0:
        raise DeviceLoginError("DEVICE_TICKET_INVALID")
    key = _ticket_key(ticket)
    restore = getattr(cache, "atomic_restore", None)
    if callable(restore):
        try:
            restored = bool(restore(key, consumed_ticket.payload, remaining_millis))
        except Exception:
            restored = False
    else:
        redis_parts = _redis_parts()
        if redis_parts is None or consumed_ticket.raw_value is None:
            restored = False
        else:
            client, redis_key, _ = redis_parts
            try:
                restored = bool(
                    client.set(
                        redis_key(key),
                        consumed_ticket.raw_value,
                        nx=True,
                        px=remaining_millis,
                    )
                )
            except Exception:
                restored = False
    if not restored:
        raise DeviceLoginError("DEVICE_TICKET_INVALID")


@contextmanager
def _session_lock(web_session_id: str):
    with _cache_lock(_session_lock_key(web_session_id), "DEVICE_SESSION_EXPIRED"):
        yield


@contextmanager
def _ticket_lock(ticket: str):
    with _cache_lock(_ticket_lock_key(ticket), "DEVICE_TICKET_INVALID"):
        yield


@contextmanager
def _cache_lock(key: str, error_code: str):
    token = secrets.token_urlsafe(16)
    deadline = time.monotonic() + DEVICE_LOCK_WAIT_SECONDS
    while not _try_cache_lock(key, token):
        if time.monotonic() >= deadline:
            raise DeviceLoginError(error_code)
        time.sleep(0.005)
    try:
        yield
    finally:
        _release_cache_lock(key, token)


def _try_cache_lock(key: str, token: str) -> bool:
    acquire = getattr(cache, "acquire_lock", None)
    if callable(acquire):
        try:
            return bool(acquire(key, token, DEVICE_LOCK_TTL_SECONDS))
        except Exception:
            return False
    redis_parts = _redis_parts()
    if redis_parts is None:
        return False
    client, redis_key, _ = redis_parts
    try:
        return bool(client.set(redis_key(key), token, nx=True, ex=DEVICE_LOCK_TTL_SECONDS))
    except Exception:
        return False


def _release_cache_lock(key: str, token: str) -> None:
    release = getattr(cache, "release_lock", None)
    if callable(release):
        try:
            release(key, token)
        except Exception:
            pass
        return
    redis_parts = _redis_parts()
    if redis_parts is None:
        return
    client, redis_key, _ = redis_parts
    try:
        client.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then "
            "return redis.call('DEL', KEYS[1]); end; return 0",
            1,
            redis_key(key),
            token,
        )
    except Exception:
        pass


def _redis_parts():
    backend_client = getattr(cache, "_cache", None)
    redis_key = getattr(cache, "make_key", None)
    get_client = getattr(backend_client, "get_client", None)
    serializer = getattr(backend_client, "_serializer", None)
    if not callable(redis_key) or not callable(get_client) or serializer is None:
        return None
    try:
        return get_client(write=True), redis_key, serializer
    except Exception:
        return None


def _cache_set(key: str, payload: dict[str, Any], expires_at: float) -> None:
    if not isinstance(expires_at, (int, float)):
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    timeout = math.ceil(expires_at - timezone.now().timestamp())
    if timeout <= 0:
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")
    try:
        stored = cache.set(key, dict(payload), timeout=timeout)
    except Exception:
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED") from None
    if stored is False:
        raise DeviceLoginError("DEVICE_SESSION_EXPIRED")


def _cache_get(key: str) -> Any:
    try:
        return cache.get(key)
    except Exception:
        return None


def _is_expired(payload: dict[str, Any]) -> bool:
    expires_at = payload.get("expires_at")
    return not isinstance(expires_at, (int, float)) or expires_at <= timezone.now().timestamp()


def _require_browser(payload: dict[str, Any], browser_session_id: str) -> None:
    stored_browser_session_id = payload.get("browser_session_id")
    if (
        not isinstance(browser_session_id, str)
        or not browser_session_id
        or not isinstance(stored_browser_session_id, str)
        or not stored_browser_session_id
        or not secrets.compare_digest(stored_browser_session_id, browser_session_id)
    ):
        raise DeviceLoginError("DEVICE_BROWSER_MISMATCH")


def _validate_identity(identity: MiniProgramIdentity) -> None:
    if (
        not isinstance(identity, MiniProgramIdentity)
        or not isinstance(identity.appid, str)
        or not identity.appid
        or not isinstance(identity.openid, str)
        or not identity.openid
        or not isinstance(identity.unionid, str)
    ):
        raise DeviceLoginError("DEVICE_IDENTITY_INVALID")


def _require_user_role(user: UserAccount, requested_role: str) -> None:
    try:
        validate_active_role(user, requested_role)
    except RoleNotGranted:
        raise DeviceLoginError("DEVICE_ROLE_CONFLICT")


def _get_wechat_miniprogram_configuration(error_code: str) -> tuple[str, str]:
    values = (
        getattr(settings, "WECHAT_MP_APPID", ""),
        getattr(settings, "WECHAT_MP_APPSECRET", ""),
    )
    if not all(isinstance(value, str) and value for value in values):
        raise DeviceLoginError(error_code)
    return values


def _get_wechat_json(
    client: Any, url: str, params: dict[str, str], error_code: str
) -> dict[str, Any]:
    try:
        payload = client.get_json(url, params=params, timeout=10.0)
    except Exception:
        raise DeviceLoginError(error_code) from None
    return _require_wechat_success_payload(payload, error_code)


def _post_wechat_json(
    client: Any,
    url: str,
    *,
    params: dict[str, str],
    json_body: dict[str, str],
    error_code: str,
) -> dict[str, Any]:
    try:
        payload = client.post_json(
            url, params=params, json=json_body, timeout=10.0
        )
    except Exception:
        raise DeviceLoginError(error_code)
    return _require_wechat_success_payload(payload, error_code)


def _require_wechat_success_payload(payload: Any, error_code: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DeviceLoginError(error_code)
    if "errcode" in payload and not (
        type(payload["errcode"]) is int and payload["errcode"] == 0
    ):
        raise DeviceLoginError(error_code)
    return payload


def _session_key(value: str) -> str:
    return f"wechat_device:session:{value}"


def _bridge_key(value: str) -> str:
    return f"wechat_device:bridge:{value}"


def _phone_token_key(value: str) -> str:
    return f"wechat_device:phone_token:{value}"


def _ticket_key(value: str) -> str:
    return f"wechat_device:ticket:{value}"


def _session_lock_key(value: str) -> str:
    return f"wechat_device:session_lock:{value}"


def _ticket_lock_key(value: str) -> str:
    return f"wechat_device:ticket_lock:{value}"
