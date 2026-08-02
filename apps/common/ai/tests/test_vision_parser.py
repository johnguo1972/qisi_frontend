from __future__ import annotations

import base64
import json
import logging
import traceback
from io import BytesIO

import pytest
from PIL import Image

from apps.common.ai.components.vision_parser import VisionParserComponent
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.image_codec import (
    MAX_IMAGE_BYTES,
    encode_image_source,
    prepare_image_sources,
)
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError


SIGNED_URL = (
    "https://bucket.example.test/page.png?OSSAccessKeyId=private-key"
    "&Signature=private-signature"
)


def _write_image(path, *, size=(2000, 1000), image_format="PNG"):
    Image.new("RGB", size, color=(20, 40, 60)).save(path, format=image_format)


class RecordingPromptRegistry:
    def __init__(self):
        self.calls = []

    def render(self, task_key, **variables):
        self.calls.append((task_key, variables))
        return f"system:{task_key}", f"user:{task_key}"


class RecordingAIClient:
    def __init__(self, responses=None, error=None):
        self.responses = responses or {}
        self.error = error
        self.calls = []

    def complete(self, task_key, **kwargs):
        self.calls.append((task_key, kwargs))
        if self.error is not None:
            raise self.error
        content = self.responses.get(task_key, "{}")
        return AIResult(
            content=content,
            provider="qwen",
            model=(
                "qwen3.7-plus"
                if task_key == "vision_position_detect"
                else "qwen3-vl-plus"
            ),
            latency_ms=37,
            raw_response={
                "id": f"response-{task_key}",
                "choices": [{"message": {"content": content}}],
            },
        )


def test_local_image_is_validated_resized_and_encoded_as_jpeg(tmp_path):
    image_path = tmp_path / "large.png"
    _write_image(image_path)

    data_url = encode_image_source(str(image_path))

    assert data_url.startswith("data:image/jpeg;base64,")
    encoded = data_url.partition(",")[2]
    with Image.open(BytesIO(base64.b64decode(encoded))) as compressed:
        assert compressed.format == "JPEG"
        assert compressed.mode == "RGB"
        assert compressed.size == (1600, 800)


def test_http_images_pass_through_and_multiple_sources_keep_input_order(
    tmp_path,
):
    local_path = tmp_path / "two.png"
    _write_image(local_path, size=(40, 20))

    prepared = prepare_image_sources(
        [SIGNED_URL, str(local_path), "http://example.test/three.webp"]
    )

    assert prepared[0] == SIGNED_URL
    assert prepared[1].startswith("data:image/jpeg;base64,")
    assert prepared[2] == "http://example.test/three.webp"


@pytest.mark.parametrize(
    "source_factory",
    [
        lambda tmp_path: str(tmp_path / "missing-private-name.png"),
        lambda tmp_path: "file:///private/hidden.png",
        lambda tmp_path: "ftp://user:password@example.test/private.png",
    ],
)
def test_invalid_image_sources_are_rejected_without_exposing_source(
    tmp_path, source_factory
):
    source = source_factory(tmp_path)

    with pytest.raises(AIRequestError) as caught:
        encode_image_source(source)

    assert source not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_unsupported_and_oversize_local_images_are_rejected_safely(tmp_path):
    unsupported = tmp_path / "private-document.txt"
    unsupported.write_text("not an image", encoding="utf-8")
    oversize = tmp_path / "private-oversize.png"
    with oversize.open("wb") as output:
        output.truncate(MAX_IMAGE_BYTES + 1)

    for image_path in (unsupported, oversize):
        with pytest.raises(AIRequestError) as caught:
            encode_image_source(str(image_path))
        assert str(image_path) not in str(caught.value)
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None


def test_multi_image_codec_failure_traceback_does_not_retain_encoded_image(
    tmp_path,
):
    image_path = tmp_path / "first-private.png"
    _write_image(image_path, size=(40, 20))
    encoded = encode_image_source(str(image_path))

    with pytest.raises(AIRequestError) as caught:
        prepare_image_sources(
            [str(image_path), "ftp://private.example.test/second.png"]
        )

    formatted = "".join(
        traceback.TracebackException(
            type(caught.value),
            caught.value,
            caught.value.__traceback__.tb_next,
            capture_locals=True,
        ).format()
    )
    assert encoded not in formatted


def test_detect_positions_uses_registry_client_parser_and_keeps_audit_fields(
    tmp_path,
):
    image_path = tmp_path / "page.png"
    _write_image(image_path, size=(40, 20))
    content = '{"page_no": 1, "questions": [{"question_no": "1"}]}'
    client = RecordingAIClient({"vision_position_detect": content})
    registry = RecordingPromptRegistry()

    result = VisionParserComponent(client, registry).detect_positions(
        str(image_path)
    )

    assert registry.calls == [("vision_position_detect", {})]
    assert client.calls[0][0] == "vision_position_detect"
    assert client.calls[0][1]["system"] == "system:vision_position_detect"
    assert client.calls[0][1]["user"] == "user:vision_position_detect"
    assert len(client.calls[0][1]["images"]) == 1
    assert client.calls[0][1]["images"][0].startswith(
        "data:image/jpeg;base64,"
    )
    assert result == {
        "raw_response": content,
        "response_json": json.dumps(
            {
                "id": "response-vision_position_detect",
                "choices": [{"message": {"content": content}}],
            },
            ensure_ascii=False,
        ),
        "latency_ms": 37,
        "parsed": {"page_no": 1, "questions": [{"question_no": "1"}]},
        "provider": "qwen",
        "model": "qwen3.7-plus",
    }


def test_parse_page_uses_page_task_and_parses_json_object():
    content = '{"page_no": 2, "questions": []}'
    client = RecordingAIClient({"vision_page_parse": content})
    registry = RecordingPromptRegistry()

    result = VisionParserComponent(client, registry).parse_page(SIGNED_URL)

    assert registry.calls == [("vision_page_parse", {})]
    assert client.calls[0][0] == "vision_page_parse"
    assert client.calls[0][1]["images"] == (SIGNED_URL,)
    assert result["parsed"] == {"page_no": 2, "questions": []}


def test_parse_question_preserves_multimage_order_and_all_prompt_context():
    content = '{"question_no": "8", "stem": "题干"}'
    client = RecordingAIClient({"vision_question_parse": content})
    registry = RecordingPromptRegistry()
    context = {
        "question_no": "8",
        "question_type": "single_choice",
        "question_type_label": "单选题",
        "section_title": "一、选择题",
        "page_start": 2,
        "page_end": 3,
        "multi_page_notice": "跨页提示",
    }

    result = VisionParserComponent(client, registry).parse_question(
        [SIGNED_URL, "https://example.test/page-3.png"], context
    )

    assert registry.calls == [("vision_question_parse", context)]
    assert client.calls[0] == (
        "vision_question_parse",
        {
            "system": "system:vision_question_parse",
            "user": "user:vision_question_parse",
            "images": (
                SIGNED_URL,
                "https://example.test/page-3.png",
            ),
            "trace_id": None,
        },
    )
    assert result["parsed"] == {"question_no": "8", "stem": "题干"}


def test_photo_and_fact_methods_parse_objects_through_their_fixed_tasks():
    client = RecordingAIClient(
        {
            "photo_recognize": '{"stem": "识别题干", "difficulty": 3}',
            "vision_fact_extract": (
                '{"subject": "math", "figure_present": false}'
            ),
        }
    )
    registry = RecordingPromptRegistry()
    component = VisionParserComponent(client, registry)

    photo = component.recognize_photo(
        [SIGNED_URL, "https://example.test/second.png"]
    )
    facts = component.extract_facts([SIGNED_URL], "规范化题干")

    assert photo == {"stem": "识别题干", "difficulty": 3}
    assert facts == {"subject": "math", "figure_present": False}
    assert registry.calls == [
        ("photo_recognize", {}),
        ("vision_fact_extract", {"normalized_text": "规范化题干"}),
    ]
    assert [call[0] for call in client.calls] == [
        "photo_recognize",
        "vision_fact_extract",
    ]


def test_course_material_recognition_uses_fixed_task_and_strict_schema():
    content = json.dumps(
        {
            "question_type": "single_choice",
            "stem": "若 x+1=2，则 x 等于多少？",
            "options": {"A": "0", "B": "1", "C": "2", "D": "3"},
            "answer": "B",
            "analysis": "移项可得 x=1。",
            "difficulty": 2,
            "knowledge_points": ["一元一次方程"],
            "images": [],
        },
        ensure_ascii=False,
    )
    client = RecordingAIClient({"course_material_recognize": content})
    registry = RecordingPromptRegistry()

    result = VisionParserComponent(
        client, registry
    ).recognize_course_material([SIGNED_URL])

    assert result == json.loads(content)
    assert registry.calls == [("course_material_recognize", {})]
    assert client.calls[0][0] == "course_material_recognize"
    assert client.calls[0][1]["images"] == (SIGNED_URL,)


def test_course_material_recognition_rejects_incomplete_success_schema():
    client = RecordingAIClient(
        {"course_material_recognize": '{"question_type":"single_choice"}'}
    )

    with pytest.raises(AIResponseError, match="schema"):
        VisionParserComponent(
            client, RecordingPromptRegistry()
        ).recognize_course_material([SIGNED_URL])


def test_course_material_recognition_preserves_explicit_no_question_error():
    client = RecordingAIClient(
        {"course_material_recognize": '{"error":"未识别到试题"}'}
    )

    result = VisionParserComponent(
        client, RecordingPromptRegistry()
    ).recognize_course_material([SIGNED_URL])

    assert result == {"error": "未识别到试题"}


def test_non_object_vision_response_is_an_explicit_response_error():
    client = RecordingAIClient({"photo_recognize": '[{"stem": "题干"}]'})

    with pytest.raises(AIResponseError, match="object"):
        VisionParserComponent(
            client, RecordingPromptRegistry()
        ).recognize_photo([SIGNED_URL])


def test_component_does_not_leak_images_signed_query_or_local_path_on_failure(
    tmp_path, caplog
):
    image_path = tmp_path / "private-local-name.png"
    _write_image(image_path, size=(40, 20))
    private_data_url = encode_image_source(str(image_path))
    client = RecordingAIClient(
        error=AIRequestError(
            f"provider echoed {SIGNED_URL} {private_data_url} {image_path}"
        )
    )
    caplog.set_level(logging.DEBUG)

    with pytest.raises(AIRequestError) as caught:
        VisionParserComponent(
            client, RecordingPromptRegistry()
        ).recognize_photo([SIGNED_URL, str(image_path)])

    combined = caplog.text + str(caught.value)
    for sensitive in (
        SIGNED_URL,
        "private-key",
        "private-signature",
        private_data_url,
        str(image_path),
    ):
        assert sensitive not in combined
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_component_failure_traceback_locals_do_not_retain_image_sources(
    tmp_path,
):
    image_path = tmp_path / "private-traceback-local.png"
    _write_image(image_path, size=(40, 20))
    client = RecordingAIClient(error=AIRequestError("provider failed"))

    with pytest.raises(AIRequestError) as caught:
        VisionParserComponent(
            client, RecordingPromptRegistry()
        ).recognize_photo([SIGNED_URL, str(image_path)])

    formatted = "".join(
        traceback.TracebackException(
            type(caught.value),
            caught.value,
            caught.value.__traceback__,
            capture_locals=True,
        ).format()
    )
    assert SIGNED_URL not in formatted
