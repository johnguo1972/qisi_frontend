from pathlib import Path


LOGIN_PAGE = Path("uniapp/src/pages/login/index.vue")
DEVICE_API = Path("uniapp/src/api/wechat-device.ts")
MINIPROGRAM_BINDING_PAGE = Path("uniapp/src/pages/auth/web-binding.vue")
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


def test_h5_shows_the_complete_device_code_before_the_consent_control():
    """The native image is visible without an iframe or a scroll container."""
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert 'class="device-qr-image"' in source
    assert ':src="wechatDeviceSession.qrcode_url"' in source
    assert source.index('class="device-qr-image-wrap"') < source.index('class="wechat-consent"')
    assert ".device-qr-image-wrap { width: 320px; height: 320px;" in source
    assert '<iframe' not in source


def test_h5_pending_status_does_not_claim_that_the_code_was_scanned():
    source = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "response.data.status === 'pending'" in source
    assert "请使用微信扫描二维码并在小程序中确认。" in source
    assert "phone_authorization_required" in source


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
