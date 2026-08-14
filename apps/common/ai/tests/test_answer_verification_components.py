"""Contract tests for the isolated two-stage answer-verification flow."""

from __future__ import annotations

import importlib
import json

import pytest
from pydantic import BaseModel, ValidationError

from apps.common.ai.components.base import QuestionInput
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.types import AIResult


QWEN_MARKER = "UNIQUE_QWEN_MARKER_DO_NOT_LEAK"


class StringLeak:
    def __str__(self):
        return QWEN_MARKER

    def __repr__(self):
        return QWEN_MARKER


class VisionFact(BaseModel):
    caption: str


class RecordingAIClient:
    """Provider-boundary fake that retains the real rendering and parsing path."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def complete(self, task_key, *, system, user, images=(), trace_id=None):
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
            content=json.dumps(self.responses[task_key], ensure_ascii=False),
            provider="deepseek",
            model="deepseek-v4-pro",
            latency_ms=1,
            raw_response={"choices": []},
        )


def _components():
    return importlib.import_module("apps.common.ai.components")


def _schemas():
    return importlib.import_module("apps.common.ai.schemas")


def _question(**metadata):
    base = {
        "reference_analysis": "The third option follows the stated law.",
        "question_type": "single_choice",
        "subject": "physics",
        "difficulty": "L2",
        "material": "A cart moves at constant speed.",
        "tables": [{"name": "measurements", "rows": [["t", "1"]]}],
        "subquestions": [{"stem": "State the law."}],
        "normalized_text": "Choose the correct law.",
        "vision_result": {"visual_summary": "A labelled cart diagram."},
        "knowledge_refs": ["inertia"],
        "target_mode": "A",
    }
    base.update(metadata)
    return QuestionInput(
        stem="Which statement about the cart is correct?",
        options=[
            {"label": "D", "content": "four"},
            {"label": "B", "content": "two"},
            {"label": "A", "content": "one"},
            {"label": "C", "content": "three"},
        ],
        answer="C",
        solution="Use the force balance before selecting C.",
        image_urls=("https://example.test/cart.png",),
        metadata=base,
    )


def _independent_response(**overrides):
    payload = {
        "independent_answer": "C",
        "independent_reasoning_summary": "The stated condition selects option C.",
        "key_facts": ["The cart is in equilibrium."],
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "confidence": 0.93,
        "mode_content": {"mode": "A", "final_answer": "C"},
    }
    payload.update(overrides)
    return payload


def _final_response(**overrides):
    payload = {
        "trusted_answer": "C",
        "qwen_content_valid": True,
        "candidate_issues": [],
        "confidence": 0.95,
        "mode_content": {"mode": "A", "final_answer": "C"},
    }
    payload.update(overrides)
    return payload


def test_public_components_and_strict_response_schemas_are_available():
    """Catch missing public contracts or an extra-permissive verification schema."""
    components = _components()
    schemas = _schemas()

    assert hasattr(components, "DeepSeekIndependentVerifierComponent")
    assert hasattr(components, "DeepSeekFinalReviewComponent")
    with pytest.raises(ValidationError):
        schemas.IndependentVerificationResponse.model_validate(
            {**_independent_response(), "unexpected": "field"}
        )
    with pytest.raises(ValidationError):
        schemas.FinalReviewResponse.model_validate(
            {**_final_response(), "confidence": 1.01}
        )


@pytest.mark.parametrize(
    "payload",
    [
        _independent_response(independent_answer="   "),
        _independent_response(confidence=-0.01),
        _independent_response(mode_content=[]),
        _final_response(candidate_issues=[" "]),
        _final_response(mode_content="not an object"),
    ],
)
def test_verification_schemas_reject_blank_or_malformed_contract_values(payload):
    """Catch weakened type, visible-text, range, or mode-content validation."""
    schemas = _schemas()
    schema = (
        schemas.IndependentVerificationResponse
        if "independent_answer" in payload
        else schemas.FinalReviewResponse
    )

    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.parametrize(
    ("reference_issues", "expected_issues"),
    [
        (None, []),
        ("", []),
        (" \t\n", []),
        (" 无 ", []),
        (" NONE ", []),
        ("  nOnE\t", []),
        ("  reference answer needs review  ", ["reference answer needs review"]),
        (["existing issue"], ["existing issue"]),
    ],
)
def test_independent_stage_normalizes_reference_issue_strings(
    reference_issues, expected_issues
):
    """Accept the provider's known scalar variants without weakening the list schema."""
    components = _components()
    client = RecordingAIClient(
        {
            "deepseek_independent_verify": _independent_response(
                reference_issues=reference_issues
            )
        }
    )

    result = components.DeepSeekIndependentVerifierComponent(client).run(_question())

    assert result["reference_issues"] == expected_issues


@pytest.mark.parametrize("reference_issues", [{}, 0, True])
def test_independent_stage_rejects_nonlist_nonstring_reference_issues(
    reference_issues,
):
    """Keep unexpected provider shapes visible to the strict response schema."""
    components = _components()
    client = RecordingAIClient(
        {
            "deepseek_independent_verify": _independent_response(
                reference_issues=reference_issues
            )
        }
    )

    with pytest.raises(AIResponseError):
        components.DeepSeekIndependentVerifierComponent(client).run(_question())


@pytest.mark.parametrize(
    ("confidence", "expected_confidence"),
    [
        ("0", 0.0),
        ("1", 1.0),
        ("0.95", 0.95),
        (".95", 0.95),
        (" \t.95\n", 0.95),
    ],
)
@pytest.mark.parametrize(
    ("component_name", "task_key", "response_factory"),
    [
        (
            "DeepSeekIndependentVerifierComponent",
            "deepseek_independent_verify",
            _independent_response,
        ),
        ("DeepSeekFinalReviewComponent", "deepseek_final_review", _final_response),
    ],
)
def test_verification_components_normalize_strict_decimal_confidence_strings(
    component_name, task_key, response_factory, confidence, expected_confidence
):
    """Accept only provider decimal strings that are unambiguously JSON numbers."""
    components = _components()
    client = RecordingAIClient({task_key: response_factory(confidence=confidence)})

    result = getattr(components, component_name)(client).run(_question())

    assert result["confidence"] == expected_confidence


@pytest.mark.parametrize(
    "confidence",
    ["95%", "1e-1", "NaN", "Inf", "-Inf", "high", "2"],
)
@pytest.mark.parametrize(
    ("component_name", "task_key", "response_factory"),
    [
        (
            "DeepSeekIndependentVerifierComponent",
            "deepseek_independent_verify",
            _independent_response,
        ),
        ("DeepSeekFinalReviewComponent", "deepseek_final_review", _final_response),
    ],
)
def test_verification_components_reject_nondecimal_or_out_of_range_confidence_strings(
    component_name, task_key, response_factory, confidence
):
    """Keep unsafe numeric-looking provider strings subject to strict validation."""
    components = _components()
    client = RecordingAIClient({task_key: response_factory(confidence=confidence)})

    with pytest.raises(AIResponseError):
        getattr(components, component_name)(client).run(_question())


def test_independent_stage_renders_full_canonical_context_but_never_candidate_data():
    """Catch a first-stage prompt that leaks a Qwen candidate into independent work."""
    components = _components()
    client = RecordingAIClient(
        {"deepseek_independent_verify": _independent_response()}
    )
    question = _question(
        qwen_result={"answer": QWEN_MARKER, "provider": "qwen"},
        independent_result={"answer": QWEN_MARKER},
        conflicts=[QWEN_MARKER],
        vision_result={"nested": {"qwen_result": QWEN_MARKER}},
    )

    result = components.DeepSeekIndependentVerifierComponent(client).run(question)
    request = client.calls[0]
    rendered = f"{request['system']}\n{request['user']}"

    assert request["task_key"] == "deepseek_independent_verify"
    assert result["independent_answer"] == "C"
    for expected in (
        question.stem,
        '"label":"A"',
        '"label":"D"',
        question.answer,
        question.solution,
        "The third option follows the stated law.",
        "https://example.test/cart.png",
        '"title":"ModeAResponse"',
    ):
        assert expected in rendered
    assert QWEN_MARKER not in rendered
    assert "qwen_result" not in rendered
    assert "independent_result" not in rendered
    assert "conflicts" not in rendered
    assert "qwen" not in rendered.casefold()
    assert "deepseek" not in rendered.casefold()


def test_independent_stage_drops_unknown_visual_objects_before_canonical_context():
    """Catch question-context stringification leaking an arbitrary visual object."""
    components = _components()
    client = RecordingAIClient(
        {"deepseek_independent_verify": _independent_response()}
    )
    question = _question(
        vision_result={
            "safe_fact": VisionFact(caption="kept vision fact"),
            "unsafe_fact": StringLeak(),
        }
    )

    components.DeepSeekIndependentVerifierComponent(client).run(question)
    rendered = f"{client.calls[0]['system']}\n{client.calls[0]['user']}"

    assert QWEN_MARKER not in rendered
    assert '"caption":"kept vision fact"' in rendered


def test_final_review_renders_neutral_candidates_conflicts_and_mode_schema():
    """Catch a final-review prompt missing evidence or exposing provider identities."""
    components = _components()
    client = RecordingAIClient({"deepseek_final_review": _final_response()})
    question = _question(
        qwen_result={
            "final_answer": "C",
            "provider": "qwen",
            "model": "qwen3.7-plus",
        },
        independent_result={"independent_answer": "C", "provider": "deepseek"},
        conflicts=["final_answer_conflict", "mode_schema_incomplete"],
    )

    result = components.DeepSeekFinalReviewComponent(client).run(question)
    request = client.calls[0]
    rendered = f"{request['system']}\n{request['user']}"

    assert request["task_key"] == "deepseek_final_review"
    assert result["trusted_answer"] == "C"
    for expected in (
        question.stem,
        '"final_answer":"C"',
        '"independent_answer":"C"',
        "final_answer_conflict",
        "mode_schema_incomplete",
        '"title":"ModeAResponse"',
        "candidate A",
        "candidate B",
    ):
        assert expected in rendered
    assert "qwen3.7-plus" not in rendered.casefold()
    assert "deepseek-v4-pro" not in rendered.casefold()


def test_reference_flags_must_be_null_exactly_when_reference_material_is_absent():
    """Catch nullable reference flags accepted for the wrong question context."""
    components = _components()
    with_reference = RecordingAIClient(
        {
            "deepseek_independent_verify": _independent_response(
                reference_answer_valid=None,
                reference_analysis_valid=None,
            )
        }
    )
    without_reference = RecordingAIClient(
        {
            "deepseek_independent_verify": _independent_response(
                reference_answer_valid=True,
                reference_analysis_valid=True,
            )
        }
    )

    with pytest.raises(AIResponseError):
        components.DeepSeekIndependentVerifierComponent(with_reference).run(_question())
    with pytest.raises(AIResponseError):
        components.DeepSeekIndependentVerifierComponent(without_reference).run(
            QuestionInput(stem="Solve this.", metadata={"target_mode": "A"})
        )


class CandidateModel(BaseModel):
    independent_answer: str


class ReprLeak:
    def __repr__(self):
        return "<ReprLeak UNIQUE_OBJECT_REPR_MARKER>"


def test_final_review_serializes_pydantic_candidates_but_never_arbitrary_object_repr():
    """Catch stringification of arbitrary objects at the final-review boundary."""
    components = _components()
    client = RecordingAIClient({"deepseek_final_review": _final_response()})
    question = _question(
        qwen_result=CandidateModel(independent_answer="C"),
        independent_result=ReprLeak(),
        conflicts=["answer_mismatch"],
    )

    components.DeepSeekFinalReviewComponent(client).run(question)
    rendered = f"{client.calls[0]['system']}\n{client.calls[0]['user']}"

    assert '"independent_answer":"C"' in rendered
    assert "UNIQUE_OBJECT_REPR_MARKER" not in rendered


def test_config_keeps_the_fixed_thinking_routes_and_exact_prompt_variables(monkeypatch):
    """Catch a component route or prompt contract drifting from the approved task keys."""
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    from apps.common.ai.config import AIConfig

    config = AIConfig.load()
    independent = config.get_task_config("deepseek_independent_verify")
    final = config.get_task_config("deepseek_final_review")

    for task in (independent, final):
        assert (
            task.provider,
            task.model,
            task.timeout_seconds,
            task.retry_count,
            task.enable_thinking,
            task.reasoning_effort,
        ) == ("deepseek", "deepseek-v4-pro", 300.0, 1, True, "high")
    assert config.get_prompt_config("deepseek_independent_verify").variables == (
        "question_context_json",
        "target_mode",
        "mode_schema_json",
    )
    assert config.get_prompt_config("deepseek_final_review").variables == (
        "question_context_json",
        "target_mode",
        "qwen_result_json",
        "independent_result_json",
        "conflicts_json",
        "mode_schema_json",
    )
