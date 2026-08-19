import logging

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.accounts import wechat_web


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
