"""Behavior tests for database-free question AI components."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
from importlib import import_module
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from apps.common.ai.types import AIResult
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.schemas import ModeBQuestionResponse
from apps.common.exceptions import AIRequestError


class RecordingAIClient:
    """Small provider-boundary fake; prompts and parsers remain real."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id=None,
    ) -> AIResult:
        self.calls.append(
            {
                "task_key": task_key,
                "system": system,
                "user": user,
                "images": tuple(images),
                "trace_id": trace_id,
            }
        )
        return AIResult(
            content=self.responses[task_key],
            provider="qwen",
            model="configured-model",
            latency_ms=1,
            raw_response={"choices": []},
        )


def test_knowledge_selection_rejects_score_outside_selected_level_range():
    components = _components()
    component = components.TaxonomyKnowledgeComponent(
        RecordingAIClient(
            {
                "controlled_taxonomy_knowledge": json.dumps(
                    {
                        "knowledge_modules": ["模块一"],
                        "difficulty_score": 4.1,
                        "difficulty_reason": "综合应用",
                        "confidence": 0.9,
                    },
                    ensure_ascii=False,
                )
            }
        ),
        prompt_registry=StaticPromptRegistry(),
    )

    with pytest.raises(AIResponseError, match="difficulty level"):
        component.run(
            components.QuestionInput(
                stem="题目",
                metadata={
                    "difficulty_level": "L3",
                    "candidates": [{"id": "模块一"}],
                },
            )
        )


def test_subtopic_selection_rejects_null_when_candidates_are_available():
    """Catch a nullable model response stopping a non-empty catalog branch."""
    components = _components()
    component = components.TaxonomySubtopicComponent(
        RecordingAIClient(
            {
                "controlled_taxonomy_subtopic": json.dumps(
                    {"subtopic_id": None, "confidence": 0.2}
                )
            }
        ),
        prompt_registry=StaticPromptRegistry(),
    )

    with pytest.raises(AIResponseError, match="subtopic"):
        component.run(
            components.QuestionInput(
                stem="判断扩散现象的说法是否正确",
                metadata={
                    "subtopic_candidates": [
                        {"id": "junior-physics-molecular-motion"}
                    ]
                },
            )
        )


class StaticPromptRegistry:
    """Prompt boundary substitute for component-only response tests."""

    def render(self, _task_key, **_variables):
        return "system", "user"


class RetryPromptRegistry(StaticPromptRegistry):
    """Component-test prompt registry with an explicit response retry budget."""

    def __init__(self, retry_count: int) -> None:
        self.retry_count = retry_count

    def get_retry_count(self, _task_key):
        return self.retry_count


class SequencedAIClient:
    """Provider-boundary fake for proving component response-retry behavior."""

    def __init__(self, responses) -> None:
        self._responses = iter(responses)
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id=None,
    ) -> AIResult:
        self.calls.append(
            {
                "task_key": task_key,
                "system": system,
                "user": user,
                "images": tuple(images),
                "trace_id": trace_id,
            }
        )
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return AIResult(
            content=response,
            provider="qwen",
            model="configured-model",
            latency_ms=1,
            raw_response={"choices": []},
        )


class OnceOnlySequencedAIClient:
    """Production-shaped fake that forbids the retrying client entrypoint."""

    def __init__(self, responses) -> None:
        self._responses = iter(responses)
        self.once_calls: list[str] = []
        self.complete_calls = 0

    def complete(self, *_args, **_kwargs):
        self.complete_calls += 1
        raise AssertionError("structured components must use complete_once")

    def complete_once(self, task_key, **_kwargs) -> AIResult:
        self.once_calls.append(task_key)
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return AIResult(
            content=response,
            provider="qwen",
            model="configured-model",
            latency_ms=1,
            raw_response={"choices": []},
        )


class PromptOptionsManager:
    """Related-manager shaped source used to prove prompts never leak its repr."""

    def __init__(self):
        self.rows = [
            SimpleNamespace(option_label="D", content="four", sort_order=3),
            SimpleNamespace(option_label="B", content="two", sort_order=1),
            SimpleNamespace(option_label="A", content="one", sort_order=0),
            SimpleNamespace(option_label="C", content="three", sort_order=2),
        ]

    def all(self):
        return self

    def order_by(self, *_fields):
        return self.rows

    def __repr__(self):  # pragma: no cover - detects accidental serialization
        return "<PromptOptionsManager>"


def _components():
    """Import inside tests so the missing feature is a RED assertion failure."""
    return import_module("apps.common.ai.components")


def _mode_answer_response(task_key):
    if task_key == "mode_a_answer":
        return {
            "mode": "A",
            "steps": [
                {"step": 1, "content": "read the condition"},
                {"step": 2, "content": "compare options"},
                {"step": 3, "content": "verify C"},
            ],
            "final_answer": "C",
            "summary": "option C is correct",
        }
    if task_key == "mode_b_answer":
        question = {
            "question": "Which option follows?",
            "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
            "correct_option": "C",
            "reference_answer": "three",
            "analysis": "C matches the condition",
        }
        return {
            "mode": "B",
            "questions": [dict(question) for _ in range(3)],
            "final_answer": "C",
            "summary": "option C is correct",
        }
    question = {
        "question": "Which option follows?",
        "reference_answer": "C",
        "key_points": ["compare all options"],
        "followup_hint": "use the given condition",
    }
    return {
        "mode": "C",
        "questions": [dict(question) for _ in range(3)],
        "final_answer": "C",
        "summary": "option C is correct",
    }


def _strict_mode_b_response():
    response = _mode_answer_response("mode_b_answer")
    for question in response["questions"]:
        question["correct_answer"] = question["correct_option"]
        question["explanation"] = question["analysis"]
    return response


def _valid_probe_payload(**overrides):
    payload = {
        "subject": "math",
        "question_type": "calculation",
        "difficulty": "L2",
        "knowledge_points": ["algebra"],
        "multi_part": False,
        "proof_or_calc": "calc",
        "visual_risk_score": 0,
        "reasoning_risk_score": 20,
        "recommended_route": "STANDARD",
        "brief_reason": "basic calculation",
        "normalized_text": "solve x+1=2",
    }
    payload.update(overrides)
    return payload


def _probe_content_with_raw_string_values(payload, replacements):
    """Inject reviewed raw JSON string bodies without changing other fields."""
    encoded_payload = dict(payload)
    markers = {}
    for index, (key, raw_value) in enumerate(replacements.items()):
        marker = f"__RAW_PROBE_SCALAR_{index}__"
        encoded_payload[key] = marker
        markers[marker] = raw_value
    content = json.dumps(encoded_payload, ensure_ascii=False)
    for marker, raw_value in markers.items():
        content = content.replace(json.dumps(marker), f'"{raw_value}"')
    return content


def _run_probe_with_responses(responses, prompt_registry):
    components = _components()
    client = SequencedAIClient(responses)
    result = components.QuestionProbeComponent(
        client, prompt_registry=prompt_registry
    ).run(components.QuestionInput(stem="solve x+1=2"))
    return result, client


def test_question_component_retries_invalid_json_response_contract_once():
    """Catch missing component-level retries after a successful malformed response."""
    result, client = _run_probe_with_responses(
        ["not valid JSON", json.dumps(_valid_probe_payload())],
        RetryPromptRegistry(1),
    )

    assert result["subject"] == "math"
    assert len(client.calls) == 2


def test_question_component_retries_schema_invalid_response_contract_once():
    """Catch missing component-level retries after a parsed but invalid response."""
    result, client = _run_probe_with_responses(
        [json.dumps({"subject": "math"}), json.dumps(_valid_probe_payload())],
        RetryPromptRegistry(1),
    )

    assert result["subject"] == "math"
    assert len(client.calls) == 2


def test_probe_invalid_question_type_retries_once_under_default_configuration():
    """The probe contract must not inherit the provider's three-retry budget."""
    components = _components()
    client = SequencedAIClient(
        [
            json.dumps(_valid_probe_payload(question_type="阅读理解")),
            json.dumps(_valid_probe_payload(question_type="未知")),
        ]
    )

    with pytest.raises(AIResponseError, match="invalid_question_type"):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="识别题型")
        )

    assert len(client.calls) == 2


def test_probe_normalizes_multiple_choice_from_original_options_and_answer():
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": json.dumps(
                _valid_probe_payload(question_type="", normalized_text="请选择"),
                ensure_ascii=False,
            )
        }
    )

    result = components.QuestionProbeComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(
            stem="请选择正确答案",
            options=["A", "B", "C", "D"],
            answer="AB",
        )
    )

    assert result["question_type"] == "multiple_choice"


def test_controlled_scope_normalizes_multiple_choice_from_original_options_and_answer():
    components = _components()
    client = RecordingAIClient(
        {
            "controlled_taxonomy_scope": json.dumps(
                {
                    "subject": "math",
                    "stage": "junior",
                    "topic_id": "topic-1",
                    "question_type": "",
                    "difficulty_level": "L2",
                    "normalized_text": "请选择",
                    "confidence": 0.9,
                },
                ensure_ascii=False,
            )
        }
    )

    result = components.TaxonomyScopeComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(
            stem="请选择正确答案",
            options=["A", "B", "C", "D"],
            answer="AB",
            metadata={"topic_candidates": [{"id": "topic-1"}]},
        )
    )

    assert result["question_type"] == "multiple_choice"


@pytest.mark.parametrize("retry_count", [0, 3])
def test_controlled_scope_invalid_question_type_retries_once_regardless_of_budget(
    retry_count,
):
    components = _components()
    invalid_scope = {
        "subject": "math",
        "stage": "junior",
        "topic_id": "topic-1",
        "question_type": "阅读理解",
        "difficulty_level": "L2",
        "normalized_text": "识别题型",
        "confidence": 0.9,
    }
    client = SequencedAIClient(
        [json.dumps(invalid_scope, ensure_ascii=False)] * 2
    )

    with pytest.raises(AIResponseError, match="invalid_question_type"):
        components.TaxonomyScopeComponent(
            client, prompt_registry=RetryPromptRegistry(retry_count)
        ).run(
            components.QuestionInput(
                stem="识别题型",
                metadata={"topic_candidates": [{"id": "topic-1"}]},
            )
        )

    assert len(client.calls) == 2


def test_mode_answer_retries_a_control_character_corrupted_response():
    invalid = _mode_answer_response("mode_a_answer")
    invalid["summary"] = "bad\times"
    client = SequencedAIClient(
        [
            json.dumps(invalid, ensure_ascii=False) + ' {"partial":',
            json.dumps(_mode_answer_response("mode_a_answer"), ensure_ascii=False),
        ]
    )
    components = _components()

    result = components.ModeAAnswerComponent(
        client, prompt_registry=RetryPromptRegistry(1)
    ).run(components.QuestionInput(stem="solve x+1=2"))

    assert result["summary"] == "option C is correct"
    assert len(client.calls) == 2


@pytest.mark.parametrize(
    "question_patch",
    [
        {"correct_answer": "A"},
        {"reference_answer": "A"},
        {"reference_answer": "two"},
        {"options": {"A": "  one  ", "B": "\uff4f\uff4e\uff45", "C": "three", "D": "four"}},
    ],
)
def test_mode_b_question_schema_rejects_local_semantic_contract_violations(
    question_patch,
):
    question = _strict_mode_b_response()["questions"][0]
    question.update(question_patch)

    with pytest.raises(ValidationError):
        ModeBQuestionResponse.model_validate(question)


def test_mode_b_component_retries_correct_answer_conflict_then_accepts_valid_response():
    invalid = _strict_mode_b_response()
    for question in invalid["questions"]:
        question["correct_answer"] = "A"
    valid = _strict_mode_b_response()
    client = SequencedAIClient(
        [json.dumps(invalid, ensure_ascii=False), json.dumps(valid, ensure_ascii=False)]
    )
    components = _components()

    result = components.ModeBAnswerComponent(
        client, prompt_registry=RetryPromptRegistry(1)
    ).run(components.QuestionInput(stem="solve x+1=2"))

    assert result["questions"][0]["correct_answer"] == "C"
    assert len(client.calls) == 2


def test_question_component_raises_after_exhausting_response_contract_retries():
    """Catch an invalid response being accepted or retried beyond its budget."""
    client = SequencedAIClient(["not valid JSON", "still not valid JSON"])
    components = _components()

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(
            client, prompt_registry=RetryPromptRegistry(1)
        ).run(components.QuestionInput(stem="solve x+1=2"))

    assert len(client.calls) == 2


def test_probe_schema_retry_adds_explicit_correction_contract():
    client = SequencedAIClient(
        ["not valid JSON", json.dumps(_valid_probe_payload())]
    )
    components = _components()

    result = components.QuestionProbeComponent(
        client, prompt_registry=RetryPromptRegistry(1)
    ).run(components.QuestionInput(stem="solve x+1=2"))

    assert result["subject"] == "math"
    assert client.calls[0]["user"] == "user"
    assert "STRICT_SCHEMA_CORRECTION" in client.calls[1]["user"]


def test_question_component_shares_budget_for_request_error_then_valid_response():
    """Legacy fakes without complete_once still use one combined component budget."""
    client = SequencedAIClient(
        [AIRequestError("provider unavailable"), json.dumps(_valid_probe_payload())]
    )
    components = _components()

    result = components.QuestionProbeComponent(
        client, prompt_registry=RetryPromptRegistry(1)
    ).run(components.QuestionInput(stem="solve x+1=2"))

    assert result["subject"] == "math"
    assert len(client.calls) == 2


def test_question_component_uses_single_attempt_entrypoint_for_combined_budget():
    client = OnceOnlySequencedAIClient(
        [AIRequestError("provider unavailable"), json.dumps(_valid_probe_payload())]
    )
    components = _components()

    result = components.QuestionProbeComponent(
        client, prompt_registry=RetryPromptRegistry(1)
    ).run(components.QuestionInput(stem="solve x+1=2"))

    assert result["subject"] == "math"
    assert client.once_calls == ["question_probe", "question_probe"]
    assert client.complete_calls == 0


def test_request_error_then_invalid_response_exhausts_two_attempts_without_third():
    client = OnceOnlySequencedAIClient(
        [
            AIRequestError("provider unavailable"),
            "not valid JSON",
            json.dumps(_valid_probe_payload()),
            json.dumps(_valid_probe_payload()),
        ]
    )
    components = _components()

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(
            client, prompt_registry=RetryPromptRegistry(1)
        ).run(components.QuestionInput(stem="solve x+1=2"))

    assert client.once_calls == ["question_probe", "question_probe"]
    assert client.complete_calls == 0


def test_question_component_does_not_retry_when_response_retry_count_is_zero():
    """Catch a zero response-retry budget still issuing an extra provider call."""
    client = SequencedAIClient(
        ["not valid JSON", json.dumps(_valid_probe_payload())]
    )
    components = _components()

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(
            client, prompt_registry=RetryPromptRegistry(0)
        ).run(components.QuestionInput(stem="solve x+1=2"))

    assert len(client.calls) == 1


def test_question_component_defaults_to_zero_retries_for_legacy_prompt_fakes():
    """Keep existing prompt-registry test doubles compatible without hidden retries."""
    client = SequencedAIClient(
        ["not valid JSON", json.dumps(_valid_probe_payload())]
    )
    components = _components()

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(
            client, prompt_registry=StaticPromptRegistry()
        ).run(components.QuestionInput(stem="solve x+1=2"))

    assert len(client.calls) == 1


def test_question_input_is_immutable_including_collection_fields():
    components = _components()
    question = components.QuestionInput(
        stem="求 x",
        options={"A": ["1"]},
        image_urls=["https://example.test/one.png"],
        metadata={"source": {"page": 1}},
    )

    with pytest.raises(FrozenInstanceError):
        question.stem = "changed"
    with pytest.raises(TypeError):
        question.options["B"] = "2"
    with pytest.raises((AttributeError, TypeError)):
        question.options["A"].append("2")
    with pytest.raises(TypeError):
        question.metadata["source"] = "changed"
    with pytest.raises(TypeError):
        question.metadata["source"]["page"] = 2
    assert question.image_urls == ("https://example.test/one.png",)


@pytest.mark.parametrize(
    "component_name",
    ["ModeAAnswerComponent", "ModeBAnswerComponent", "ModeCAnswerComponent"],
)
def test_mode_answer_prompt_variables_append_canonical_options_to_probe_text(
    component_name,
):
    """Mode prompts retain complete canonical options when probe text has only a stem."""
    components = _components()
    question = components.QuestionInput(
        stem="fallback stem",
        options=[
            {"label": "C", "content": "third option"},
            {"label": "A", "content": "first option"},
            {"label": "B", "content": "second option"},
        ],
        metadata={"normalized_text": "probe stem only"},
    )

    variables = getattr(components, component_name)(
        RecordingAIClient({}), prompt_registry=StaticPromptRegistry()
    ).prompt_variables(question)

    assert variables["normalized_text"] == (
        "probe stem only\n\n完整选项：\n"
        "A: first option\nB: second option\nC: third option"
    )
    assert json.loads(variables["question_context_json"])["options"] == [
        {"label": "A", "content": "first option"},
        {"label": "B", "content": "second option"},
        {"label": "C", "content": "third option"},
    ]


@pytest.mark.parametrize(
    "component_name",
    ["ModeAAnswerComponent", "ModeBAnswerComponent", "ModeCAnswerComponent"],
)
def test_mode_answer_prompt_variables_do_not_invent_options_when_absent(
    component_name,
):
    """Mode prompts keep probe text unchanged when the current question has no options."""
    components = _components()
    question = components.QuestionInput(
        stem="fallback stem",
        metadata={"normalized_text": "probe stem only"},
    )

    variables = getattr(components, component_name)(
        RecordingAIClient({}), prompt_registry=StaticPromptRegistry()
    ).prompt_variables(question)

    assert variables["normalized_text"] == "probe stem only"
    assert "完整选项" not in variables["normalized_text"]
    assert json.loads(variables["question_context_json"])["options"] == []


@pytest.mark.parametrize(
    ("raw_options", "expected_options"),
    [
        (
            [
                {"label": " d ", "content": "four"},
                {"label": "B", "content": "two"},
                {"label": " a", "content": "one"},
                {"label": "C ", "content": "three"},
            ],
            {"A": "one", "B": "two", "C": "three", "D": "four"},
        ),
        (
            {"A": "one", "B": "two", "C": "three", "D": "four"},
            {"A": "one", "B": "two", "C": "three", "D": "four"},
        ),
    ],
)
def test_mode_b_normalizes_only_complete_labeled_option_lists(
    raw_options, expected_options
):
    """Mode B converts complete A-D lists while preserving existing option maps."""
    components = _components()
    question = {
        "question": "Which option follows?",
        "options": raw_options,
        "correct_option": "A",
        "reference_answer": "one",
        "analysis": "A matches the condition",
    }
    client = RecordingAIClient(
        {
            "mode_b_answer": json.dumps(
                {
                    "mode": "B",
                    "questions": [dict(question) for _ in range(3)],
                    "final_answer": "A",
                    "summary": "option A is correct",
                }
            )
        }
    )

    result = components.ModeBAnswerComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(components.QuestionInput(stem="Which option follows?"))

    assert result["questions"][0]["options"] == expected_options


@pytest.mark.parametrize(
    "raw_options",
    [
        [
            {"label": "A", "content": "one"},
            {"label": "a", "content": "another one"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "E", "content": "five"},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": " \u200b\n"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
    ],
)
def test_mode_b_rejects_incomplete_or_invalid_labeled_option_lists(raw_options):
    """Mode B leaves malformed option lists for strict schema rejection."""
    components = _components()
    question = {
        "question": "Which option follows?",
        "options": raw_options,
        "correct_option": "A",
        "reference_answer": "one",
        "analysis": "A matches the condition",
    }
    client = RecordingAIClient(
        {
            "mode_b_answer": json.dumps(
                {
                    "mode": "B",
                    "questions": [dict(question) for _ in range(3)],
                    "final_answer": "A",
                    "summary": "option A is correct",
                }
            )
        }
    )

    with pytest.raises(AIResponseError):
        components.ModeBAnswerComponent(
            client, prompt_registry=StaticPromptRegistry()
        ).run(components.QuestionInput(stem="Which option follows?"))


def test_probe_routes_fixed_task_and_normalizes_taxonomy_with_multiple_images():
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": """
            {
              "subject": "math",
                  "question_style": "single_choice",
                  "difficulty_est": "L2",
                  "topic_tags_top3": ["一元一次方程"],
                  "multi_part": false,
                  "proof_or_calc": "calc",
                  "visual_risk_score": 10,
                  "reasoning_risk_score": 20,
                  "recommended_route": "STANDARD",
                  "brief_reason": "基础计算",
                  "normalized_text": "解方程 x+1=2"
            }
            """
        }
    )
    question = components.QuestionInput(
        stem="解方程 x+1=2",
        image_urls=(
            "https://example.test/one.png",
            "https://example.test/two.png",
        ),
        metadata={"ocr_confidence": 0.91},
    )

    result = components.QuestionProbeComponent(client).run(question)

    assert client.calls[0]["task_key"] == "question_probe"
    assert client.calls[0]["images"] == question.image_urls
    assert set(result) >= {
        "subject",
        "question_type",
        "difficulty",
        "knowledge_points",
    }
    assert result["question_type"] == "single_choice"
    assert result["difficulty"] == "L2"
    assert result["knowledge_points"] == ["一元一次方程"]


def test_probe_normalizes_common_provider_scalar_and_collection_variants():
    components = _components()
    payload = _valid_probe_payload(
        subject="物理",
        difficulty=3,
        knowledge_points=[{"module": "欧姆定律"}, "串联电路"],
        multi_part="true",
        proof_or_calc="计算",
        visual_risk_score="45",
        reasoning_risk_score="70",
        recommended_route="deep",
    )
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="分析电路")
    )

    assert result["subject"] == "physics"
    assert result["difficulty"] == "L3"
    assert result["knowledge_points"] == ["欧姆定律", "串联电路"]
    assert result["multi_part"] is True
    assert result["proof_or_calc"] == "calc"
    assert result["visual_risk_score"] == 45
    assert result["reasoning_risk_score"] == 70
    assert result["recommended_route"] == "DEEP"


def test_probe_response_omits_taxonomy_owned_by_local_knowledge_tree():
    """Catch model-owned grade, term, and chapter leaking from the probe contract."""
    components = _components()
    client = RecordingAIClient(
        {"question_probe": json.dumps(_valid_probe_payload(), ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="解方程 x+1=2")
    )

    assert {"grade", "semester", "chapter"}.isdisjoint(result)


def test_probe_normalizes_legacy_question_type_aliases_to_the_contract():
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": """
            {
              "subject": "physics",
              "question_type": "calculation",
              "grade": "八年级",
              "semester": "下学期",
                  "chapter": "第八章",
                  "difficulty": "L3",
                  "knowledge_points": ["力与运动"],
                  "multi_part": false,
                  "proof_or_calc": "calc",
                  "visual_risk_score": 0,
                  "reasoning_risk_score": 35,
                  "recommended_route": "STANDARD",
                  "brief_reason": "力学计算",
                  "normalized_text": "计算物体所受合力"
            }
            """
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="计算物体所受合力")
    )

    assert result["question_type"] == "computation"
    assert result["question_style"] == "computation"
    assert result["difficulty_est"] == "L3"
    assert result["topic_tags_top3"] == ["力与运动"]


@pytest.mark.parametrize(
    ("canonical", "legacy", "expected"),
    [
        ("computation", "legacy-conflict", "computation"),
        ("", "calculation", "computation"),
        ("   ", "calculation", "computation"),
        (None, "calculation", "computation"),
    ],
)
def test_probe_scalar_aliases_prefer_nonempty_canonical_then_legacy(
    canonical, legacy, expected
):
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": """
            {
              "subject": "math",
              "question_type": %s,
              "question_style": %s,
              "grade": "七年级",
              "semester": "上学期",
              "chapter": "第三章",
              "difficulty": "L2",
              "difficulty_est": "L4",
              "knowledge_points": ["方程"],
              "topic_tags_top3": ["冲突知识点"],
              "multi_part": false,
              "proof_or_calc": "calc",
              "visual_risk_score": 0,
              "reasoning_risk_score": 20,
              "recommended_route": "STANDARD",
              "brief_reason": "基础计算",
              "normalized_text": "解方程 x+1=2"
            }
            """
            % (
                "null" if canonical is None else json.dumps(canonical),
                json.dumps(legacy),
            )
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="解方程 x+1=2")
    )

    assert result["question_type"] == expected
    assert result["question_style"] == expected
    assert result["difficulty"] == "L2"
    assert result["difficulty_est"] == "L2"
    assert result["knowledge_points"] == ["方程"]
    assert result["topic_tags_top3"] == ["方程"]


@pytest.mark.parametrize(
    ("canonical", "legacy", "expected"),
    [
        (
            " \t\r\n\u00a0\u2003\u3000calculation\u3000\u2003\u00a0\r\n\t ",
            "legacy-conflict",
            "computation",
        ),
        (
            " \t\r\n\u00a0\u2003\u3000 ",
            "\u3000\u2003\u00a0calculation\u00a0\u2003\u3000",
            "computation",
        ),
    ],
)
def test_probe_normalizes_scalar_question_type_alias_boundaries(
    canonical, legacy, expected
):
    components = _components()
    payload = {
        "subject": "math",
        "question_type": canonical,
        "question_style": legacy,
        "difficulty": "L2",
        "knowledge_points": ["algebra"],
        "multi_part": False,
        "proof_or_calc": "calc",
        "visual_risk_score": 0,
        "reasoning_risk_score": 20,
        "recommended_route": "STANDARD",
        "brief_reason": "basic calculation",
        "normalized_text": "solve x+1=2",
    }
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["question_type"] == expected
    assert result["question_style"] == expected


@pytest.mark.parametrize(
    ("canonical", "legacy", "expected"),
    [
        ("\t\r\n\u00a0\u2003\u3000L2\u3000\u2003\u00a0\r\n", "L4", "L2"),
        ("\t\r\n\u00a0\u2003\u3000", "\u3000\u2003L2\u2003\u3000", "L2"),
    ],
)
def test_probe_normalizes_scalar_difficulty_alias_boundaries(
    canonical, legacy, expected
):
    components = _components()
    payload = {
        "subject": "math",
        "question_type": "calculation",
        "difficulty": canonical,
        "difficulty_est": legacy,
        "knowledge_points": ["algebra"],
        "multi_part": False,
        "proof_or_calc": "calc",
        "visual_risk_score": 0,
        "reasoning_risk_score": 20,
        "recommended_route": "STANDARD",
        "brief_reason": "basic calculation",
        "normalized_text": "solve x+1=2",
    }
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["difficulty"] == expected
    assert result["difficulty_est"] == expected


@pytest.mark.parametrize(
    "format_char", ["\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"]
)
@pytest.mark.parametrize(
    ("canonical_key", "legacy_key"),
    [
        ("question_type", "question_style"),
        ("difficulty", "difficulty_est"),
    ],
)
def test_probe_rejects_scalar_aliases_containing_only_format_characters(
    format_char, canonical_key, legacy_key
):
    components = _components()
    payload = {
        "subject": "math",
        "question_type": "calculation",
        "difficulty": "L2",
        "knowledge_points": ["algebra"],
        "multi_part": False,
        "proof_or_calc": "calc",
        "visual_risk_score": 0,
        "reasoning_risk_score": 20,
        "recommended_route": "STANDARD",
        "brief_reason": "basic calculation",
        "normalized_text": "solve x+1=2",
    }
    payload[canonical_key] = format_char
    payload[legacy_key] = format_char
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


def test_probe_rejects_noncanonical_question_type_after_boundary_cleanup():
    components = _components()
    payload = {
        "subject": "math",
        "question_type": "\u200bcalcu\u200blation\ufeff",
        "difficulty": "\u2060L2\u200d",
        "knowledge_points": ["algebra"],
        "multi_part": False,
        "proof_or_calc": "calc",
        "visual_risk_score": 0,
        "reasoning_risk_score": 20,
        "recommended_route": "STANDARD",
        "brief_reason": "basic calculation",
        "normalized_text": "solve x+1=2",
    }
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError, match="invalid_question_type"):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "token", "conflict"),
    [
        ("question_type", "question_style", "computation", "legacy-conflict"),
        ("difficulty", "difficulty_est", "L2", "L4"),
    ],
)
@pytest.mark.parametrize(
    ("escaped_padding", "actual_padding"),
    [(r"\t", "\t"), (r"\n", "\n"), (r"\f", "\f"), (r"\r", "\r")],
)
@pytest.mark.parametrize("source_key", ["canonical", "legacy"])
def test_probe_normalizes_repaired_and_actual_escaped_whitespace_boundaries(
    canonical_key,
    legacy_key,
    token,
    conflict,
    escaped_padding,
    actual_padding,
    source_key,
):
    """Taxonomy boundaries accept repaired literal and decoded whitespace."""
    components = _components()
    prefix = (
        actual_padding
        + "\u200b"
        + escaped_padding
        + "\u00a0"
        + actual_padding
    )
    suffix = (
        actual_padding
        + "\u3000"
        + escaped_padding
        + "\ufeff"
        + actual_padding
    )
    padded_token = prefix + token + suffix
    boundary_only = prefix + suffix
    payload = _valid_probe_payload()
    if source_key == "canonical":
        payload[canonical_key] = padded_token
        payload[legacy_key] = conflict
    else:
        payload[canonical_key] = boundary_only
        payload[legacy_key] = padded_token
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result[canonical_key] == token
    assert result[legacy_key] == token


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "token", "conflict"),
    [
        ("question_type", "question_style", "computation", "legacy-conflict"),
        ("difficulty", "difficulty_est", "L2", "L4"),
    ],
)
@pytest.mark.parametrize(
    ("escape_letter", "actual_padding"),
    [("t", "\t"), ("n", "\n"), ("f", "\f"), ("r", "\r")],
)
@pytest.mark.parametrize("edge", ["prefix", "suffix"])
@pytest.mark.parametrize("source_key", ["canonical", "legacy"])
def test_probe_strips_mixed_backslash_real_whitespace_pairs_at_token_edges(
    canonical_key,
    legacy_key,
    token,
    conflict,
    escape_letter,
    actual_padding,
    edge,
    source_key,
):
    """A repaired slash+decoded-whitespace pair is one boundary unit."""
    components = _components()
    # Prefix adjacency triggers the overlap with two raw slashes; at the
    # suffix the equivalent repaired pair is produced from three raw slashes.
    mixed_pair_source = "\\" * (2 if edge == "prefix" else 3) + escape_letter
    padded_token_source = (
        mixed_pair_source + token
        if edge == "prefix"
        else token + mixed_pair_source
    )
    payload = _valid_probe_payload()
    if source_key == "canonical":
        payload[legacy_key] = conflict
        replacements = {canonical_key: padded_token_source}
    else:
        replacements = {
            canonical_key: mixed_pair_source,
            legacy_key: padded_token_source,
        }
    client = RecordingAIClient(
        {
            "question_probe": _probe_content_with_raw_string_values(
                payload, replacements
            )
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result[canonical_key] == token
    assert result[legacy_key] == token
    assert actual_padding not in result[canonical_key]


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "token"),
    [
        ("question_type", "question_style", "computation"),
        ("difficulty", "difficulty_est", "L2"),
    ],
)
def test_probe_strips_repeated_interleaved_mixed_taxonomy_boundaries(
    canonical_key, legacy_key, token
):
    """Mixed pairs, literal escapes, Unicode whitespace and Cf may interleave."""
    components = _components()
    prefix_source = (
        "\\" * 2
        + "t"
        + "\\" * 2
        + "n"
        + "\u200b"
        + r"\f"
        + "\u3000"
        + "\\" * 2
        + "r"
        + "\u2060"
    )
    suffix_source = (
        "\ufeff"
        + "\\" * 3
        + "f"
        + "\u00a0"
        + r"\t"
        + "\u200d"
        + "\\" * 3
        + "n"
        + "\\" * 3
        + "r"
    )
    payload = _valid_probe_payload()
    payload[legacy_key] = "legacy-conflict"
    client = RecordingAIClient(
        {
            "question_probe": _probe_content_with_raw_string_values(
                payload,
                {canonical_key: prefix_source + token + suffix_source},
            )
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result[canonical_key] == token
    assert result[legacy_key] == token


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "valid_value"),
    [
        ("question_type", "question_style", "computation"),
        ("difficulty", "difficulty_est", "L2"),
    ],
)
def test_probe_mixed_boundary_only_canonical_uses_legacy_scalar_alias(
    canonical_key, legacy_key, valid_value
):
    components = _components()
    payload = _valid_probe_payload()
    payload[legacy_key] = valid_value
    client = RecordingAIClient(
        {
            "question_probe": _probe_content_with_raw_string_values(
                payload,
                {
                    canonical_key: (
                        "\\" * 2
                        + "t"
                        + "\\" * 2
                        + "n"
                        + "\u200b"
                        + "\\" * 2
                        + "f"
                        + "\\" * 2
                        + "r"
                    )
                },
            )
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result[canonical_key] == valid_value
    assert result[legacy_key] == valid_value


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key"),
    [
        ("question_type", "question_style"),
        ("difficulty", "difficulty_est"),
    ],
)
def test_probe_rejects_two_mixed_boundary_only_scalar_aliases(
    canonical_key, legacy_key
):
    components = _components()
    payload = _valid_probe_payload()
    client = RecordingAIClient(
        {
            "question_probe": _probe_content_with_raw_string_values(
                payload,
                {
                    canonical_key: (
                        "\\" * 2 + "t" + "\u200b" + "\\" * 2 + "n"
                    ),
                    legacy_key: (
                        "\\" * 2 + "f" + "\u2060" + "\\" * 2 + "r"
                    ),
                },
            )
        }
    )

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


def test_probe_rejects_internal_mixed_pair_and_latex_question_type_content():
    from apps.common.ai.response_parser import ResponseParser

    components = _components()
    payload = _valid_probe_payload()
    content = _probe_content_with_raw_string_values(
        payload,
        {
            "question_type": (
                "calcu" + "\\" * 2 + "t" + "lation" + r"-\frac{1}{2}"
            )
        },
    )
    parsed_value = ResponseParser.parse_json(content)["question_type"]
    client = RecordingAIClient({"question_probe": content})

    assert r"\tlation" in parsed_value
    assert r"\frac{1}{2}" in parsed_value
    with pytest.raises(AIResponseError, match="invalid_question_type"):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


def test_probe_rejects_literal_escape_sequences_inside_question_type():
    components = _components()
    provider_value = "calcu\nla\ttion"
    payload = _valid_probe_payload(question_type=provider_value)
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError, match="invalid_question_type"):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "valid_value"),
    [
        ("question_type", "question_style", "computation"),
        ("difficulty", "difficulty_est", "L2"),
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [[], {}, ["invalid"], {"invalid": "value"}, 7, True],
)
@pytest.mark.parametrize("invalid_source", ["canonical", "legacy"])
def test_probe_rejects_non_string_scalar_alias_values_without_fallback(
    canonical_key,
    legacy_key,
    valid_value,
    invalid_value,
    invalid_source,
):
    components = _components()
    payload = _valid_probe_payload()
    if invalid_source == "canonical":
        payload[canonical_key] = invalid_value
        payload[legacy_key] = valid_value
    else:
        payload[canonical_key] = None
        payload[legacy_key] = invalid_value
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="solve x+1=2")
        )


def test_probe_keeps_none_compatibility_fallback_for_difficulty():
    components = _components()
    payload = _valid_probe_payload(difficulty=None, difficulty_est="L2")
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["difficulty"] == "L2"
    assert result["difficulty_est"] == "L2"


def test_probe_list_alias_uses_nonempty_legacy_when_canonical_is_empty():
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": """
            {
              "subject": "physics",
              "question_type": "calculation",
              "grade": "八年级",
              "semester": "下学期",
              "chapter": "第八章",
              "difficulty": "L3",
              "knowledge_points": [],
              "topic_tags_top3": ["力与运动"],
              "multi_part": false,
              "proof_or_calc": "calc",
              "visual_risk_score": 0,
              "reasoning_risk_score": 35,
              "recommended_route": "STANDARD",
              "brief_reason": "力学计算",
              "normalized_text": "计算物体所受合力"
            }
            """
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="计算物体所受合力")
    )

    assert result["knowledge_points"] == ["力与运动"]
    assert result["topic_tags_top3"] == ["力与运动"]


def test_probe_infers_question_type_from_stem_when_aliases_are_blank():
    components = _components()
    client = RecordingAIClient(
        {
            "question_probe": json.dumps(
                {
                    "subject": "math",
                    "question_type": "   ",
                    "question_style": "\t",
                    "difficulty": "L2",
                    "knowledge_points": ["方程"],
                    "multi_part": False,
                    "proof_or_calc": "calc",
                    "visual_risk_score": 0,
                    "reasoning_risk_score": 20,
                    "recommended_route": "STANDARD",
                    "brief_reason": "基础计算",
                    "normalized_text": "解方程 x+1=2",
                },
                ensure_ascii=False,
            )
        }
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="解方程 x+1=2")
    )

    assert result['question_type'] == 'computation'


@pytest.mark.parametrize(
    ("component_name", "task_key", "invalid_content"),
    [
        ("QuestionProbeComponent", "question_probe", "{}"),
        (
            "KnowledgeAnalysisComponent",
            "knowledge_analysis",
            '{"subject":"math","difficulty":"L2","knowledge_points":"方程"}',
        ),
        (
            "KnowledgeAnalysisComponent",
            "knowledge_analysis",
            '{"subject":"math","difficulty":"L2","knowledge_points":[{"module":"方程"}]}',
        ),
        (
            "VisionExtractionComponent",
            "vision_fact_extract",
            '{"subject":"math","figure_present":false}',
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"B","steps":[1],"final_answer":"2","summary":"完成"}',
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"A","steps":[1],"final_answer":"2"}',
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"A","steps":[1]}',
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"A","steps":[1],"final_answer":"2","summary":"完成"',
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"steps":[1],"final_answer":"2","summary":"完成"}',
        ),
        (
            "ModeBAnswerComponent",
            "mode_b_answer",
            '{"mode":"B","questions":[{"question":"下一步？","options":{"A":"1"}}]}',
        ),
        (
            "ModeBAnswerComponent",
            "mode_b_answer",
            '{"questions":[{"question":"下一步？","options":{"A":"1"},"correct_option":"A","analysis":"说明"}]}',
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            '{"mode":"C","questions":[{"question":"观察什么？","reference_answer":"等式"}]}',
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            '{"questions":[{"question":"观察什么？","reference_answer":"等式","key_points":["结构"],"followup_hint":"观察"}],"final_answer":"2","summary":"完成"}',
        ),
        (
            "ResultVerifierComponent",
            "result_verify",
            '{"pass":true,"issues":[],"retry_needed":false}',
        ),
    ],
)
def test_question_components_reject_wrong_mode_missing_fields_and_bad_shapes(
    component_name, task_key, invalid_content
):
    components = _components()
    client = RecordingAIClient({task_key: invalid_content})
    question = components.QuestionInput(
        stem="解方程 x+1=2",
        metadata={
            "vision_result": {"figure_present": False},
            "solver_output": {"final_answer": "2"},
        },
    )

    with pytest.raises(AIResponseError):
        getattr(components, component_name)(client).run(question)


@pytest.mark.parametrize(
    ("steps", "expected_contents"),
    [
        (
            [
                {"step": 1, "description": "set up the equation"},
                {"step": 2, "description": "solve for x"},
                {"step": 3, "description": "check the result"},
            ],
            ["set up the equation", "solve for x", "check the result"],
        ),
        (
            [
                {
                    "step": 1,
                    "content": "",
                    "description": "set up the equation",
                },
                {
                    "step": 2,
                    "content": "",
                    "description": "solve for x",
                },
                {
                    "step": 3,
                    "content": "",
                    "description": "check the result",
                },
            ],
            ["set up the equation", "solve for x", "check the result"],
        ),
        (
            [
                {
                    "step": 1,
                    "content": "canonical setup",
                    "description": "legacy setup",
                },
                {
                    "step": 2,
                    "content": "canonical solution",
                    "description": "legacy solution",
                },
                {
                    "step": 3,
                    "content": "canonical check",
                    "description": "legacy check",
                },
            ],
            ["canonical setup", "canonical solution", "canonical check"],
        ),
    ],
)
def test_mode_a_normalizes_legacy_step_descriptions_without_overriding_content(
    steps, expected_contents
):
    """Legacy descriptions reach schema validation only when content is absent."""
    components = _components()
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": steps,
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    result = components.ModeAAnswerComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert [step["content"] for step in result["steps"]] == expected_contents


@pytest.mark.parametrize(
    ("step_patch", "expected_content"),
    [
        ({"reason": "derive the equation"}, "derive the equation"),
        ({"content": None, "reason": "isolate x"}, "isolate x"),
        ({"content": " \t\u200b\n", "reason": "check the result"}, "check the result"),
        (
            {
                "content": "canonical content",
                "description": "legacy description",
                "reason": "qwen reason",
            },
            "canonical content",
        ),
        (
            {"description": "legacy description", "reason": "qwen reason"},
            "legacy description",
        ),
    ],
)
def test_mode_a_normalizes_qwen_step_reason_with_stable_content_priority(
    step_patch, expected_content
):
    """Mode A accepts Qwen's reason alias without exposing it in the response."""
    components = _components()
    steps = [
        {"step": index, "content": f"existing content {index}"}
        for index in range(1, 4)
    ]
    steps[1] = {"step": 2, **step_patch}
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": steps,
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    result = components.ModeAAnswerComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["steps"][1]["content"] == expected_content
    assert "reason" not in result["steps"][1]


@pytest.mark.parametrize(
    ("step_patch", "expected_content"),
    [
        ({"reasoning": "derive the equation"}, "derive the equation"),
        (
            {"reason": "visible reason", "reasoning": "hidden fallback"},
            "visible reason",
        ),
        (
            {"content": "canonical content", "reasoning": "hidden fallback"},
            "canonical content",
        ),
    ],
)
def test_mode_a_normalizes_reasoning_step_fallback_without_leaking_alias(
    step_patch, expected_content
):
    """Mode A supports Qwen's lowest-priority reasoning step alias."""
    components = _components()
    steps = [
        {"step": index, "content": f"existing content {index}"}
        for index in range(1, 4)
    ]
    steps[1] = {"step": 2, **step_patch}
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": steps,
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    result = components.ModeAAnswerComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["steps"][1]["content"] == expected_content
    assert "reasoning" not in result["steps"][1]


@pytest.mark.parametrize(
    ("raw_step", "expected_step"),
    [
        ("1", 1),
        ("步骤1", 1),
        ("Step 1", 1),
        ("sTeP 2", 2),
        (3, 3),
    ],
)
def test_mode_a_normalizes_explicit_positive_step_numbers(raw_step, expected_step):
    """Mode A converts only explicit positive step-number text to integers."""
    components = _components()
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": [
                        {"step": raw_step, "content": "first step"},
                        {"step": 2, "content": "second step"},
                        {"step": 3, "content": "third step"},
                    ],
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    result = components.ModeAAnswerComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["steps"][0]["step"] == expected_step
    assert isinstance(result["steps"][0]["step"], int)


@pytest.mark.parametrize(
    "raw_step",
    ["0", "步骤0", "Step 0", "-1", "", " \t\u200b\n", None, 0, -1, {}],
)
def test_mode_a_rejects_ambiguous_or_nonpositive_step_numbers(raw_step):
    """Mode A leaves invalid step identifiers for schema rejection."""
    components = _components()
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": [
                        {"step": raw_step, "content": "first step"},
                        {"step": 2, "content": "second step"},
                        {"step": 3, "content": "third step"},
                    ],
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    with pytest.raises(AIResponseError):
        components.ModeAAnswerComponent(
            client, prompt_registry=StaticPromptRegistry()
        ).run(components.QuestionInput(stem="solve x+1=2"))


@pytest.mark.parametrize(
    ("step_patch", "expected_content"),
    [
        ({"step": "identify the known conditions"}, "identify the known conditions"),
        (
            {
                "step": "compare the options",
                "reasoning": "use the equation relation",
            },
            "use the equation relation",
        ),
        (
            {
                "step": "lowest-priority explanation",
                "content": "canonical content",
                "description": "legacy description",
                "reason": "legacy reason",
                "reasoning": "legacy reasoning",
            },
            "canonical content",
        ),
    ],
)
def test_mode_a_uses_visible_unparsed_step_text_as_last_content_fallback(
    step_patch, expected_content
):
    """Visible explanatory step text is retained after numbered normalization fails."""
    components = _components()
    steps = [
        {"step": 1, "content": "first step"},
        step_patch,
        {"step": 3, "content": "third step"},
    ]
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(
                {
                    "mode": "A",
                    "steps": steps,
                    "final_answer": "2",
                    "summary": "completed",
                }
            )
        }
    )

    result = components.ModeAAnswerComponent(
        client, prompt_registry=StaticPromptRegistry()
    ).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["steps"][1]["step"] == 2
    assert result["steps"][1]["content"] == expected_content
    assert "reason" not in result["steps"][1]
    assert "reasoning" not in result["steps"][1]


@pytest.mark.parametrize(
    ("component_name", "task_key", "content", "expected"),
    [
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"A","steps":[{"step":1,"content":"列式"},{"step":2,"content":"求解"},{"step":3,"content":"验算"}],"final_answer":"2","summary":"完成"}',
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"step": 2, "content": "求解"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeBAnswerComponent",
            "mode_b_answer",
            """
            {
              "mode": "B",
              "questions": [
                {"question":"第一步？","options":{"A":"1","B":"2","C":"3","D":"4"},"correct_option":"B","reference_answer":"2","analysis":"代入"},
                {"question":"第二步？","options":{"A":"1","B":"2","C":"3","D":"4"},"correct_option":"B","reference_answer":"2","analysis":"计算"},
                {"question":"第三步？","options":{"A":"1","B":"2","C":"3","D":"4"},"correct_option":"B","reference_answer":"2","analysis":"验算"}
              ],
              "final_answer": "2",
              "summary": "递进完成"
            }
            """,
            {
                "mode": "B",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                "correct_answer": "B",
                "explanation": "代入",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            """
            {
              "mode": "C",
              "questions": [
                {"question":"你观察到什么？","reference_answer":"等式","key_points":["观察结构"],"followup_hint":"看等号两侧"},
                {"question":"下一步做什么？","reference_answer":"移项","key_points":["等式性质"],"followup_hint":"保持等式成立"},
                {"question":"如何验算？","reference_answer":"代回原式","key_points":["结果验证"],"followup_hint":"检查左右两边"}
              ],
              "final_answer": "2",
              "summary": "开放引导"
            }
            """,
            {
                "mode": "C",
                "reference_answer": "等式",
                "key_points": ["观察结构"],
                "followup_hint": "看等号两侧",
            },
        ),
    ],
)
def test_mode_components_route_fixed_tasks_and_preserve_contracts(
    component_name, task_key, content, expected
):
    components = _components()
    client = RecordingAIClient({task_key: content})
    question = components.QuestionInput(
        stem="解方程 x+1=2",
        answer="2",
        solution="两边减一",
        image_urls=("https://example.test/one.png",),
        metadata={"vision_result": {"figure_present": False}},
    )

    result = getattr(components, component_name)(client).run(question)

    assert client.calls[0]["task_key"] == task_key
    assert client.calls[0]["images"] == question.image_urls
    assert result["mode"] == expected["mode"]
    if task_key == "mode_a_answer":
        assert {key: result[key] for key in expected} == expected
    else:
        first_question = result["questions"][0]
        for key, value in expected.items():
            if key != "mode":
                assert first_question[key] == value


@pytest.mark.parametrize(
    ("component_name", "task_key"),
    [
        ("ModeAAnswerComponent", "mode_a_answer"),
        ("ModeBAnswerComponent", "mode_b_answer"),
        ("ModeCAnswerComponent", "mode_c_answer"),
    ],
)
def test_mode_prompts_include_complete_authoritative_question_context(
    component_name, task_key
):
    """Catch solvers receiving only legacy text instead of complete answer facts."""
    context = import_module("apps.common.ai.question_context")
    options = PromptOptionsManager()
    source_question = SimpleNamespace(
        stem="Which option is correct?",
        options=options,
        answer="C",
        analysis="Existing analysis explains the third option.",
        solution="Existing solution substitutes the values.",
        question_type="single_choice",
        subject="physics",
        difficulty="0.75",
        material="A material passage",
        tables=[],
        subquestions=[],
    )
    question = context.QuestionContextBuilder.build(
        source_question,
        normalized_text="normalized option question",
        vision_result={"figure_present": True},
        knowledge_refs="kinematics",
        target_mode=task_key.split("_")[1].upper(),
    )
    client = RecordingAIClient(
        {task_key: json.dumps(_mode_answer_response(task_key), ensure_ascii=False)}
    )

    getattr(_components(), component_name)(client).run(question)

    user_prompt = client.calls[0]["user"]
    context_json = user_prompt.split("）：\n", 1)[1].split(
        "\n规范化题干：", 1
    )[0]
    captured_context = json.loads(context_json)
    assert captured_context["stem"] == "Which option is correct?"
    assert captured_context["options"] == [
        {"label": "A", "content": "one"},
        {"label": "B", "content": "two"},
        {"label": "C", "content": "three"},
        {"label": "D", "content": "four"},
    ]
    assert captured_context["reference_answer"] == "C"
    assert captured_context["reference_analysis"] == (
        "Existing analysis explains the third option."
    )
    assert "PromptOptionsManager" not in user_prompt


def test_knowledge_vision_and_verifier_use_their_fixed_configured_tasks():
    components = _components()
    client = RecordingAIClient(
        {
                "knowledge_analysis": (
                    '{"subject":"math","difficulty":"L2",'
                    '"knowledge_points":[{"module":"方程",'
                    '"reason":"直接求解方程"}]}'
                ),
            "vision_fact_extract": """
            {
              "subject":"math",
              "figure_present":false,
              "figure_type":"",
              "visual_summary":"无图形",
              "diagram_facts":[],
              "text_marks_in_figure":[],
              "variables_and_symbols":[],
              "target_related_visual_info":[],
              "unclear_parts":[],
              "ocr_conflicts":[],
              "confidence":"high"
            }
            """,
            "result_verify": """
            {
              "pass":true,
              "consistency":"consistent",
              "fact_violation":false,
              "calc_suspect":false,
              "issues":[],
              "retry_needed":false,
              "retry_reason":""
            }
            """,
        }
    )
    question = components.QuestionInput(
        stem="解方程 x+1=2",
        metadata={
            "subject_hint": "math",
            "vision_result": {"figure_present": False},
            "solver_output": {"final_answer": "2"},
        },
    )

    knowledge = components.KnowledgeAnalysisComponent(client).run(question)
    vision = components.VisionExtractionComponent(client).run(question)
    verified = components.ResultVerifierComponent(client).run(question)

    assert [call["task_key"] for call in client.calls] == [
        "knowledge_analysis",
        "vision_fact_extract",
        "result_verify",
    ]
    assert knowledge["knowledge_points"][0]["module"] == "方程"
    assert vision["figure_present"] is False
    assert verified == {
        "pass": True,
        "consistency": "consistent",
        "fact_violation": False,
        "calc_suspect": False,
        "issues": [],
        "retry_needed": False,
        "retry_reason": "",
    }


def test_probe_service_builds_bounded_structured_fallback_when_stem_is_blank():
    from apps.common.ai_service import AIReviewService

    component = MagicMock()
    component.run.return_value = _valid_probe_payload()
    service = AIReviewService(component_factory=MagicMock(return_value=component))
    question = SimpleNamespace(
        stem="",
        raw_text="原始复合题题面",
        material="阅读材料",
        options={"A": "选项一"},
        answer="",
        solution="",
        analysis="",
        question_type="true_false",
        subject="physics",
        tables=[{"rows": [["电压", "6V"]]}],
        subquestions=[{"label": "(1)", "stem": "判断电流是否增大"}],
    )

    service.probe_and_norm(question, [])

    probe_input = component.run.call_args.args[0]
    assert "原始复合题题面" in probe_input.stem
    assert "判断电流是否增大" in probe_input.stem
    assert "6V" in probe_input.stem
    assert "physics" in probe_input.stem
    assert len(probe_input.stem) <= 30000


def test_probe_service_preserves_nonblank_stem_without_raw_fallback_noise():
    from apps.common.ai_service import AIReviewService

    component = MagicMock()
    component.run.return_value = _valid_probe_payload()
    service = AIReviewService(component_factory=MagicMock(return_value=component))
    question = SimpleNamespace(
        stem="正式题干",
        raw_text="不应覆盖正式题干",
        options=None,
        answer="",
        solution="",
        analysis="",
    )

    service.probe_and_norm(question, [])

    probe_input = component.run.call_args.args[0]
    assert probe_input.stem == "正式题干"


def test_legacy_service_factory_keeps_mode_a_shape_without_own_http_path():
    from apps.common.ai_service import AIReviewService

    component = MagicMock()
    component.run.return_value = {
        "mode": "A",
        "steps": ["一", "二", "三"],
        "final_answer": "2",
        "summary": "完成",
    }
    factory = MagicMock(return_value=component)
    question = SimpleNamespace(
        stem="解方程 x+1=2",
        options=None,
        answer="2",
        solution="两边减一",
        analysis="",
    )

    service = AIReviewService(component_factory=factory)
    with patch.object(service, "_get_question_image_urls", return_value=[]):
        result = service.generate_answer_a(question)

    assert result == {
        "mode": "A",
        "steps": ["一", "二", "三"],
        "final_answer": "2",
        "summary": "完成",
    }
    assert factory.call_count == 1
    component.run.assert_called_once()


def test_legacy_service_does_not_create_unused_client_for_injected_factory():
    from apps.common.ai_service import AIReviewService

    component = MagicMock()
    component.run.return_value = {
        "mode": "A",
        "steps": ["一", "二", "三"],
        "final_answer": "2",
        "summary": "完成",
    }
    factory = MagicMock(return_value=component)
    question = SimpleNamespace(
        stem="解方程 x+1=2",
        options=None,
        answer="2",
        solution="两边减一",
        analysis="",
    )

    with patch("apps.common.ai_service.AIClient") as client_constructor:
        service = AIReviewService(component_factory=factory)
        with patch.object(service, "_get_question_image_urls", return_value=[]):
            result = service.generate_answer_a(question)

    client_constructor.assert_not_called()
    assert result["final_answer"] == "2"


@pytest.mark.parametrize(
    ("component_name", "task_key", "invalid_payload"),
    [
        (
            "QuestionProbeComponent",
            "question_probe",
            {
                "subject": "math",
                "question_type": "calculation",
                "difficulty": "L2",
                "knowledge_points": ["方程"],
                "multi_part": False,
                "proof_or_calc": "calc",
                "visual_risk_score": 0,
                "reasoning_risk_score": 20,
                "recommended_route": "STANDARD",
                "brief_reason": "基础计算",
                "normalized_text": "",
            },
        ),
        (
            "QuestionProbeComponent",
            "question_probe",
            {
                "subject": "math",
                "question_type": "calculation",
                "difficulty": "L2",
                "knowledge_points": [],
                "multi_part": False,
                "proof_or_calc": "calc",
                "visual_risk_score": 0,
                "reasoning_risk_score": 20,
                "recommended_route": "STANDARD",
                "brief_reason": "基础计算",
                "normalized_text": "解方程",
            },
        ),
        (
            "QuestionProbeComponent",
            "question_probe",
            {
                "subject": "math",
                "question_type": "calculation",
                "difficulty": "L2",
                "knowledge_points": ["方程", "代数", "运算", "等式", "数", "超限"],
                "multi_part": False,
                "proof_or_calc": "calc",
                "visual_risk_score": 0,
                "reasoning_risk_score": 20,
                "recommended_route": "STANDARD",
                "brief_reason": "基础计算",
                "normalized_text": "解方程",
            },
        ),
        (
            "QuestionProbeComponent",
            "question_probe",
            {
                "subject": "math",
                "question_type": "calculation",
                "difficulty": "L2",
                "knowledge_points": ["方程", ""],
                "multi_part": False,
                "proof_or_calc": "calc",
                "visual_risk_score": 0,
                "reasoning_risk_score": 20,
                "recommended_route": "STANDARD",
                "brief_reason": "基础计算",
                "normalized_text": "解方程",
            },
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"step": 2, "content": "求解"},
                ],
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"step": 2, "content": ""},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"step": 2, "content": "求解"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "",
                "summary": "完成",
            },
        ),
        (
            "KnowledgeAnalysisComponent",
            "knowledge_analysis",
            {
                "subject": "math",
                "difficulty": "L2",
                "knowledge_points": [{"module": "方程", "reason": "   "}],
            },
        ),
        (
            "ModeBAnswerComponent",
            "mode_b_answer",
            {
                "mode": "B",
                "questions": [
                    {
                        "question": "第一步？",
                        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                        "reference_answer": "数值2",
                        "analysis": "说明",
                    }
                ] * 3,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeBAnswerComponent",
            "mode_b_answer",
            {
                "mode": "B",
                "questions": [
                    {
                        "question": "第一步？",
                        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                        "correct_answer": ["A"],
                        "reference_answer": "1",
                        "analysis": "说明",
                    }
                ] * 3,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"content": "求解"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "列式"},
                    {"step": 2, "content": "求解"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "   ",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            {
                "mode": "C",
                "questions": [
                    {
                        "question": "观察什么？",
                        "reference_answer": "等式",
                        "key_points": [""],
                        "followup_hint": "观察等号",
                    }
                ] * 3,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            {
                "mode": "C",
                "questions": [
                    {
                        "question": "观察什么？",
                        "reference_answer": "等式",
                        "key_points": ["结构"],
                        "followup_hint": "观察等号",
                    }
                ] * 2,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            {
                "mode": "C",
                "questions": [
                    {
                        "question": "观察什么？",
                        "reference_answer": "",
                        "key_points": ["结构"],
                        "followup_hint": "观察等号",
                    }
                ] * 3,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            {
                "mode": "C",
                "questions": [
                    {
                        "question": "观察什么？",
                        "reference_answer": "等式",
                        "key_points": ["结构"],
                        "followup_hint": "",
                    }
                ] * 3,
                "final_answer": "2",
                "summary": "完成",
            },
        ),
        (
            "ModeCAnswerComponent",
            "mode_c_answer",
            {
                "mode": "C",
                "questions": [
                    {
                        "question": "观察什么？",
                        "reference_answer": "等式",
                        "key_points": ["结构"],
                        "followup_hint": "观察等号",
                    }
                ] * 3,
                "final_answer": "",
                "summary": "完成",
            },
        ),
        (
            "VisionExtractionComponent",
            "vision_fact_extract",
            {
                "subject": "math",
                "figure_present": True,
                "figure_type": "坐标图",
                "visual_summary": "坐标图中标出一点",
                "diagram_facts": [""],
                "text_marks_in_figure": [],
                "variables_and_symbols": [],
                "target_related_visual_info": [],
                "unclear_parts": [],
                "ocr_conflicts": [],
                "confidence": "high",
            },
        ),
        (
            "ResultVerifierComponent",
            "result_verify",
            {
                "pass": True,
                "consistency": "",
                "fact_violation": False,
                "calc_suspect": False,
                "issues": [],
                "retry_needed": False,
                "retry_reason": "",
            },
        ),
        (
            "ResultVerifierComponent",
            "result_verify",
            {
                "pass": True,
                "consistency": "consistent",
                "fact_violation": "false",
                "calc_suspect": False,
                "issues": [],
                "retry_needed": False,
                "retry_reason": "",
            },
        ),
        (
            "ResultVerifierComponent",
            "result_verify",
            {
                "pass": False,
                "consistency": "inconsistent",
                "fact_violation": True,
                "calc_suspect": False,
                "issues": [""],
                "retry_needed": True,
                "retry_reason": "事实冲突",
            },
        ),
        (
            "ResultVerifierComponent",
            "result_verify",
            {
                "pass": False,
                "consistency": "inconsistent",
                "fact_violation": False,
                "calc_suspect": True,
                "issues": ["计算可疑"],
                "retry_needed": True,
                "retry_reason": "",
            },
        ),
    ],
)
def test_components_reject_payloads_outside_central_cfg_hard_contract(
    component_name, task_key, invalid_payload
):
    components = _components()
    client = RecordingAIClient(
        {task_key: json.dumps(invalid_payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError):
        getattr(components, component_name)(client).run(
            components.QuestionInput(stem="解方程 x+1=2")
        )


@pytest.mark.parametrize(
    "payload_patch",
    [
        {"questions": []},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct_option": "A", "reference_answer": "1", "analysis": "说明"}] * 2},
        {"questions": [{"question": "", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct_option": "A", "reference_answer": "1", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3"}, "correct_option": "A", "reference_answer": "1", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}, "correct_option": "A", "reference_answer": "1", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": ""}, "correct_option": "A", "reference_answer": "1", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct_option": "E", "reference_answer": "1", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct_option": "A", "reference_answer": "", "analysis": "说明"}] * 3},
        {"questions": [{"question": "第一步？", "options": {"A": "1", "B": "2", "C": "3", "D": "4"}, "correct_option": "A", "reference_answer": "1", "analysis": ""}] * 3},
        {"final_answer": ""},
        {"summary": ""},
    ],
)
def test_mode_b_rejects_each_invalid_question_contract_field(payload_patch):
    components = _components()
    valid_question = {
        "question": "第一步？",
        "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
        "correct_option": "A",
        "reference_answer": "1",
        "analysis": "说明",
    }
    payload = {
        "mode": "B",
        "questions": [dict(valid_question) for _ in range(3)],
        "final_answer": "2",
        "summary": "完成",
    }
    payload.update(payload_patch)
    client = RecordingAIClient(
        {"mode_b_answer": json.dumps(payload, ensure_ascii=False)}
    )

    with pytest.raises(AIResponseError):
        components.ModeBAnswerComponent(client).run(
            components.QuestionInput(stem="解方程 x+1=2")
        )


def test_provider_client_is_lazy_and_constructed_once_for_sixteen_threads():
    from apps.common.ai_service import AIReviewService

    created = []
    created_lock = threading.Lock()

    def create_client():
        time.sleep(0.02)
        client = MagicMock(name=f"client-{len(created)}")
        with created_lock:
            created.append(client)
        return client

    with patch("apps.common.ai_service.AIClient", side_effect=create_client):
        service = AIReviewService()
        assert created == []
        with ThreadPoolExecutor(max_workers=16) as executor:
            clients = list(executor.map(lambda _index: service._provider_client(), range(16)))

        assert len(created) == 1
        assert all(client is created[0] for client in clients)
        service.close()

    created[0].close.assert_called_once_with()


def test_mode_b_accepts_only_explicit_abcd_legacy_correct_answer_alias():
    components = _components()
    questions = [
        {
            "question": f"第{index}步？",
            "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
            "correct_answer": "B",
            "reference_answer": "2",
            "explanation": "计算说明",
        }
        for index in range(1, 4)
    ]
    client = RecordingAIClient(
        {
            "mode_b_answer": json.dumps(
                {
                    "mode": "B",
                    "questions": questions,
                    "final_answer": "2",
                    "summary": "递进完成",
                },
                ensure_ascii=False,
            )
        }
    )

    result = components.ModeBAnswerComponent(client).run(
        components.QuestionInput(stem="解方程 x+1=2")
    )

    assert result["questions"][0]["correct_option"] == "B"
    assert result["questions"][0]["correct_answer"] == "B"
    assert result["questions"][0]["reference_answer"] == "2"


def test_service_close_does_not_close_injected_client():
    from apps.common.ai_service import AIReviewService

    borrowed_client = MagicMock()
    service = AIReviewService(ai_client=borrowed_client)

    service.close()

    borrowed_client.close.assert_not_called()


def test_service_arbitration_uses_one_injected_factory_for_qwen_and_deepseek():
    from apps.common.ai.components import QuestionComponentFactory
    from apps.common.ai_service import AIReviewService

    qwen = _mode_answer_response("mode_a_answer") | {"final_answer": "B"}
    independent = {
        "independent_answer": "C",
        "independent_reasoning_summary": "The reference answer follows from the data.",
        "key_facts": ["three is the required value"],
        "reference_answer_valid": True,
        "reference_analysis_valid": False,
        "reference_issues": ["analysis needs review"],
        "confidence": 0.95,
        "mode_content": _mode_answer_response("mode_a_answer"),
    }
    final = {
        "trusted_answer": "C",
        "qwen_content_valid": False,
        "candidate_issues": ["candidate answer conflicts with the reference"],
        "confidence": 0.99,
        "mode_content": _mode_answer_response("mode_a_answer"),
    }
    client = RecordingAIClient(
        {
            "mode_a_answer": json.dumps(qwen),
            "deepseek_independent_verify": json.dumps(independent),
            "deepseek_final_review": json.dumps(final),
        }
    )
    factory = QuestionComponentFactory(client)
    service = AIReviewService(component_factory=factory)
    question = SimpleNamespace(
        stem="Which value is correct?",
        options=PromptOptionsManager(),
        answer="C",
        analysis="Reference analysis",
        solution="Reference solution",
        question_type="single_choice",
        subject="math",
        difficulty=2,
        material="Read the material",
        tables=[{"rows": [["x", "3"]]}],
        subquestions=[{"stem": "Subquestion one"}],
    )

    outcome = service.solve_mode_with_arbitration(
        question,
        mode="A",
        image_urls=("https://cdn.example.test/q.png",),
        normalized_text="Normalized stem",
        vision_result={"figure_present": True},
        knowledge_refs="linear equations",
    )

    assert outcome.answer["final_answer"] == "C"
    assert outcome.answer["verification"]["selected_content_provider"] == (
        "deepseek_final_review"
    )
    assert [call["task_key"] for call in client.calls] == [
        "mode_a_answer",
        "deepseek_independent_verify",
        "deepseek_final_review",
    ]
    rendered = "\n".join(str(call["user"]) for call in client.calls)
    for expected in (
        "Which value is correct?",
        "Reference analysis",
        "Reference solution",
        "Normalized stem",
        "linear equations",
        "https://cdn.example.test/q.png",
    ):
        assert expected in rendered
    assert "<PromptOptionsManager>" not in rendered


def test_service_retries_full_mode_arbitration_once_after_provider_failure():
    from apps.common.ai.answer_arbitration import ArbitrationOutcome, ArbitrationProviderError
    from apps.common.ai_service import AIReviewService

    service = AIReviewService(component_factory=lambda _component_type: MagicMock())
    question = SimpleNamespace(
        stem="Which value is correct?",
        options=None,
        answer="C",
        analysis="Reference analysis",
        solution="Reference solution",
        question_type="single_choice",
        subject="math",
        difficulty=2,
        material="",
        tables=[],
        subquestions=[],
    )
    recovered = ArbitrationOutcome(
        answer=_mode_answer_response("mode_a_answer"),
        verification={"context_hash": "same-context"},
        shared_verifier_result=None,
    )

    with patch(
        "apps.common.ai_service.ModeAnswerArbitrator.process",
        side_effect=[ArbitrationProviderError(), recovered],
    ) as process:
        outcome = service.solve_mode_with_arbitration(question, mode="A")

    assert outcome.answer["final_answer"] == "C"
    assert process.call_count == 2


def test_service_reuses_only_shared_verification_while_routing_all_mode_components():
    from apps.common.ai.components import (
        DeepSeekFinalReviewComponent,
        DeepSeekIndependentVerifierComponent,
        ModeAAnswerComponent,
        ModeBAnswerComponent,
        ModeCAnswerComponent,
    )
    from apps.common.ai_service import AIReviewService

    mode_components = {
        ModeAAnswerComponent: "mode_a_answer",
        ModeBAnswerComponent: "mode_b_answer",
        ModeCAnswerComponent: "mode_c_answer",
    }
    factory_calls = []
    run_calls = []

    def complete_mode_content(task_key):
        content = _mode_answer_response(task_key)
        content["reasoning_content"] = "private chain"
        content["raw_response"] = {"provider": "private raw"}
        content["provider_payload"] = {"request_id": "private request"}
        content["verification"] = {"provider": "candidate supplied"}
        if task_key == "mode_a_answer":
            content["steps"][0]["raw_response"] = "nested private raw"
        if task_key == "mode_b_answer":
            content["questions"] = [
                {
                    **question,
                    "correct_answer": question["correct_option"],
                    "explanation": question["analysis"],
                    "reasoning_content": "nested private chain",
                }
                for question in content["questions"]
            ]
        if task_key == "mode_c_answer":
            content["questions"][0]["provider_payload"] = {
                "request_id": "nested private request"
            }
        return content

    class Component:
        def __init__(self, component_type):
            self.component_type = component_type

        def run(self, question_input):
            run_calls.append((self.component_type, question_input))
            if self.component_type in mode_components:
                return complete_mode_content(
                    mode_components[self.component_type]
                ) | {"final_answer": "B"}
            if self.component_type is DeepSeekIndependentVerifierComponent:
                return {
                    "independent_answer": "C",
                    "independent_reasoning_summary": "C follows from the data.",
                    "key_facts": ["three is the required value"],
                    "reference_answer_valid": True,
                    "reference_analysis_valid": False,
                    "reference_issues": ["analysis needs review"],
                    "confidence": 0.95,
                    "mode_content": complete_mode_content("mode_a_answer"),
                }
            target_mode = question_input.metadata["target_mode"]
            return {
                "trusted_answer": "C",
                "qwen_content_valid": False,
                "candidate_issues": ["candidate answer conflicts with reference"],
                "confidence": 0.99,
                "mode_content": complete_mode_content(
                    f"mode_{target_mode.lower()}_answer"
                ),
            }

    def factory(component_type):
        factory_calls.append(component_type)
        return Component(component_type)

    service = AIReviewService(component_factory=factory)
    question = SimpleNamespace(
        stem="Which value is correct?",
        options=PromptOptionsManager(),
        answer="C",
        analysis="Reference analysis",
        solution="Reference solution",
        question_type="single_choice",
        subject="math",
        difficulty=2,
        material="",
        tables=[],
        subquestions=[],
    )
    shared = None
    outcomes = []

    for mode in "ABC":
        outcome = service.solve_mode_with_arbitration(
            question,
            mode=mode,
            cached_verification=shared,
        )
        outcomes.append(outcome)
        shared = outcome.shared_verifier_result or shared

    assert [component_type for component_type, _context in run_calls] == [
        ModeAAnswerComponent,
        DeepSeekIndependentVerifierComponent,
        DeepSeekFinalReviewComponent,
        ModeBAnswerComponent,
        DeepSeekFinalReviewComponent,
        ModeCAnswerComponent,
        DeepSeekFinalReviewComponent,
    ]
    assert factory_calls == [component_type for component_type, _context in run_calls]
    assert [outcome.answer["mode"] for outcome in outcomes] == ["A", "B", "C"]
    assert all(
        outcome.answer["verification"]["selected_content_provider"]
        == "deepseek_final_review"
        for outcome in outcomes
    )
    assert "independent_verification_cached" in (
        outcomes[1].answer["verification"]["warnings"]
    )
    assert "independent_verification_cached" in (
        outcomes[2].answer["verification"]["warnings"]
    )
    expected_keys = {
        "A": {"mode", "steps", "final_answer", "summary", "missing_conditions"},
        "B": {"mode", "questions", "final_answer", "summary"},
        "C": {"mode", "questions", "final_answer", "summary"},
    }
    for mode, outcome in zip("ABC", outcomes):
        assert set(outcome.answer) == expected_keys[mode] | {"verification"}
        serialized = json.dumps(outcome.answer, ensure_ascii=False)
        for forbidden in (
            "reasoning_content",
            "raw_response",
            "provider_payload",
            "private chain",
            "private raw",
            "private request",
            "candidate supplied",
        ):
            assert forbidden not in serialized
    assert set(outcomes[0].answer["steps"][0]) == {"step", "content"}
    assert set(outcomes[1].answer["questions"][0]) == {
        "question",
        "options",
        "correct_option",
        "reference_answer",
        "analysis",
        "correct_answer",
        "explanation",
    }
    assert set(outcomes[2].answer["questions"][0]) == {
        "question",
        "reference_answer",
        "key_points",
        "followup_hint",
    }
