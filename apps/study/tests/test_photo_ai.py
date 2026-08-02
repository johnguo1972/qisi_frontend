from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest

from apps.common import oss_service
from apps.study import photo_views


def _plain_view_handler(decorated_view):
    return decorated_view.cls.post.__closure__[0].cell_contents


def test_photo_adapter_keeps_oss_then_local_fallback_order(monkeypatch):
    uploaded = []

    def upload(path, prefix):
        uploaded.append((path, prefix))
        if path == "first-private.png":
            return "https://bucket.example.test/first.png?Signature=secret"
        return None

    class Component:
        def __init__(self):
            self.close_calls = 0

        def recognize_photo(self, images):
            assert images == [
                "https://bucket.example.test/first.png?Signature=secret",
                "second-private.png",
            ]
            return {"stem": "识别题干", "question_type": "short_answer"}

        def close(self):
            self.close_calls += 1

    component = Component()

    monkeypatch.setattr(photo_views, "upload_crop_image_safe", upload)
    monkeypatch.setattr(
        photo_views,
        "vision_parser_component_factory",
        lambda: component,
        raising=False,
    )

    result = photo_views._call_vision_api(
        ["first-private.png", "second-private.png"]
    )

    assert result == {"stem": "识别题干", "question_type": "short_answer"}
    assert uploaded == [
        ("first-private.png", "photo_questions"),
        ("second-private.png", "photo_questions"),
    ]
    assert component.close_calls == 1


def test_missing_crop_file_response_does_not_expose_local_path(
    monkeypatch, tmp_path
):
    missing_relative_path = "private/users/alice/crop.png"
    monkeypatch.setattr(photo_views.settings, "MEDIA_ROOT", tmp_path)
    request = SimpleNamespace(
        FILES=SimpleNamespace(getlist=lambda _name: []),
        POST={
            "paper_id": "",
            "crop_file_path": missing_relative_path,
            "page_no": "1",
        },
        user=SimpleNamespace(id=1),
    )

    response = _plain_view_handler(photo_views.photo_create_question)(request)

    assert response.status_code == 400
    assert response.data["code"] == 400
    assert response.data["message"] == "裁剪文件不存在"
    assert missing_relative_path not in str(response.data)


def test_photo_upload_failure_does_not_expose_saved_path_in_logs_or_response(
    monkeypatch, tmp_path, caplog
):
    private_path = str(tmp_path / "private-user" / "upload.png")
    monkeypatch.setattr(photo_views.settings, "MEDIA_ROOT", tmp_path)

    class Uploaded:
        name = "upload.png"

        def chunks(self):
            raise OSError(private_path)

    request = SimpleNamespace(
        FILES=SimpleNamespace(getlist=lambda _name: [Uploaded()]),
        POST={"paper_id": "", "crop_file_path": "", "page_no": "1"},
        user=SimpleNamespace(id=1),
    )
    caplog.set_level(logging.INFO)

    response = _plain_view_handler(photo_views.photo_create_question)(request)

    assert response.status_code == 500
    assert response.data["message"] == "识别失败，请稍后重试"
    assert private_path not in caplog.text + str(response.data)


def test_oss_failure_does_not_expose_local_path_or_signed_url(
    monkeypatch, tmp_path, caplog
):
    image_path = tmp_path / "private-local-image.png"
    image_path.write_bytes(b"image")
    signed_url = (
        "https://bucket.example.test/private?OSSAccessKeyId=private-key"
        "&Signature=private-signature"
    )

    class OssError(Exception):
        pass

    class Bucket:
        def put_object(self, _key, _file):
            raise OssError(signed_url)

    monkeypatch.setitem(
        sys.modules,
        "oss2",
        SimpleNamespace(exceptions=SimpleNamespace(OssError=OssError)),
    )
    monkeypatch.setattr(oss_service, "get_oss_client", lambda: Bucket())
    caplog.set_level(logging.INFO, logger="apps.common.oss_service")

    with pytest.raises(OSError) as caught:
        oss_service.upload_crop_image(str(image_path))

    combined = caplog.text + str(caught.value)
    for sensitive in (
        str(image_path),
        signed_url,
        "private-key",
        "private-signature",
    ):
        assert sensitive not in combined
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
