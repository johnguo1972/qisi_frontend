import logging

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.accounts.wechat_web import (
    WebAuthorization,
    WebAuthorizationError,
    WebConfigurationError,
    WebLoginStateError,
    consume_login_ticket,
    consume_web_callback,
    consume_web_login_state,
    create_web_login_state,
    issue_login_ticket,
)


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
    def __init__(self, token_payload, profile_payload):
        self.responses = [FakeResponse(token_payload), FakeResponse(profile_payload)]
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def isolate_cache():
    with override_settings(CACHES=TEST_CACHES):
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


def test_state_is_single_use_and_has_a_five_minute_ttl(monkeypatch):
    recorded_timeouts = []
    original_set = cache.set

    def record_state_timeout(key, value, timeout=None, version=None):
        if key.startswith("wechat_web:state:"):
            recorded_timeouts.append(timeout)
        return original_set(key, value, timeout=timeout, version=version)

    monkeypatch.setattr(cache, "set", record_state_timeout)
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")

    consumed = consume_web_login_state(state.value)

    assert consumed.requested_role == "teacher"
    assert consumed.redirect_path == "/teacher"
    assert state.expires_in == 300
    assert recorded_timeouts == [300]
    with pytest.raises(WebLoginStateError, match="state_invalid_or_expired"):
        consume_web_login_state(state.value)


def test_ticket_is_single_use_and_has_a_five_minute_ttl(monkeypatch):
    authorization = WebAuthorization(
        requested_role="teacher",
        redirect_path="/teacher",
        appid="web-test-app-id",
        openid="wechat-openid",
        unionid="wechat-unionid",
        mobile="13800000001",
        phone_authorization_confirmed=True,
    )
    recorded_timeouts = []
    original_set = cache.set

    def record_ticket_timeout(key, value, timeout=None, version=None):
        if key.startswith("wechat_web:ticket:"):
            recorded_timeouts.append(timeout)
        return original_set(key, value, timeout=timeout, version=version)

    monkeypatch.setattr(cache, "set", record_ticket_timeout)
    ticket = issue_login_ticket(authorization)

    assert consume_login_ticket(ticket) == authorization
    assert recorded_timeouts == [300]
    with pytest.raises(WebAuthorizationError, match="ticket_invalid_or_expired"):
        consume_login_ticket(ticket)


def test_callback_rejects_a_phone_not_confirmed_by_wechat(wechat_settings):
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")
    client = FakeWechatClient(
        {"access_token": "server-access-token", "openid": "wechat-openid"},
        {
            "openid": "wechat-openid",
            "phone_number": "13800000001",
            "phone_authorization_confirmed": False,
        },
    )

    with pytest.raises(WebAuthorizationError, match="phone_authorization_required"):
        consume_web_callback("browser-oauth-code", state.value, http_client=client)


def test_callback_uses_only_wechat_confirmed_phone(wechat_settings):
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")
    client = FakeWechatClient(
        {"access_token": "server-access-token", "openid": "wechat-openid"},
        {
            "openid": "wechat-openid",
            "unionid": "wechat-unionid",
            "phone_number": "13800000001",
            "phone_authorization_confirmed": True,
        },
    )

    authorization = consume_web_callback(
        "browser-oauth-code", state.value, http_client=client
    )

    assert authorization.mobile == "13800000001"
    assert authorization.phone_authorization_confirmed is True
    assert authorization.requested_role == "teacher"


def test_callback_configuration_failure_is_closed_and_makes_no_provider_call():
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")
    client = FakeWechatClient(
        {"access_token": "server-access-token", "openid": "wechat-openid"},
        {"phone_number": "13800000001", "phone_authorization_confirmed": True},
    )

    with override_settings(
        WECHAT_WEB_APP_ID="",
        WECHAT_WEB_APP_SECRET="",
        WECHAT_WEB_REDIRECT_URI="",
    ):
        with pytest.raises(WebConfigurationError, match="wechat_web_not_configured"):
            consume_web_callback("browser-oauth-code", state.value, http_client=client)

    assert client.calls == []


def test_configuration_failure_still_consumes_callback_state():
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")
    client = FakeWechatClient(
        {"access_token": "server-access-token", "openid": "wechat-openid"},
        {"phone_number": "13800000001", "phone_authorization_confirmed": True},
    )

    with override_settings(
        WECHAT_WEB_APP_ID="",
        WECHAT_WEB_APP_SECRET="",
        WECHAT_WEB_REDIRECT_URI="",
    ):
        with pytest.raises(WebConfigurationError, match="wechat_web_not_configured"):
            consume_web_callback("browser-oauth-code", state.value, http_client=client)

    with override_settings(
        WECHAT_WEB_APP_ID="web-test-app-id",
        WECHAT_WEB_APP_SECRET="web-test-secret",
        WECHAT_WEB_REDIRECT_URI="https://example.test/auth/wechat/callback",
    ):
        with pytest.raises(WebLoginStateError, match="state_invalid_or_expired"):
            consume_web_callback("browser-oauth-code", state.value, http_client=client)

    assert client.calls == []


def test_ticket_callback_does_not_log_oauth_code_or_provider_token(wechat_settings, caplog):
    oauth_code = "oauth-code-must-not-appear-in-logs"
    provider_token = "provider-token-must-not-appear-in-logs"
    state = create_web_login_state(requested_role="teacher", redirect_path="/teacher")
    client = FakeWechatClient(
        {"access_token": provider_token, "openid": "wechat-openid"},
        {
            "phone_number": "13800000001",
            "phone_authorization_confirmed": True,
        },
    )
    caplog.set_level(logging.DEBUG, logger="apps.accounts.wechat_web")

    consume_web_callback(oauth_code, state.value, http_client=client)

    assert oauth_code not in caplog.text
    assert provider_token not in caplog.text
