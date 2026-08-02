from __future__ import annotations

import base64
import hashlib
import io
import traceback

import httpx
import pytest
from PIL import Image

from apps.common.ai import client as client_module
from apps.common.ai import image_codec
from apps.common.ai.components import (
    ModeAAnswerComponent,
    QuestionComponentFactory,
    QuestionInput,
    VariantGeneratorComponent,
    VisionParserComponent,
)
from apps.common.ai.config import reset_ai_config_for_tests
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError
from apps.courses import ai_service as course_ai_service


def _png_data_uri(*, size: tuple[int, int] = (12, 8)) -> str:
    output = io.BytesIO()
    Image.new("RGB", size, color="white").save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(
        output.getvalue()
    ).decode("ascii")


def _provider_env(monkeypatch, *, key: str = "final-fix-private-key"):
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("QWEN_API_KEY", key)
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    reset_ai_config_for_tests()


def _capture_facade_locals(facade) -> str:
    try:
        local_facade = facade
        raise RuntimeError("fixed safe error")
    except RuntimeError as error:
        formatted = "".join(
            traceback.TracebackException(
                type(error), error, error.__traceback__, capture_locals=True
            ).format()
        )
    assert local_facade is facade
    return formatted


def test_data_image_uri_is_strictly_decoded_validated_and_normalized():
    source = _png_data_uri()

    prepared = image_codec.encode_image_source(source)

    assert prepared.startswith("data:image/jpeg;base64,")
    assert prepared != source
    with Image.open(
        io.BytesIO(base64.b64decode(prepared.partition(",")[2], validate=True))
    ) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.size == (12, 8)


@pytest.mark.parametrize(
    "source",
    [
        "data:text/plain;base64,SGVsbG8=",
        "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
        "data:image/png;base64,not valid base64!",
        "data:image/png;utf8,AAAA",
    ],
)
def test_data_image_uri_rejects_mime_and_encoding_attacks_without_echo(source):
    with pytest.raises(AIRequestError) as caught:
        image_codec.encode_image_source(source)

    assert source not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_data_image_uri_rejects_byte_and_pixel_limit_overruns(monkeypatch):
    source = _png_data_uri(size=(20, 20))

    monkeypatch.setattr(image_codec, "MAX_IMAGE_BYTES", 8)
    with pytest.raises(AIRequestError, match="large"):
        image_codec.encode_image_source(source)

    monkeypatch.setattr(image_codec, "MAX_IMAGE_BYTES", 1024 * 1024)
    monkeypatch.setattr(image_codec, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(AIRequestError, match="dimensions"):
        image_codec.encode_image_source(source)


def test_retired_course_api_exposes_only_structured_component_entrypoints():
    service = course_ai_service.VariantAIService()

    assert not hasattr(course_ai_service, "call_ai")
    assert not hasattr(course_ai_service, "get_deepseek_api_key")
    assert not hasattr(service, "call_ai")
    assert not hasattr(service, "get_deepseek_api_key")


def test_facade_does_not_retain_key_in_attributes_repr_or_capture_locals(
    monkeypatch,
):
    private_key = "final-fix-private-key"
    _provider_env(monkeypatch, key=private_key)

    from apps.common.ai_service import AIReviewService

    facade = AIReviewService(component_factory=lambda component_type: component_type)
    try:
        assert "api_key" not in vars(facade)
        assert "_config" not in vars(facade)
        assert "_config" not in vars(facade._prompt_registry)
        assert all(
            private_key not in repr(value) for value in vars(facade).values()
        )
        assert private_key not in repr(facade)

        formatted = _capture_facade_locals(facade)
        assert private_key not in formatted
    finally:
        facade.close()
        reset_ai_config_for_tests()


def test_ai_save_logs_field_metadata_without_ai_content(monkeypatch, caplog):
    import logging

    from apps.common.ai_service import AIReviewService
    from apps.parser.models import ExamQuestion

    sensitive = (
        "13812345678 token=PRIVATE_TOKEN "
        "data:image/png;base64,PRIVATE_DATA "
        "https://cdn.example.test/a.png?Signature=PRIVATE_SIGNATURE "
        "provider raw answer"
    )

    class Question:
        ai_answer_a = None
        ai_answer_b = None
        ai_answer_c = None
        subject = "math"
        difficulty = 3

        def save(self):
            return None

    question = Question()
    monkeypatch.setattr(ExamQuestion.objects, "get", lambda **_kwargs: question)
    caplog.set_level(logging.DEBUG, logger="apps.common.ai_service")

    service = AIReviewService.__new__(AIReviewService)
    service.save_results_to_question(
        7,
        {
            "answer_a": {
                "steps": [sensitive],
                "final_answer": sensitive,
                "summary": sensitive,
            }
        },
    )

    assert sensitive not in caplog.text
    for marker in (
        "13812345678",
        "PRIVATE_TOKEN",
        "PRIVATE_DATA",
        "PRIVATE_SIGNATURE",
        "provider raw answer",
    ):
        assert marker not in caplog.text


class _CloseCountingClient:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1

    def complete(self, *_args, **_kwargs):
        raise AssertionError("network must not be called")


class _FalseyCloseCountingClient(_CloseCountingClient):
    def __bool__(self):
        return False


@pytest.mark.parametrize(
    ("module_path", "component_type"),
    [
        ("apps.common.ai.components.vision_parser", VisionParserComponent),
        ("apps.common.ai.components.variant_generator", VariantGeneratorComponent),
    ],
)
def test_default_component_owns_and_idempotently_closes_its_client(
    monkeypatch, module_path, component_type
):
    created = []

    def create_client():
        client = _CloseCountingClient()
        created.append(client)
        return client

    monkeypatch.setattr(f"{module_path}.AIClient", create_client)

    with component_type() as component:
        assert component is not None
    component.close()

    assert len(created) == 1
    assert created[0].close_calls == 1


@pytest.mark.parametrize(
    "component_type", [VisionParserComponent, VariantGeneratorComponent]
)
def test_component_never_closes_a_borrowed_client(component_type):
    borrowed = _CloseCountingClient()

    with component_type(borrowed):
        pass

    assert borrowed.close_calls == 0


@pytest.mark.parametrize(
    "component_type",
    [ModeAAnswerComponent, VisionParserComponent, VariantGeneratorComponent],
)
def test_falsey_borrowed_client_is_never_replaced_or_closed(component_type):
    borrowed = _FalseyCloseCountingClient()

    component = component_type(borrowed)
    component.close()

    assert component._ai_client is borrowed
    assert borrowed.close_calls == 0


def test_question_component_factory_owns_default_but_not_borrowed_client(
    monkeypatch,
):
    created = _CloseCountingClient()
    monkeypatch.setattr(
        "apps.common.ai.components.base.AIClient", lambda: created
    )

    with QuestionComponentFactory() as owned_factory:
        assert owned_factory is not None
    owned_factory.close()
    assert created.close_calls == 1

    borrowed = _CloseCountingClient()
    with QuestionComponentFactory(borrowed):
        pass
    assert borrowed.close_calls == 0

    falsey_borrowed = _FalseyCloseCountingClient()
    with QuestionComponentFactory(falsey_borrowed) as factory:
        assert factory._ai_client is falsey_borrowed
    assert falsey_borrowed.close_calls == 0


def test_facade_context_manager_closes_owned_client_once_on_exception(
    monkeypatch,
):
    _provider_env(monkeypatch)
    created = _CloseCountingClient()
    monkeypatch.setattr("apps.common.ai_service.AIClient", lambda: created)

    from apps.common.ai_service import AIReviewService

    with pytest.raises(RuntimeError, match="boom"):
        with AIReviewService() as service:
            assert service._provider_client() is created
            raise RuntimeError("boom")
    service.close()

    assert created.close_calls == 1
    reset_ai_config_for_tests()


def test_facade_never_closes_a_borrowed_component_factory(monkeypatch):
    _provider_env(monkeypatch)

    class BorrowedFactory:
        def __init__(self):
            self.close_calls = 0

        def __call__(self, component_type):
            return component_type

        def close(self):
            self.close_calls += 1

    from apps.common.ai_service import AIReviewService

    borrowed = BorrowedFactory()
    with AIReviewService(component_factory=borrowed):
        pass

    assert borrowed.close_calls == 0
    reset_ai_config_for_tests()


def test_borrowed_httpx_client_remains_open_after_ai_client_context(
    monkeypatch,
):
    _provider_env(monkeypatch)
    http_client = httpx.Client(transport=httpx.MockTransport(lambda request: None))
    try:
        with client_module.AIClient(client=http_client):
            pass
        assert http_client.is_closed is False
    finally:
        http_client.close()
        reset_ai_config_for_tests()


def test_low_entropy_trace_ids_use_process_keyed_non_enumerable_digest():
    digest = client_module._trace_id_hash("1")

    assert digest == client_module._trace_id_hash("1")
    assert digest != hashlib.sha256(b"1").hexdigest()[:16]
    assert digest != "1"
    assert len(digest) >= 16


class _ModeClient:
    def __init__(self, content: str):
        self.content = content

    def complete(self, task_key, **_kwargs):
        return AIResult(
            content=self.content,
            provider="qwen",
            model="qwen3.7-plus",
            latency_ms=1,
            raw_response={},
        )


@pytest.mark.parametrize(
    ("missing_conditions", "expected"),
    [(None, []), ("图像模糊", ["图像模糊"]), (["缺少长度"], ["缺少长度"])],
)
def test_mode_a_accepts_five_steps_and_normalizes_legacy_missing_conditions(
    missing_conditions, expected
):
    import json

    payload = {
        "mode": "A",
        "steps": [
            {"step": index, "content": f"步骤{index}"}
            for index in range(1, 6)
        ],
        "final_answer": "42",
        "summary": "完成",
    }
    if missing_conditions is not None:
        payload["missing_conditions"] = missing_conditions

    result = ModeAAnswerComponent(
        _ModeClient(json.dumps(payload, ensure_ascii=False))
    ).run(QuestionInput(stem="题目"))

    assert len(result["steps"]) == 5
    assert result["missing_conditions"] == expected
