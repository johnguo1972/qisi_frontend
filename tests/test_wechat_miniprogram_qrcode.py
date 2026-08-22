import requests
import pytest

from apps.qrcode import services


class _JsonResponse:
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _ImageResponse:
    headers = {"Content-Type": "image/jpeg"}
    content = b"jpeg-data"


def test_binding_page_qrcode_requires_a_published_miniprogram_page(
    monkeypatch, settings
):
    """A QR for an unpublished page must not be generated as if it were usable."""
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret-test"
    captured = {}

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _JsonResponse({"access_token": "token-test"}),
    )

    def fake_post(*args, **kwargs):
        captured.update(kwargs["json"])
        return _ImageResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    content = services.wxacode_png(
        scene="bridge-code",
        page="pages/auth/web-binding",
        width=430,
        check_path=True,
    )

    assert content == b"jpeg-data"
    assert captured["check_path"] is True
    assert captured["env_version"] == "release"


def test_qrcode_can_target_the_miniprogram_trial_version(monkeypatch, settings):
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret-test"
    captured = {}
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _JsonResponse({"access_token": "token-test"}),
    )

    def fake_post(*args, **kwargs):
        captured.update(kwargs["json"])
        return _ImageResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    services.wxacode_png(
        scene="bridge-code",
        page="pages/auth/web-binding",
        check_path=True,
        env_version="trial",
    )

    assert captured["env_version"] == "trial"


def test_qrcode_rejects_an_unknown_miniprogram_version(settings):
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret-test"

    with pytest.raises(RuntimeError, match="env_version"):
        services.wxacode_png(scene="bridge-code", env_version="unknown")
