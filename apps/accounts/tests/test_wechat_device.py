from datetime import datetime, timezone as datetime_timezone
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from apps.accounts import wechat_device
from apps.accounts.models import UserAccount, WechatIdentity
from apps.accounts.roles import grant_user_role, revoke_user_role


class FakeWechatResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeWechatClient:
    """External WeChat boundary fake; application behavior remains real."""

    def __init__(self, *, get_payload, post_payload=None):
        self.get_payload = get_payload
        self.post_payload = post_payload
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append(("get", url, params, timeout))
        return FakeWechatResponse(self.get_payload)

    def post(self, url, *, params, json, timeout):
        self.calls.append(("post", url, params, json, timeout))
        return FakeWechatResponse(self.post_payload)

    def get_json(self, url, *, params, timeout):
        self.calls.append(("get", url, params, timeout))
        return self.get_payload

    def post_json(self, url, *, params, json, timeout):
        self.calls.append(("post", url, params, json, timeout))
        return self.post_payload


class UnavailableWechatClient:
    def get(self, *args, **kwargs):
        raise httpx.ConnectError("wechat unavailable")

    def get_json(self, *args, **kwargs):
        raise httpx.ConnectError("wechat unavailable")


class LocalWechatServer:
    """Real loopback transport for tests that need to observe client logging."""

    def __init__(self, responses):
        self.responses = responses
        self.server = None
        self.thread = None

    def __enter__(self):
        responses = self.responses

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._respond()

            def do_POST(self):
                self._respond()

            def log_message(self, format, *args):
                return

            def _respond(self):
                status, payload = responses[self.path.split("?", 1)[0]]
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *args):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()


def _use_local_wechat_urls(monkeypatch, base_url):
    monkeypatch.setattr(wechat_device, "WECHAT_CODE2SESSION_URL", f"{base_url}/code2session")
    monkeypatch.setattr(wechat_device, "WECHAT_TOKEN_URL", f"{base_url}/token")
    monkeypatch.setattr(wechat_device, "WECHAT_PHONE_URL", f"{base_url}/phone")


def _success_responses():
    return {
        "/code2session": (200, {"openid": "openid-from-wechat"}),
        "/token": (200, {"access_token": "access-token-from-wechat"}),
        "/phone": (200, {"phone_info": {"phoneNumber": "13900000001"}}),
    }


def test_exchange_login_code_returns_server_verified_identity(settings):
    """Dropping server-side code2session verification would accept a forged identity."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    client = FakeWechatClient(
        get_payload={
            "openid": "openid-1",
            "unionid": "unionid-1",
            "session_key": "hidden",
        }
    )

    identity = wechat_device.exchange_miniprogram_login_code("one-time", client)

    assert identity == wechat_device.MiniProgramIdentity(
        appid="wx-test", openid="openid-1", unionid="unionid-1"
    )
    assert client.calls == [
        (
            "get",
            wechat_device.WECHAT_CODE2SESSION_URL,
            {
                "appid": "wx-test",
                "secret": "secret",
                "js_code": "one-time",
                "grant_type": "authorization_code",
            },
            10.0,
        )
    ]


def test_exchange_phone_code_returns_wechat_verified_mobile(settings):
    """Using caller-supplied mobile input instead of WeChat's response would be unsafe."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    client = FakeWechatClient(
        get_payload={"access_token": "provider-token"},
        post_payload={"phone_info": {"phoneNumber": "13900000001"}},
    )

    mobile = wechat_device.exchange_miniprogram_phone_code("phone-once", client)

    assert mobile == "13900000001"
    assert client.calls == [
        (
            "get",
            wechat_device.WECHAT_TOKEN_URL,
            {
                "grant_type": "client_credential",
                "appid": "wx-test",
                "secret": "secret",
            },
            10.0,
        ),
        (
            "post",
            wechat_device.WECHAT_PHONE_URL,
            {"access_token": "provider-token"},
            {"code": "phone-once"},
            10.0,
        ),
    ]


def test_exchange_phone_code_rejects_wechat_error(settings):
    """Treating a provider errcode as a phone number response would authorize anyone."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    client = FakeWechatClient(
        get_payload={"access_token": "token"},
        post_payload={"errcode": 40029, "errmsg": "invalid code"},
    )

    with pytest.raises(wechat_device.DeviceLoginError) as error:
        wechat_device.exchange_miniprogram_phone_code("bad-code", client)

    assert error.value.code == "DEVICE_PHONE_AUTHORIZATION_FAILED"


def test_exchange_login_code_rejects_network_and_incomplete_provider_responses(
    settings,
):
    """A transport failure or response without OpenID must not create an identity."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"

    for client in (
        UnavailableWechatClient(),
        FakeWechatClient(get_payload=[]),
        FakeWechatClient(get_payload={"unionid": "unionid-1"}),
    ):
        with pytest.raises(wechat_device.DeviceLoginError) as error:
            wechat_device.exchange_miniprogram_login_code("one-time", client)

        assert error.value.code == "DEVICE_LOGIN_AUTHORIZATION_FAILED"


def test_exchange_phone_code_rejects_non_json_and_missing_mobile(settings):
    """A non-JSON payload or incomplete phone_info must not authorize a phone."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"

    for client in (
        FakeWechatClient(get_payload={"access_token": "token"}, post_payload=[]),
        FakeWechatClient(
            get_payload={"access_token": "token"}, post_payload={"phone_info": {}}
        ),
    ):
        with pytest.raises(wechat_device.DeviceLoginError) as error:
            wechat_device.exchange_miniprogram_phone_code("phone-once", client)

        assert error.value.code == "DEVICE_PHONE_AUTHORIZATION_FAILED"


def test_wechat_credential_exchanges_do_not_log_sensitive_values(settings, caplog):
    """Logging request codes or provider identities would leak reusable credentials."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    login_code = "login-code-must-not-be-logged"
    phone_code = "phone-code-must-not-be-logged"
    access_token = "access-token-must-not-be-logged"
    openid = "openid-must-not-be-logged"
    mobile = "13900000001"
    caplog.set_level(logging.DEBUG, logger="apps.accounts.wechat_device")

    wechat_device.exchange_miniprogram_login_code(
        login_code,
        FakeWechatClient(get_payload={"openid": openid, "session_key": "hidden"}),
    )
    wechat_device.exchange_miniprogram_phone_code(
        phone_code,
        FakeWechatClient(
            get_payload={"access_token": access_token},
            post_payload={"phone_info": {"phoneNumber": mobile}},
        ),
    )

    for secret in (login_code, phone_code, access_token, openid, mobile):
        assert secret not in caplog.text


def test_default_wechat_transport_does_not_log_sensitive_urls(
    settings, monkeypatch, caplog
):
    """A transport INFO log must not expose credential-bearing query strings."""
    settings.WECHAT_MP_APPID = "appid-must-not-be-logged"
    settings.WECHAT_MP_APPSECRET = "appsecret-must-not-be-logged"
    login_code = "login-code-must-not-be-logged-by-transport"
    phone_code = "phone-code-must-not-be-logged-by-transport"
    openid = "openid-from-wechat"
    access_token = "access-token-from-wechat"
    mobile = "13900000001"
    caplog.set_level(logging.INFO)

    with LocalWechatServer(_success_responses()) as base_url:
        _use_local_wechat_urls(monkeypatch, base_url)
        wechat_device.exchange_miniprogram_login_code(login_code)
        wechat_device.exchange_miniprogram_phone_code(phone_code)

    for secret in (
        settings.WECHAT_MP_APPSECRET,
        login_code,
        phone_code,
        access_token,
        openid,
        mobile,
    ):
        assert secret not in caplog.text


@pytest.mark.parametrize("failed_request", ("login", "token", "phone"))
def test_wechat_exchange_rejects_every_non_success_http_response(
    settings, monkeypatch, failed_request
):
    """Ignoring a 4xx or 5xx status would accept an untrusted WeChat payload."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    responses = _success_responses()
    path = {"login": "/code2session", "token": "/token", "phone": "/phone"}[failed_request]
    responses[path] = (401 if failed_request != "token" else 500, responses[path][1])

    with LocalWechatServer(responses) as base_url:
        _use_local_wechat_urls(monkeypatch, base_url)
        with pytest.raises(wechat_device.DeviceLoginError) as error:
            if failed_request == "login":
                wechat_device.exchange_miniprogram_login_code("one-time")
            else:
                wechat_device.exchange_miniprogram_phone_code("phone-once")

    assert error.value.code == (
        "DEVICE_LOGIN_AUTHORIZATION_FAILED"
        if failed_request == "login"
        else "DEVICE_PHONE_AUTHORIZATION_FAILED"
    )


@pytest.mark.parametrize("failed_response", ("login", "token", "phone"))
def test_wechat_exchange_rejects_mixed_nonzero_errcode_responses(
    settings, monkeypatch, failed_response
):
    """A nonzero WeChat errcode must win over otherwise plausible payload fields."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    responses = _success_responses()
    path = {"login": "/code2session", "token": "/token", "phone": "/phone"}[failed_response]
    status, payload = responses[path]
    responses[path] = (status, {**payload, "errcode": 40029})

    with LocalWechatServer(responses) as base_url:
        _use_local_wechat_urls(monkeypatch, base_url)
        with pytest.raises(wechat_device.DeviceLoginError) as error:
            if failed_response == "login":
                wechat_device.exchange_miniprogram_login_code("one-time")
            else:
                wechat_device.exchange_miniprogram_phone_code("phone-once")

    assert error.value.code == (
        "DEVICE_LOGIN_AUTHORIZATION_FAILED"
        if failed_response == "login"
        else "DEVICE_PHONE_AUTHORIZATION_FAILED"
    )


class ClockedCache:
    """Small cache fake that enforces TTLs against a controllable clock."""

    def __init__(self):
        self.now = 0
        self.values = {}

    def set(self, key, value, timeout):
        self.values[key] = (value, self.now + timeout)
        return True

    def get(self, key):
        stored = self.values.get(key)
        if stored is None:
            return None
        value, expires_at = stored
        if self.now >= expires_at:
            self.values.pop(key, None)
            return None
        return value

    def delete(self, key):
        return self.values.pop(key, None) is not None

    def advance(self, seconds):
        self.now += seconds


class AtomicClockedCache(ClockedCache):
    """Thread-safe fake exposing the atomic Redis operations the service needs."""

    def __init__(self):
        super().__init__()
        self._mutex = threading.Lock()
        self._locks = {}
        self._session_read_barrier = None
        self._read_barrier = None

    def get(self, key):
        barrier = self._session_read_barrier
        session_race = (
            barrier is not None
            and key == self._session_read_barrier[0]
            and not self._locks
        )
        read_barrier = self._read_barrier
        value_race = read_barrier is not None and key == read_barrier[0]
        if session_race or value_race:
            with self._mutex:
                snapshot = super().get(key)
            (barrier if session_race else read_barrier)[1].wait(timeout=2)
            return snapshot
        with self._mutex:
            return super().get(key)

    def atomic_consume(self, key):
        with self._mutex:
            payload = super().get(key)
            if payload is not None:
                super().delete(key)
            return payload

    def atomic_consume_with_ttl(self, key):
        with self._mutex:
            stored = self.values.get(key)
            if stored is None:
                return None
            payload, expires_at = stored
            if self.now >= expires_at:
                self.values.pop(key, None)
                return None
            self.values.pop(key, None)
            return payload, int((expires_at - self.now) * 1000)

    def atomic_restore(self, key, payload, ttl_millis):
        with self._mutex:
            if super().get(key) is not None or ttl_millis <= 0:
                return False
            self.values[key] = (payload, self.now + ttl_millis / 1000)
            return True

    def acquire_lock(self, key, token, timeout):
        with self._mutex:
            stored = self._locks.get(key)
            if stored is not None and self.now < stored[1]:
                return False
            self._locks[key] = (token, self.now + timeout)
            return True

    def release_lock(self, key, token):
        with self._mutex:
            if self._locks.get(key, (None,))[0] == token:
                self._locks.pop(key, None)


@pytest.fixture
def atomic_clock(monkeypatch):
    clocked_cache = AtomicClockedCache()
    monkeypatch.setattr(wechat_device, "cache", clocked_cache)
    monkeypatch.setattr(
        wechat_device.timezone,
        "now",
        lambda: datetime.fromtimestamp(clocked_cache.now, tz=datetime_timezone.utc),
    )
    return clocked_cache


def _user(mobile, role):
    user = UserAccount.objects.create(
        role_type=role,
        mobile=mobile,
        display_name=f"User{mobile[-4:]}",
        password="",
    )
    grant_user_role(user, role)
    return user


@pytest.fixture
def clock(monkeypatch):
    clocked_cache = AtomicClockedCache()
    monkeypatch.setattr(wechat_device, "cache", clocked_cache)
    monkeypatch.setattr(
        wechat_device.timezone,
        "now",
        lambda: datetime.fromtimestamp(clocked_cache.now, tz=datetime_timezone.utc),
    )
    return clocked_cache


def test_device_session_and_bridge_are_browser_bound_and_expire_together(clock):
    """Removing browser binding or absolute expiry would allow a QR login takeover."""
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")

    assert session.expires_in == 300
    assert len(bridge) <= 32
    assert wechat_device.get_or_create_device_bridge(session.value, "browser-a") == bridge
    with pytest.raises(wechat_device.DeviceLoginError) as mismatch:
        wechat_device.get_or_create_device_bridge(session.value, "browser-b")
    assert mismatch.value.code == "DEVICE_BROWSER_MISMATCH"

    clock.advance(301)
    with pytest.raises(wechat_device.DeviceLoginError) as expired:
        wechat_device.get_device_login_status(session.value, "browser-a")
    assert expired.value.code == "DEVICE_SESSION_EXPIRED"


def test_concurrent_bridge_creation_returns_the_single_session_bridge(atomic_clock):
    """Without a session lock, two QR renders can persist different bridge codes."""
    session = wechat_device.create_device_login_session("student", "browser-a")
    atomic_clock._session_read_barrier = (
        wechat_device._session_key(session.value), threading.Barrier(2)
    )
    results = []
    errors = []

    def create_bridge():
        try:
            results.append(
                wechat_device.get_or_create_device_bridge(session.value, "browser-a")
            )
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=create_bridge) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not errors
    assert len(results) == 2
    assert results[0] == results[1]


@pytest.mark.parametrize(
    ("key_factory", "payload", "consume"),
    [
        (
            wechat_device._bridge_key,
            {"web_session_id": "session", "expires_at": 300},
            wechat_device._consume_bridge,
        ),
        (
            wechat_device._phone_token_key,
            {
                "web_session_id": "session",
                "appid": "wx-test",
                "openid": "openid",
                "unionid": "",
                "expires_at": 300,
            },
            wechat_device._consume_phone_token,
        ),
        (
            wechat_device._ticket_key,
            {
                "user_id": "user",
                "requested_role": "student",
                "browser_session_id": "browser-a",
                "expires_at": 300,
            },
            wechat_device._consume_ticket,
        ),
    ],
)
def test_concurrent_one_time_values_have_exactly_one_consumer(
    atomic_clock, key_factory, payload, consume
):
    """A get/delete implementation lets both threads observe the same credential."""
    value = "concurrent-value"
    key = key_factory(value)
    atomic_clock.set(key, payload, timeout=300)
    atomic_clock._read_barrier = (key, threading.Barrier(2))
    results = []
    errors = []
    start = threading.Barrier(2)

    def consume_value():
        start.wait(timeout=2)
        try:
            results.append(consume(value))
        except wechat_device.DeviceLoginError as error:
            errors.append(error.code)

    threads = [threading.Thread(target=consume_value) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert len(results) == 1
    assert len(errors) == 1


@pytest.mark.django_db
def test_invalid_completion_request_does_not_consume_the_completion_ticket(clock):
    """A cross-browser or cross-role request must not deny the legitimate browser."""
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")
    pending = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", "ticket-openid", ""),
    )
    wechat_device.bind_device_identity_phone(pending.phone_binding_token, "13900009004")
    ticket = wechat_device.get_device_login_status(session.value, "browser-a").ticket

    with pytest.raises(wechat_device.DeviceLoginError) as invalid_role:
        wechat_device.complete_device_login(ticket, "browser-a", "teacher")
    with pytest.raises(wechat_device.DeviceLoginError) as invalid_browser:
        wechat_device.complete_device_login(ticket, "browser-b", "student")
    user, tokens = wechat_device.complete_device_login(ticket, "browser-a", "student")

    assert invalid_role.value.code == "DEVICE_TICKET_INVALID"
    assert invalid_browser.value.code == "DEVICE_TICKET_INVALID"
    assert user.mobile == "13900009004"
    assert tokens["access_token"]


def _bound_ticket(mobile, openid):
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")
    pending = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", openid, ""),
    )
    wechat_device.bind_device_identity_phone(pending.phone_binding_token, mobile)
    ticket = wechat_device.get_device_login_status(session.value, "browser-a").ticket
    user = UserAccount.objects.get(mobile=mobile)
    return user, ticket


@pytest.mark.django_db
def test_disabled_account_does_not_consume_ticket_before_reactivation(clock):
    """Consuming before active-state validation locks out a restored account."""
    user, ticket = _bound_ticket("13900009005", "disabled-openid")
    user.status = "inactive"
    user.save(update_fields=["status"])

    with pytest.raises(wechat_device.DeviceLoginError) as disabled:
        wechat_device.complete_device_login(ticket, "browser-a", "student")
    user.status = "active"
    user.save(update_fields=["status"])
    completed, tokens = wechat_device.complete_device_login(ticket, "browser-a", "student")

    assert disabled.value.code == "DEVICE_ROLE_CONFLICT"
    assert completed.id == user.id
    assert tokens["access_token"]


@pytest.mark.django_db
def test_revoked_role_does_not_consume_ticket_before_regrant(clock):
    """Consuming before role validation locks out a role restored by an admin."""
    user, ticket = _bound_ticket("13900009006", "revoked-role-openid")
    revoke_user_role(user, "student")

    with pytest.raises(wechat_device.DeviceLoginError) as revoked:
        wechat_device.complete_device_login(ticket, "browser-a", "student")
    grant_user_role(user, "student")
    completed, tokens = wechat_device.complete_device_login(ticket, "browser-a", "student")

    assert revoked.value.code == "DEVICE_ROLE_CONFLICT"
    assert completed.id == user.id
    assert tokens["access_token"]


@pytest.mark.django_db
def test_role_revoked_after_precheck_restores_ticket_for_retry(clock, monkeypatch):
    """A post-precheck revoke must compensate the consumed ticket before failing."""
    user, ticket = _bound_ticket("13900009007", "mid-flight-revoke-openid")
    original_generate_tokens = wechat_device.generate_tokens
    monotonic_clock = [0]
    monkeypatch.setattr(wechat_device.time, "monotonic", lambda: monotonic_clock[0])

    def revoke_then_generate(account, requested_role):
        monotonic_clock[0] = 1
        revoke_user_role(user, "student")
        return original_generate_tokens(account, requested_role)

    monkeypatch.setattr(wechat_device, "generate_tokens", revoke_then_generate)
    with pytest.raises(wechat_device.DeviceLoginError) as revoked:
        wechat_device.complete_device_login(ticket, "browser-a", "student")

    _, restored_expiry = clock.values[wechat_device._ticket_key(ticket)]
    grant_user_role(user, "student")
    monkeypatch.setattr(wechat_device, "generate_tokens", original_generate_tokens)
    completed, tokens = wechat_device.complete_device_login(ticket, "browser-a", "student")

    assert revoked.value.code == "DEVICE_ROLE_CONFLICT"
    assert restored_expiry == 299
    assert completed.id == user.id
    assert tokens["access_token"]


@pytest.mark.django_db
def test_restore_ttl_starts_before_atomic_consume_returns(clock, monkeypatch):
    """Transport time after Lua consumption must reduce, never extend, the TTL."""
    user, ticket = _bound_ticket("13900009008", "consume-delay-openid")
    original_consume = clock.atomic_consume_with_ttl
    original_generate_tokens = wechat_device.generate_tokens
    monotonic_clock = [0]
    monkeypatch.setattr(wechat_device.time, "monotonic", lambda: monotonic_clock[0])

    def delayed_consume(key):
        consumed = original_consume(key)
        monotonic_clock[0] = 1
        return consumed

    def revoke_then_generate(account, requested_role):
        revoke_user_role(user, "student")
        return original_generate_tokens(account, requested_role)

    monkeypatch.setattr(clock, "atomic_consume_with_ttl", delayed_consume)
    monkeypatch.setattr(wechat_device, "generate_tokens", revoke_then_generate)
    with pytest.raises(wechat_device.DeviceLoginError) as revoked:
        wechat_device.complete_device_login(ticket, "browser-a", "student")

    _, restored_expiry = clock.values[wechat_device._ticket_key(ticket)]
    assert revoked.value.code == "DEVICE_ROLE_CONFLICT"
    assert restored_expiry == 299


@pytest.mark.django_db(transaction=True)
def test_ticket_lock_blocks_second_completion_until_authorization_restore(
    clock, monkeypatch
):
    """Only the post-restore contender may be the single successful consumer."""
    user, ticket = _bound_ticket("13900009009", "threaded-restore-openid")
    original_generate_tokens = wechat_device.generate_tokens
    original_restore = clock.atomic_restore
    original_try_lock = wechat_device._try_cache_lock
    first_consumed = threading.Event()
    second_attempted = threading.Event()
    restore_written = threading.Event()
    release_restore = threading.Event()
    first_result = []
    second_result = []

    def generate_with_first_thread_revoke(account, requested_role):
        if threading.current_thread().name == "first-complete":
            revoke_user_role(user, "student")
            first_consumed.set()
        return original_generate_tokens(account, requested_role)

    def restore_then_pause(key, payload, ttl_millis):
        restored = original_restore(key, payload, ttl_millis)
        restore_written.set()
        assert release_restore.wait(timeout=3)
        return restored

    def observe_second_lock(key, token):
        if (
            threading.current_thread().name == "second-complete"
            and key == wechat_device._ticket_lock_key(ticket)
        ):
            second_attempted.set()
        return original_try_lock(key, token)

    def first_complete():
        try:
            wechat_device.complete_device_login(ticket, "browser-a", "student")
        except wechat_device.DeviceLoginError as error:
            first_result.append(error.code)

    def second_complete():
        try:
            second_result.append(
                wechat_device.complete_device_login(ticket, "browser-a", "student")
            )
        except wechat_device.DeviceLoginError as error:
            second_result.append(error.code)

    monkeypatch.setattr(wechat_device, "generate_tokens", generate_with_first_thread_revoke)
    monkeypatch.setattr(clock, "atomic_restore", restore_then_pause)
    monkeypatch.setattr(wechat_device, "_try_cache_lock", observe_second_lock)
    first = threading.Thread(target=first_complete, name="first-complete")
    second = threading.Thread(target=second_complete, name="second-complete")
    first.start()
    assert first_consumed.wait(timeout=3)
    second.start()
    assert second_attempted.wait(timeout=3)
    assert restore_written.wait(timeout=3)
    assert not second_result

    grant_user_role(user, "student")
    release_restore.set()
    first.join(timeout=3)
    second.join(timeout=3)

    assert first_result == ["DEVICE_ROLE_CONFLICT"]
    assert len(second_result) == 1
    completed, tokens = second_result[0]
    assert completed.id == user.id
    assert tokens["access_token"]


@pytest.mark.django_db
def test_ticket_restore_failure_fails_closed_without_issuing_jwt(clock, monkeypatch):
    """An authorization failure cannot become a retryable ticket if restore is lost."""
    from apps.accounts import services

    user, ticket = _bound_ticket("13900009010", "restore-failure-openid")
    original_generate_tokens = wechat_device.generate_tokens

    def revoke_then_generate(account, requested_role):
        revoke_user_role(user, "student")
        return original_generate_tokens(account, requested_role)

    monkeypatch.setattr(wechat_device, "generate_tokens", revoke_then_generate)
    monkeypatch.setattr(clock, "atomic_restore", lambda *args: False)
    monkeypatch.setattr(
        services.RefreshToken,
        "for_user",
        lambda *args: (_ for _ in ()).throw(AssertionError("JWT must not be issued")),
    )
    with pytest.raises(wechat_device.DeviceLoginError) as failed_restore:
        wechat_device.complete_device_login(ticket, "browser-a", "student")

    assert failed_restore.value.code == "DEVICE_TICKET_INVALID"
    assert wechat_device._ticket_key(ticket) not in clock.values


@pytest.mark.django_db
def test_known_identity_marks_device_session_bound_without_issuing_tokens(clock):
    """Signing a JWT at scan time would expose browser credentials to the phone flow."""
    teacher = _user("13900009002", "teacher")
    identity = WechatIdentity.objects.create(user=teacher, appid="wx-test", openid="known-openid")
    session = wechat_device.create_device_login_session("teacher", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")

    result = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity(
            appid=identity.appid, openid=identity.openid, unionid=""
        ),
    )
    status = wechat_device.get_device_login_status(session.value, "browser-a")

    assert result.status == "login_confirmed"
    assert result.phone_binding_token is None
    assert status.status == "login_confirmed"
    assert status.bound is True
    assert status.ticket
    assert "access_token" not in result.__dict__


@pytest.mark.django_db
def test_unknown_identity_requires_phone_and_bridge_cannot_replay(clock):
    """Keeping a bridge reusable would let an attacker replace a pending identity."""
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")

    result = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", "new-openid", ""),
    )

    assert result.status == "phone_authorization_required"
    assert result.phone_binding_token
    with pytest.raises(wechat_device.DeviceLoginError) as replay:
        wechat_device.confirm_device_identity(
            bridge,
            wechat_device.MiniProgramIdentity("wx-test", "new-openid", ""),
        )
    assert replay.value.code == "DEVICE_BRIDGE_INVALID"


@pytest.mark.django_db
def test_phone_binding_creates_safe_identity_then_completion_consumes_ticket(
    clock,
):
    """Skipping ticket consumption would permit repeated JWT issuance from one scan."""
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")
    pending = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", "first-openid", "first-unionid"),
    )

    wechat_device.bind_device_identity_phone(pending.phone_binding_token, "13900009001")
    status = wechat_device.get_device_login_status(session.value, "browser-a")
    user, tokens = wechat_device.complete_device_login(
        status.ticket, "browser-a", "student"
    )

    assert user.mobile == "13900009001"
    assert tokens["access_token"]
    assert WechatIdentity.objects.get().user_id == user.id
    with pytest.raises(wechat_device.DeviceLoginError) as replay:
        wechat_device.complete_device_login(status.ticket, "browser-a", "student")
    assert replay.value.code == "DEVICE_TICKET_INVALID"


@pytest.mark.django_db
def test_phone_binding_rejects_second_wechat_identity_for_same_user(clock):
    """Replacing a user's existing one-to-one identity would silently hijack it."""
    student = _user("13900009003", "student")
    WechatIdentity.objects.create(user=student, appid="wx-test", openid="original-openid")
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")
    pending = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", "second-openid", ""),
    )

    with pytest.raises(wechat_device.DeviceLoginError) as conflict:
        wechat_device.bind_device_identity_phone(pending.phone_binding_token, student.mobile)

    assert conflict.value.code == "DEVICE_IDENTITY_CONFLICT"
    assert WechatIdentity.objects.get(user=student).openid == "original-openid"
