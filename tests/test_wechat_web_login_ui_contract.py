from pathlib import Path


LOGIN_PAGE = Path("uniapp/src/pages/login/index.vue")
DEVICE_API = Path("uniapp/src/api/wechat-device.ts")
MINIPROGRAM_BINDING_PAGE = Path("uniapp/src/pages/auth/web-binding.vue")
APP_PAGE = Path("uniapp/src/App.vue")
PAGES_CONFIG = Path("uniapp/src/pages.json")


def test_h5_uses_the_direct_device_qr_login_contract():
    """H5 owns only an opaque device session and never navigates through OAuth."""
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "wechatDeviceApi.createSession" in source
    assert "wechatDeviceApi.status" in source
    assert "wechatDeviceApi.complete" in source
    assert "wechatDeviceSession.qrcode_url" in source
    assert "window.location.assign" not in source
    assert "<iframe" not in source


def test_h5_shows_the_complete_device_code_and_refreshes_without_extra_consent():
    """The QR starts automatically; users only need to scan it once."""
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert 'class="device-qr-image"' in source
    assert ':src="wechatDeviceSession.qrcode_url"' in source
    assert '@load="handleWechatQrLoad"' in source
    assert '@error="handleWechatQrError"' in source
    assert 'device-qr-image-hidden' in source
    assert 'class="wechat-refresh-btn"' in source
    assert 'phoneAuthorizationConfirmed' not in source
    assert 'startWechatDeviceLogin' not in source
    assert ".device-qr-image-wrap {" in source
    assert "width: 320px; height: 320px;" in source
    assert '<iframe' not in source


def test_h5_login_page_defaults_to_wechat_qr_login():
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "loginMode.value = 'wechat'" in source
    assert "if (loginMode.value === 'wechat') void createWechatDeviceSession()" in source


def test_h5_pending_status_does_not_claim_that_the_code_was_scanned():
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "response.data.status === 'pending'" in source
    assert "请使用微信扫描二维码并在小程序中确认。" in source
    assert "phone_authorization_required" in source


def test_h5_handles_expired_sessions_and_browser_login_errors_explicitly():
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "DEVICE_SESSION_EXPIRED" in source
    assert "DEVICE_BROWSER_MISMATCH" in source
    assert "await createWechatDeviceSession()" in source
    assert "stopWechatDevicePolling()" in source


def test_h5_device_api_only_exchanges_opaque_session_and_ticket_values():
    """The browser never receives or submits a phone number during device login."""
    source = DEVICE_API.read_text(encoding="utf-8")

    assert "createSession" in source
    assert "status" in source
    assert "complete" in source
    assert "/auth/wechat-device/session" in source
    assert "/auth/wechat-device/status" in source
    assert "/auth/wechat-device/complete" in source
    assert "mobile" not in source.lower()


def test_miniprogram_binding_page_confirms_identity_and_uses_phone_code_only():
    source = MINIPROGRAM_BINDING_PAGE.read_text(encoding="utf-8")
    pages = PAGES_CONFIG.read_text(encoding="utf-8")

    assert 'open-type="getPhoneNumber"' in source
    assert "event?.detail?.code" in source
    assert "/auth/wechat-device/scan" in source
    assert "/auth/wechat-device/phone" in source
    assert "bridge_code" in source and "phone_code" in source
    assert "pages/auth/web-binding" in pages


def test_miniprogram_binding_page_explains_single_use_qr_errors():
    source = MINIPROGRAM_BINDING_PAGE.read_text(encoding="utf-8")

    assert "DEVICE_BRIDGE_INVALID" in source
    assert "不要重复扫码" in source


def test_miniprogram_binding_page_is_a_standalone_success_state_page():
    source = MINIPROGRAM_BINDING_PAGE.read_text(encoding="utf-8")
    app = APP_PAGE.read_text(encoding="utf-8")

    assert "bindingState" in source
    assert "微信授权成功" in source
    assert "请返回电脑网页继续使用" in source
    assert "auth/web-binding" in app
    assert "launchPath" in app


def test_miniprogram_one_click_login_contract_remains_unchanged():
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert 'open-type="getPhoneNumber"' in source
    assert '@getphonenumber="handleWechatPhoneLogin"' in source
    assert "wechatApi.phoneLogin(loginCode, phoneCode, activeTab.value)" in source
