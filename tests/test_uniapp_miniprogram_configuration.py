import json
from pathlib import Path


def test_wechat_binding_source_uses_the_production_miniprogram_appid():
    """The QR bridge must target the same Mini Program that ships this page."""
    manifest = json.loads(
        Path("uniapp/src/manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["mp-weixin"]["appid"] == "wx86647a750a7727cb"
