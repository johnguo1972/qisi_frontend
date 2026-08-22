from datetime import datetime, timezone as datetime_timezone

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
    clocked_cache = ClockedCache()
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
