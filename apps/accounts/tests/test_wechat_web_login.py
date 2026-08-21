import logging
from datetime import datetime, timezone as datetime_timezone

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts import views, wechat_web
from apps.accounts.models import UserAccount, WechatWebIdentity
from apps.accounts.roles import grant_user_role, has_user_role
from apps.accounts.services import generate_tokens


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "wechat-web-login-tests",
    }
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeWechatClient:
    def __init__(self, *payloads):
        self.responses = [FakeResponse(payload) for payload in payloads]
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


class ClockedCache:
    """Minimal cache fake whose expiry can be advanced without a database."""

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


@pytest.fixture(autouse=True)
def isolate_cache():
    with override_settings(
        CACHES=TEST_CACHES,
        WECHAT_WEB_APP_ID="web-test-app-id",
        WECHAT_WEB_APP_SECRET="web-test-secret",
    ):
        cache.clear()
        yield
        cache.clear()


@pytest.fixture
def wechat_settings():
    with override_settings(
        WECHAT_WEB_APP_ID="web-test-app-id",
        WECHAT_WEB_APP_SECRET="web-test-secret",
        WECHAT_WEB_REDIRECT_URI="https://example.test/auth/wechat/callback",
    ):
        yield


def test_browser_bound_state_rejects_a_different_browser_and_is_consumed():
    state = wechat_web.create_web_login_state(
        requested_role="teacher",
        browser_session_id="browser-a",
    )

    with pytest.raises(wechat_web.WebLoginStateError):
        wechat_web.consume_web_login_state(state.value, browser_session_id="browser-b")

    with pytest.raises(wechat_web.WebLoginStateError):
        wechat_web.consume_web_login_state(state.value, browser_session_id="browser-a")


def test_standard_oauth_identity_needs_only_openid_and_unionid(wechat_settings):
    exchange_web_identity = getattr(wechat_web, "exchange_web_identity", None)
    assert callable(exchange_web_identity)
    client = FakeWechatClient(
        {
            "access_token": "server-access-token",
            "openid": "wechat-openid",
            "unionid": "wechat-unionid",
        }
    )

    identity = exchange_web_identity("browser-oauth-code", http_client=client)

    assert identity.openid == "wechat-openid"
    assert identity.unionid == "wechat-unionid"
    assert len(client.calls) == 1
    assert client.calls[0]["url"] == wechat_web.WECHAT_WEB_TOKEN_URL


def test_cache_set_error_fails_closed(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(cache, "set", unavailable)

    with pytest.raises(wechat_web.WebLoginStateError):
        wechat_web.create_web_login_state(
            requested_role="teacher",
            browser_session_id="browser-a",
        )


def test_cache_get_error_fails_closed(monkeypatch):
    state = wechat_web.create_web_login_state(
        requested_role="teacher",
        browser_session_id="browser-a",
    )

    def unavailable(*args, **kwargs):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(cache, "get", unavailable)

    with pytest.raises(wechat_web.WebLoginStateError):
        wechat_web.consume_web_login_state(state.value, browser_session_id="browser-a")


def test_cache_delete_error_fails_closed(monkeypatch):
    state = wechat_web.create_web_login_state(
        requested_role="teacher",
        browser_session_id="browser-a",
    )

    def unavailable(*args, **kwargs):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(cache, "delete", unavailable)

    with pytest.raises(wechat_web.WebLoginStateError):
        wechat_web.consume_web_login_state(state.value, browser_session_id="browser-a")


def test_oauth_exchange_does_not_log_code_or_access_token(wechat_settings, caplog):
    exchange_web_identity = getattr(wechat_web, "exchange_web_identity", None)
    assert callable(exchange_web_identity)
    oauth_code = "oauth-code-must-not-appear-in-logs"
    provider_token = "provider-token-must-not-appear-in-logs"
    client = FakeWechatClient(
        {
            "access_token": provider_token,
            "openid": "wechat-openid",
            "unionid": "wechat-unionid",
        }
    )
    caplog.set_level(logging.DEBUG, logger="apps.accounts.wechat_web")

    exchange_web_identity(oauth_code, http_client=client)

    assert oauth_code not in caplog.text
    assert provider_token not in caplog.text


def _browser_session_id(client):
    session = client.session
    session["wechat_web_binding_test"] = True
    session.save()
    return session.session_key


def _authenticated_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {generate_tokens(user, 'student')['access_token']}"
    )
    return client


def _user(mobile, role="student"):
    user = UserAccount.objects.create(
        mobile=mobile,
        role_type=role,
        display_name=f"User {mobile[-4:]}",
    )
    grant_user_role(user, role)
    return user


def _binding_session(browser_session_id, requested_role="student", suffix="1"):
    create_session = getattr(wechat_web, "create_web_binding_session", None)
    assert callable(create_session)
    return create_session(
        identity=wechat_web.WebIdentity(
            openid=f"web-openid-{suffix}", unionid=f"web-unionid-{suffix}"
        ),
        requested_role=requested_role,
        browser_session_id=browser_session_id,
    )


def test_web_binding_session_is_bound_to_its_originating_browser():
    """Dropping this guard would disclose a pending binding to a different browser."""
    session = _binding_session("browser-a", suffix="browser")
    get_status = getattr(wechat_web, "get_web_binding_status", None)
    assert callable(get_status)
    assert session.expires_in == 300

    with pytest.raises(wechat_web.WebBindingError):
        get_status(session.value, "browser-b")


def test_binding_bridge_code_is_single_use_and_opaque():
    session = _binding_session("browser-a", suffix="bridge")
    create = getattr(wechat_web, "create_web_binding_bridge_code", None)
    consume = getattr(wechat_web, "consume_web_binding_bridge_code", None)
    assert callable(create)
    assert callable(consume)

    code = create(session.value)
    assert len(code) <= 32
    assert consume(code) == session.value
    with pytest.raises(wechat_web.WebBindingError):
        consume(code)


@pytest.mark.django_db
def test_miniprogram_phone_authorization_binds_the_web_session(monkeypatch):
    """A phone code is verified only by WeChat's server API, never by H5."""
    browser = APIClient()
    session = _binding_session(_browser_session_id(browser), suffix="phone-code")
    bridge_code = wechat_web.create_web_binding_bridge_code(session.value)
    monkeypatch.setattr(
        views,
        "exchange_miniprogram_phone_code",
        lambda code: "13900009888",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-web/binding-phone",
        {"bridge_code": bridge_code, "phone_code": "wechat-phone-code"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"] == {"bound": True}
    assert WechatWebIdentity.objects.get().user.mobile == "13900009888"


@pytest.mark.django_db
def test_binding_qrcode_is_only_available_to_the_originating_browser(monkeypatch):
    browser = APIClient()
    session = _binding_session(_browser_session_id(browser), suffix="qrcode")
    monkeypatch.setattr(views, "wxacode_png", lambda **kwargs: b"png-data")

    denied = APIClient().get(
        "/api/v1/auth/wechat-web/binding-qrcode",
        {"web_session_id": session.value},
    )
    accepted = browser.get(
        "/api/v1/auth/wechat-web/binding-qrcode",
        {"web_session_id": session.value},
    )

    assert denied.status_code == 400
    assert accepted.status_code == 200
    assert accepted["Content-Type"] == "image/png"
    assert accepted.content == b"png-data"


def test_rewriting_binding_session_never_extends_its_initial_expiry(monkeypatch):
    """Resetting the cache timeout during binding must not make the session live longer."""
    clocked_cache = ClockedCache()
    monkeypatch.setattr(wechat_web, "cache", clocked_cache)
    monkeypatch.setattr(
        wechat_web.timezone,
        "now",
        lambda: datetime.fromtimestamp(clocked_cache.now, tz=datetime_timezone.utc),
    )
    session = _binding_session("browser-a", suffix="ttl")

    clocked_cache.now = 299
    payload = wechat_web._get_binding_session(session.value)
    payload["ticket"] = "opaque-ticket"
    wechat_web._set_binding_cache(wechat_web._binding_session_key(session.value), payload)

    clocked_cache.now = 300
    with pytest.raises(wechat_web.WebBindingError):
        wechat_web.get_web_binding_status(session.value, "browser-a")


def test_binding_session_accepts_standard_oauth_without_unionid(wechat_settings):
    """UnionID 是可选字段；网站应用必须能仅凭 AppID + OpenID 继续绑定。"""
    session = wechat_web.create_web_binding_session(
        identity=wechat_web.WebIdentity(
            openid="web-openid-blank-unionid", unionid=""
        ),
        requested_role="student",
        browser_session_id="browser-a",
    )

    assert session.value


def test_binding_complete_rejects_mobile_before_consuming_ticket(monkeypatch):
    """Removing this guard would allow the H5 body to carry an untrusted mobile."""
    request = APIRequestFactory().post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": "opaque-ticket", "requested_role": "student", "mobile": "13900009999"},
        format="json",
    )
    request.session = type("BrowserSession", (), {"session_key": "browser-a"})()
    monkeypatch.setattr(
        views,
        "complete_web_binding",
        lambda *args: (object(), {"access_token": "access", "refresh_token": "refresh"}),
    )
    monkeypatch.setattr(views, "serialize_user_session", lambda *args: {})

    response = views.wechat_web_binding_complete(request)

    assert response.status_code == 400
    assert response.data["code"] == "BINDING_MOBILE_NOT_ALLOWED"


@pytest.mark.django_db
def test_binding_endpoint_rejects_browser_posted_mobile_before_linking_identity():
    """Removing the payload guard would let a browser supply an untrusted mobile."""
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client))
    miniprogram_user = _user("13900009401")

    response = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value, "mobile": "13900009999"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "BINDING_MOBILE_NOT_ALLOWED"
    assert not WechatWebIdentity.objects.exists()


@pytest.mark.django_db
def test_binding_uses_authenticated_miniprogram_mobile_and_returns_login_envelope():
    """Using request data instead of the authenticated account would log in the wrong user."""
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client), suffix="2")
    miniprogram_user = _user("13900009402")

    binding = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value},
        format="json",
    )
    assert binding.status_code == 200
    assert binding.data["data"]["bound"] is True
    assert "mobile" not in binding.data["data"]

    status_response = h5_client.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": web_session.value},
    )
    assert status_response.status_code == 200
    ticket = status_response.data["data"]["ticket"]

    completed = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket},
        format="json",
    )

    assert completed.status_code == 200
    assert completed.data["code"] == 0
    assert completed.data["data"]["user"]["mobile"] == "13900009402"
    assert completed.data["data"]["user"]["active_role"] == "student"
    assert completed.data["data"]["access_token"]
    assert completed.data["data"]["refresh_token"]
    assert WechatWebIdentity.objects.get().user_id == miniprogram_user.id


@pytest.mark.django_db
def test_binding_ticket_rejects_other_browser_and_is_consumed_on_attempt():
    """Removing browser binding or delete-before-check would enable login CSRF/replay."""
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client), suffix="3")
    miniprogram_user = _user("13900009403")
    binding = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value},
        format="json",
    )
    assert binding.status_code == 200
    ticket = h5_client.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": web_session.value},
    ).data["data"]["ticket"]

    other_browser = APIClient()
    _browser_session_id(other_browser)
    cross_browser = other_browser.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "student"},
        format="json",
    )
    replay = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "student"},
        format="json",
    )

    assert cross_browser.status_code == 400
    assert cross_browser.data["code"] == "BINDING_TICKET_INVALID"
    assert replay.status_code == 400
    assert replay.data["code"] == "BINDING_TICKET_INVALID"


@pytest.mark.django_db
def test_binding_ticket_is_one_time_even_for_the_original_browser():
    """Removing ticket consumption would let a captured ticket mint multiple sessions."""
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client), suffix="4")
    miniprogram_user = _user("13900009404")
    binding = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value},
        format="json",
    )
    assert binding.status_code == 200
    ticket = h5_client.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": web_session.value},
    ).data["data"]["ticket"]

    first = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "student"},
        format="json",
    )
    replay = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "student"},
        format="json",
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    assert replay.data["code"] == "BINDING_TICKET_INVALID"


@pytest.mark.django_db
def test_binding_ticket_rejects_a_role_different_from_its_web_session():
    """Trusting a completion role would let a ticket switch the selected role."""
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client), suffix="role")
    miniprogram_user = _user("13900009405")
    binding = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value},
        format="json",
    )
    assert binding.status_code == 200
    ticket = h5_client.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": web_session.value},
    ).data["data"]["ticket"]

    response = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "teacher"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "BINDING_TICKET_INVALID"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["student", "parent"])
def test_trusted_mobile_login_creates_only_safe_first_roles(role):
    """Allowing every requested role would self-provision teacher/admin accounts."""
    login = getattr(wechat_web, "login_with_trusted_mobile", None)
    assert callable(login)

    user, tokens = login(f"1390000941{0 if role == 'student' else 1}", role)

    assert user.role_type == role
    assert has_user_role(user, role)
    assert tokens["access_token"]


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["teacher", "admin"])
def test_trusted_mobile_login_rejects_privileged_first_roles(role):
    """Changing the safe-role gate would create a privileged account from a phone number."""
    login = getattr(wechat_web, "login_with_trusted_mobile", None)
    assert callable(login)

    with pytest.raises(wechat_web.WebBindingError):
        login(f"1390000942{0 if role == 'teacher' else 1}", role)


@pytest.mark.django_db
def test_binding_fails_closed_when_web_identity_or_unionid_belongs_to_another_user():
    """Dropping either conflict check would attach a victim's web identity to another account."""
    h5_client = APIClient()
    browser_session_id = _browser_session_id(h5_client)
    owner = _user("13900009430")
    miniprogram_user = _user("13900009431")
    WechatWebIdentity.objects.create(
        user=owner,
        appid="web-test-app-id",
        openid="web-openid-conflict",
        unionid="web-unionid-conflict",
    )
    conflicting_session = _binding_session(
        browser_session_id, suffix="conflict"
    )

    with pytest.raises(wechat_web.WebBindingError):
        wechat_web.bind_web_identity_from_miniprogram(
            conflicting_session.value, miniprogram_user
        )


@pytest.mark.django_db
def test_binding_flow_never_calls_sms_services(monkeypatch):
    """Adding SMS fallback would cause this real binding flow to raise."""
    from apps.accounts import services

    def sms_must_not_run(*args, **kwargs):
        raise AssertionError("SMS must not be used for web binding")

    monkeypatch.setattr(services, "verify_code", sms_must_not_run)
    monkeypatch.setattr(services, "send_sms_code", sms_must_not_run)
    h5_client = APIClient()
    web_session = _binding_session(_browser_session_id(h5_client), suffix="sms")
    miniprogram_user = _user("13900009440")

    binding = _authenticated_client(miniprogram_user).post(
        "/api/v1/auth/wechat-web/binding-session",
        {"web_session_id": web_session.value},
        format="json",
    )
    assert binding.status_code == 200
    ticket = h5_client.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": web_session.value},
    ).data["data"]["ticket"]
    completed = h5_client.post(
        "/api/v1/auth/wechat-web/binding-complete",
        {"ticket": ticket, "requested_role": "student"},
        format="json",
    )

    assert completed.status_code == 200


@pytest.mark.django_db
def test_web_session_requires_a_valid_role_and_returns_an_expiring_authorization_url(
    wechat_settings,
):
    """Removing role validation or the server session would permit unsafe QR starts."""
    client = APIClient()

    invalid = client.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "operator"}, format="json"
    )
    response = client.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
    )

    assert invalid.status_code == 400
    assert invalid.data["code"] == "INVALID_ROLE"
    assert response.status_code == 200
    assert response.data["code"] == 0
    assert response.data["data"]["web_session_id"]
    assert response.data["data"]["expires_in"] == 300
    assert "https://open.weixin.qq.com/connect/qrconnect?" in response.data["data"]["authorization_url"]
    assert "state=" in response.data["data"]["authorization_url"]
    assert client.session.session_key


@pytest.mark.django_db
def test_web_session_requires_explicit_phone_binding_authorization_confirmation(
    wechat_settings,
):
    """扫码会话必须由用户明确确认手机号绑定授权后才可创建。"""
    client = APIClient()

    missing = client.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student"}, format="json"
    )
    denied = client.post(
        "/api/v1/auth/wechat-web/session", {
            "requested_role": "student", "phone_authorization_confirmed": False,
        }, format="json"
    )
    accepted = client.post(
        "/api/v1/auth/wechat-web/session", {
            "requested_role": "student", "phone_authorization_confirmed": True,
        }, format="json"
    )

    assert missing.status_code == 400
    assert denied.status_code == 400
    assert accepted.status_code == 200


@pytest.mark.django_db
def test_web_session_fails_closed_when_web_oauth_is_not_configured():
    """Dropping config checks would make an unusable provider URL look valid."""
    client = APIClient()

    with override_settings(
        WECHAT_WEB_APP_ID="", WECHAT_WEB_APP_SECRET="", WECHAT_WEB_REDIRECT_URI=""
    ):
        response = client.post(
            "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
        )

    assert response.status_code == 400
    assert response.data["code"] == "WECHAT_WEB_NOT_CONFIGURED"


@pytest.mark.django_db
def test_callback_requires_the_originating_browser_and_consumes_state(
    wechat_settings, monkeypatch
):
    """Dropping browser binding or one-time consumption would enable login CSRF."""
    browser = APIClient()
    session = browser.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
    ).data["data"]
    state = session["authorization_url"].split("state=", 1)[1].split("&", 1)[0].split("#", 1)[0]
    monkeypatch.setattr(
        views,
        "exchange_web_identity",
        lambda code: wechat_web.WebIdentity(openid="callback-openid", unionid="callback-unionid"),
    )

    other_browser = APIClient()
    rejected = other_browser.get(
        "/api/v1/auth/wechat-web/callback", {"code": "provider-code", "state": state}
    )
    replay = browser.get(
        "/api/v1/auth/wechat-web/callback", {"code": "provider-code", "state": state}
    )

    assert rejected.status_code == 400
    assert rejected.data["code"] == "WECHAT_WEB_CALLBACK_INVALID"
    assert replay.status_code == 400
    assert replay.data["code"] == "WECHAT_WEB_CALLBACK_INVALID"


@pytest.mark.django_db
def test_callback_rejects_an_unknown_state_without_echoing_oauth_values():
    """Accepting arbitrary state would let an attacker attach their OAuth response."""
    response = APIClient().get(
        "/api/v1/auth/wechat-web/callback",
        {"code": "provider-code-must-not-echo", "state": "unknown-state"},
    )

    assert response.status_code == 400
    assert response.data["code"] == "WECHAT_WEB_CALLBACK_INVALID"
    assert "provider-code-must-not-echo" not in str(response.data)


@pytest.mark.django_db
def test_binding_status_reports_pending_before_oauth_callback(wechat_settings):
    """The H5 poll starts before WeChat redirects back, so this is not an error."""
    browser = APIClient()
    session = browser.post(
        "/api/v1/auth/wechat-web/session",
        {"requested_role": "student", "phone_authorization_confirmed": True},
        format="json",
    ).data["data"]

    response = browser.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": session["web_session_id"]},
    )

    assert response.status_code == 200
    assert response.data["data"] == {"bound": False, "ticket": None}


@pytest.mark.django_db
def test_callback_redirect_never_leaks_provider_code_or_jwt_for_unbound_identity(
    wechat_settings, monkeypatch
):
    """Returning OAuth values in the redirect would expose credentials to H5 history."""
    browser = APIClient()
    session = browser.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
    ).data["data"]
    state = session["authorization_url"].split("state=", 1)[1].split("&", 1)[0].split("#", 1)[0]
    provider_code = "provider-code-must-not-leak"
    monkeypatch.setattr(
        views,
        "exchange_web_identity",
        lambda code: wechat_web.WebIdentity(openid="waiting-openid", unionid="waiting-unionid"),
    )

    response = browser.get(
        "/api/v1/auth/wechat-web/callback", {"code": provider_code, "state": state}
    )

    location = response["Location"]
    assert response.status_code == 302
    assert provider_code not in location
    assert "access_token" not in location
    assert "refresh_token" not in location
    assert "web_session_id=" in location


@pytest.mark.django_db
def test_callback_for_existing_web_identity_creates_a_login_ticket_without_jwt(
    wechat_settings, monkeypatch
):
    """Skipping the existing identity branch would unnecessarily force MP rebinding."""
    user = _user("13900009501")
    WechatWebIdentity.objects.create(
        user=user,
        appid="web-test-app-id",
        openid="known-openid",
        unionid="known-unionid",
    )
    browser = APIClient()
    session = browser.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
    ).data["data"]
    state = session["authorization_url"].split("state=", 1)[1].split("&", 1)[0].split("#", 1)[0]
    monkeypatch.setattr(
        views,
        "exchange_web_identity",
        lambda code: wechat_web.WebIdentity(openid="known-openid", unionid="known-unionid"),
    )

    callback = browser.get(
        "/api/v1/auth/wechat-web/callback", {"code": "provider-code", "state": state}
    )
    status_response = browser.get(
        "/api/v1/auth/wechat-web/binding-status",
        {"web_session_id": callback["Location"].split("web_session_id=", 1)[1]},
    )

    assert callback.status_code == 302
    assert "access_token" not in callback["Location"]
    assert status_response.data["data"]["bound"] is True
    assert status_response.data["data"]["ticket"]


@pytest.mark.django_db
def test_callback_returns_controlled_error_when_identity_exchange_fails(
    wechat_settings, monkeypatch
):
    """Letting provider failures escape would expose OAuth details in an error body."""
    browser = APIClient()
    session = browser.post(
        "/api/v1/auth/wechat-web/session", {"requested_role": "student", "phone_authorization_confirmed": True}, format="json"
    ).data["data"]
    state = session["authorization_url"].split("state=", 1)[1].split("&", 1)[0].split("#", 1)[0]
    monkeypatch.setattr(
        views,
        "exchange_web_identity",
        lambda code: (_ for _ in ()).throw(wechat_web.WebAuthorizationError("provider failed")),
    )

    response = browser.get(
        "/api/v1/auth/wechat-web/callback", {"code": "provider-code", "state": state}
    )

    assert response.status_code == 400
    assert response.data["code"] == "WECHAT_WEB_CALLBACK_INVALID"
    assert "provider-code" not in str(response.data)
