from pathlib import Path

import pytest


LOGIN_PAGE = Path("uniapp/src/pages/login/index.vue")
API_CLIENT = Path("uniapp/src/api/wechat-web.ts")
API_INDEX = Path("uniapp/src/api/index.ts")


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
