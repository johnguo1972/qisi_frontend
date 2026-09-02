from __future__ import annotations

import traceback

import pytest

from apps.common.exceptions import AIRequestError
from apps.study import photo_views


SENSITIVE_VALUES = (
    "https://bucket.example.test/private.png?OSSAccessKeyId=private-key&Signature=private-signature",
    r"C:\Users\private\exam.png",
    "/srv/private/exam.png",
    "data:image/png;base64,PRIVATE_BASE64_MARKER",
    "RAW_BYTES_MARKER",
)
UNSAFE_DETAIL = " | ".join(SENSITIVE_VALUES) + " | b'RAW_BYTES_MARKER'"


class UnsafePhotoComponent:
    def recognize_photo(self, _images):
        raise AIRequestError(UNSAFE_DETAIL)


def _assert_no_sensitive(value) -> None:
    rendered = str(value)
    for sensitive in SENSITIVE_VALUES:
        assert sensitive not in rendered


def _format_captured_locals(error: BaseException) -> str:
    return "".join(
        traceback.TracebackException(
            type(error),
            error,
            error.__traceback__,
            capture_locals=True,
        ).format()
    )


def test_photo_adapter_raises_chainless_safe_error_and_clears_locals(
    monkeypatch,
):
    monkeypatch.setattr(
        photo_views,
        "upload_crop_image_safe",
        lambda *_args, **_kwargs: SENSITIVE_VALUES[0],
    )
    monkeypatch.setattr(
        photo_views,
        "vision_parser_component_factory",
        lambda: UnsafePhotoComponent(),
    )

    with pytest.raises(
        AIRequestError,
        match=r"^PHOTO_RECOGNITION_FAILED: 图片识别失败$",
    ) as caught:
        photo_views._call_vision_api(list(SENSITIVE_VALUES))

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(caught.value)
    _assert_no_sensitive(_format_captured_locals(caught.value))
