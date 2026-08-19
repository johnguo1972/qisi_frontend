import logging

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts import wechat_web
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
