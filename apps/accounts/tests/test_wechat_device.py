from datetime import datetime, timezone as datetime_timezone
import threading

import pytest

from apps.accounts import wechat_device
from apps.accounts.models import UserAccount, WechatIdentity
from apps.accounts.roles import grant_user_role


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
