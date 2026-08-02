from __future__ import annotations

import json

import httpx
import pytest

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.components.variant_generator import VariantGeneratorComponent
from apps.common.ai.config import load_ai_config, reset_ai_config_for_tests
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError


VALID_VARIANT = {
    "stem": "若 x + 3 = 8，则 x 等于多少？",
    "question_type": "single_choice",
    "options": [
        {"label": "A", "content": "3"},
        {"label": "B", "content": "4"},
        {"label": "C", "content": "5"},
        {"label": "D", "content": "6"},
    ],
    "answer": "C",
    "analysis": "移项计算。",
    "solution": "x=8-3=5。",
    "difficulty": 2,
    "knowledge_points": [{"module": "方程"}],
    "variant_mode": "数值变化",
    "changes_from_original": "常数发生变化。",
}


class RecordingRegistry:
    def __init__(self):
        self.calls = []

    def render(self, task_key, **variables):
        self.calls.append((task_key, variables))
        return f"system:{task_key}", f"user:{task_key}"


class RecordingClient:
    def __init__(self, responses=None, providers=None, error=None):
        self.responses = responses or {}
        self.providers = providers or {}
        self.error = error
        self.calls = []

    def complete(self, task_key, **kwargs):
        self.calls.append((task_key, kwargs))
        if self.error is not None:
            raise self.error
        content = self.responses[task_key]
        provider = self.providers.get(
            task_key,
            "deepseek" if task_key == "variant_verify_deepseek" else "qwen",
        )
        model = (
            "deepseek-v4-pro"
            if provider == "deepseek"
            else "qwen3.7-plus"
        )
        return AIResult(
            content=content,
            provider=provider,
            model=model,
            latency_ms=41,
            raw_response={"id": task_key, "content": content},
        )


def _question() -> QuestionInput:
    return QuestionInput(
        stem="若 x + 2 = 7，则 x 等于多少？",
        options=[
            {"label": "A", "content": "3"},
            {"label": "B", "content": "4"},
            {"label": "C", "content": "5"},
            {"label": "D", "content": "6"},
        ],
        answer="C",
        solution="x=5",
        metadata={
            "question_type": "single_choice",
            "difficulty": 2,
            "knowledge_points": [{"module": "方程"}],
            "analysis": "移项。",
        },
    )


def test_variant_generator_uses_fixed_task_and_returns_validated_audit_result():
    registry = RecordingRegistry()
    client = RecordingClient(
        {"variant_generate": json.dumps(VALID_VARIANT, ensure_ascii=False)}
    )

    result = VariantGeneratorComponent(client, registry).generate(
        _question(), "数值变化"
    )

    assert [call[0] for call in client.calls] == ["variant_generate"]
    assert client.calls[0][1] == {
        "system": "system:variant_generate",
        "user": "user:variant_generate",
        "images": (),
        "trace_id": None,
    }
    task_key, variables = registry.calls[0]
    assert task_key == "variant_generate"
    assert variables["variant_mode"] == "数值变化"
    assert variables["question_type"] == "single_choice"
    assert json.loads(variables["question_context"])["stem"] == _question().stem
    assert result["parsed"]["stem"] == VALID_VARIANT["stem"]
    assert result["provider"] == "qwen"
    assert result["model"] == "qwen3.7-plus"
    assert result["latency_ms"] == 41
    assert result["raw_response"].startswith('{"stem"')


@pytest.mark.parametrize(
    "content",
    [
        '[{"stem": "array"}]',
        '{"stem": "缺答案", "question_type": "fill_blank"}',
        '{"stem": " ", "question_type": "fill_blank", "answer": "1"}',
        (
            '{"stem": "题目", "question_type": "single_choice", '
            '"answer": "A", "options": []}'
        ),
    ],
)
def test_variant_generator_rejects_malformed_or_incomplete_payload(content):
    client = RecordingClient({"variant_generate": content})

    with pytest.raises(AIResponseError):
        VariantGeneratorComponent(client, RecordingRegistry()).generate(
            _question(), "数值变化"
        )


def test_variant_schema_error_does_not_expose_raw_provider_payload():
    marker = "provider-raw-sensitive-marker"
    client = RecordingClient(
        {
            "variant_generate": json.dumps(
                {
                    "stem": " ",
                    "question_type": "fill_blank",
                    "answer": marker,
                }
            )
        }
    )

    with pytest.raises(AIResponseError) as caught:
        VariantGeneratorComponent(client, RecordingRegistry()).generate(
            _question(), "数值变化"
        )

    assert marker not in str(caught.value)


def test_variant_generator_propagates_provider_error_without_fabricating_result():
    client = RecordingClient(error=AIRequestError("provider unavailable"))

    with pytest.raises(AIRequestError, match="provider unavailable"):
        VariantGeneratorComponent(client, RecordingRegistry()).generate(
            _question(), "数值变化"
        )


def test_variant_verifier_uses_deepseek_task_and_validates_response():
    registry = RecordingRegistry()
    client = RecordingClient(
        {
            "variant_verify_deepseek": json.dumps(
                {
                    "passed": True,
                    "issues": [],
                    "score": 0.96,
                    "summary": "校验通过",
                },
                ensure_ascii=False,
            )
        }
    )

    result = ResultVerifierComponent(client, registry).verify(
        "variant_verify_deepseek",
        {"stem": _question().stem, "question_type": "single_choice"},
        VALID_VARIANT,
    )

    assert [call[0] for call in client.calls] == ["variant_verify_deepseek"]
    assert registry.calls[0][0] == "variant_verify_deepseek"
    variables = registry.calls[0][1]
    assert json.loads(variables["variant_json"])["stem"] == VALID_VARIANT["stem"]
    assert json.loads(variables["original_question_context"])["stem"] == _question().stem
    assert result == {
        "passed": True,
        "issues": [],
        "score": 0.96,
        "summary": "校验通过",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "latency_ms": 41,
    }


def test_variant_verifier_rejects_qwen_identity_instead_of_falling_back():
    client = RecordingClient(
        {
            "variant_verify_deepseek": (
                '{"passed":true,"issues":[],"score":1.0,'
                '"summary":"ok"}'
            )
        },
        providers={"variant_verify_deepseek": "qwen"},
    )

    with pytest.raises(AIResponseError, match="DeepSeek"):
        ResultVerifierComponent(client, RecordingRegistry()).verify(
            "variant_verify_deepseek", {}, VALID_VARIANT
        )


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        '{"passed":"yes","issues":[],"score":0.8,"summary":"ok"}',
        '{"passed":false,"issues":[],"score":2,"summary":"bad"}',
        '{"passed":false,"issues":[" "],"score":0.5,"summary":"bad"}',
    ],
)
def test_variant_verifier_rejects_malformed_payload(content):
    client = RecordingClient({"variant_verify_deepseek": content})

    with pytest.raises(AIResponseError):
        ResultVerifierComponent(client, RecordingRegistry()).verify(
            "variant_verify_deepseek", {}, VALID_VARIANT
        )


def test_variant_verifier_schema_error_does_not_expose_raw_provider_payload():
    marker = "deepseek-raw-sensitive-marker"
    client = RecordingClient(
        {
            "variant_verify_deepseek": json.dumps(
                {
                    "passed": "invalid",
                    "issues": [marker],
                    "score": 0.5,
                    "summary": "invalid",
                }
            )
        }
    )

    with pytest.raises(AIResponseError) as caught:
        ResultVerifierComponent(client, RecordingRegistry()).verify(
            "variant_verify_deepseek", {}, VALID_VARIANT
        )

    assert marker not in str(caught.value)


def test_variant_routes_are_cfg_fixed_to_expected_provider_model_and_timeout():
    config = load_ai_config()
    generation = config.get_task_config("variant_generate")
    verification = config.get_task_config("variant_verify_deepseek")

    assert (generation.provider, generation.model, generation.timeout_seconds) == (
        "qwen",
        "qwen3.7-plus",
        300.0,
    )
    assert (
        verification.provider,
        verification.model,
        verification.timeout_seconds,
    ) == ("deepseek", "deepseek-v4-pro", 300.0)


def test_real_qwen_variant_component_runs_when_optional_deepseek_key_is_absent(
    monkeypatch,
):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                VALID_VARIANT, ensure_ascii=False
                            )
                        }
                    }
                ]
            },
        )

    reset_ai_config_for_tests()
    try:
        client = AIClient(transport=httpx.MockTransport(handler))
        result = VariantGeneratorComponent(client).generate(
            _question(), "数值变化"
        )
    finally:
        if "client" in locals():
            client.close()
        reset_ai_config_for_tests()

    assert result["provider"] == "qwen"
    assert seen == ["https://example.test/qwen"]
