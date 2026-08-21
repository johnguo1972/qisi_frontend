from pathlib import Path

import pytest


LOGIN_PAGE = Path("uniapp/src/pages/login/index.vue")
API_CLIENT = Path("uniapp/src/api/wechat-web.ts")
API_INDEX = Path("uniapp/src/api/index.ts")
MINIPROGRAM_BINDING_PAGE = Path("uniapp/src/pages/auth/web-binding.vue")
PAGES_CONFIG = Path("uniapp/src/pages.json")


@pytest.fixture(autouse=True)
def ensure_unmanaged_knowledge_table():
    """Static source contracts need no Django database setup."""
    yield


def test_h5_wechat_binding_login_ui_contract():
    """H5 guides an unbound web identity to MP authorization without phone data."""
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "微信扫码登录" in source
    assert "请在微信小程序完成手机号授权" in source
    assert "#ifdef H5" in source
    assert "#ifdef MP-WEIXIN" in source
    assert "persistSession" in source
    assert "routeForRole" in source
    assert "activeTab.value" in source
    assert "wechatWebApi.createSession" in source
    assert "wechatWebApi.bindingStatus" in source
    assert "wechatWebApi.complete" in source
    assert "wechatWebPhoneAuthorizationConfirmed" in source
    assert "手机号绑定授权确认" in source
    assert "const loginMode = ref<'phone' | 'wechat'>('phone')" in source
    assert "v-if=\"loginMode === 'phone'\"" in source
    assert "v-else" in source
    assert "switchLoginMode('wechat')" in source
    assert "switchLoginMode('phone')" in source
    assert "@click.stop=\"switchRole(tab.role)\"" in source
    assert "overflow: hidden" in source
    assert "scrolling=\"no\"" in source
    assert "restoreWechatWebSessionFromCallback" in source
    assert "web_session_id" in source
    assert "window.location.assign(res.data.authorization_url)" in source
    assert "<iframe" not in source


def test_h5_wechat_qr_view_keeps_the_full_code_visible_and_consent_below_it():
    """The QR-only page must not crop WeChat's code or place consent above it."""
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert 'class="wechat-web-title"' not in source
    assert 'class="wechat-web-desc"' not in source
    assert source.index('class="wechat-web-qr"') < source.index('class="wechat-web-consent"')
    assert "width: 360px" in source
    assert "height: 420px" in source
    assert '<iframe' not in source


def test_wechat_web_api_only_exchanges_opaque_session_and_ticket_values():
    """The H5 API client never submits, stores, or models a mobile number."""
    source = API_CLIENT.read_text(encoding="utf-8")
    index = API_INDEX.read_text(encoding="utf-8")

    assert "createSession" in source
    assert "bindingStatus" in source
    assert "complete" in source
    assert "/auth/wechat-web/session" in source
    assert "/auth/wechat-web/binding-status" in source
    assert "/auth/wechat-web/binding-complete" in source
    assert "mobile" not in source.lower()
    assert "wechatWebApi" in index
    assert "phone_authorization_confirmed" in source


def test_miniprogram_phone_bridge_uses_wechat_authorization_code_only():
    source = MINIPROGRAM_BINDING_PAGE.read_text(encoding="utf-8")
    pages = PAGES_CONFIG.read_text(encoding="utf-8")
    assert 'open-type="getPhoneNumber"' in source
    assert "event?.detail?.code" in source
    assert "/auth/wechat-web/binding-phone" in source
    assert "bridge_code" in source and "phone_code" in source
    assert "mobile" not in source
    assert "pages/auth/web-binding" in pages
