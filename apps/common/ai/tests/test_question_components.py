"""Behavior tests for database-free question AI components."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from importlib import import_module
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.common.ai.types import AIResult
from apps.common.ai.exceptions import AIResponseError


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


def _components():
    """Import inside tests so the missing feature is a RED assertion failure."""
    return import_module("apps.common.ai.components")


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
        "grade",
        "semester",
        "chapter",
        "difficulty",
        "knowledge_points",
    }
    assert result["question_type"] == "single_choice"
    assert result["difficulty"] == "L2"
    assert result["knowledge_points"] == ["一元一次方程"]


def test_probe_preserves_legacy_aliases_when_provider_returns_canonical_fields():
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

    assert result["question_style"] == "calculation"
    assert result["difficulty_est"] == "L3"
    assert result["topic_tags_top3"] == ["力与运动"]


@pytest.mark.parametrize(
    ("canonical", "legacy", "expected"),
    [
        ("canonical", "legacy", "canonical"),
        ("", "legacy", "legacy"),
        ("   ", "calculation", "calculation"),
        (None, "legacy", "legacy"),
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
            "calculation",
        ),
        (
            " \t\r\n\u00a0\u2003\u3000 ",
            "\u3000\u2003\u00a0calculation\u00a0\u2003\u3000",
            "calculation",
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


def test_probe_strips_boundary_format_characters_but_preserves_internal_ones():
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

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["question_type"] == "calcu\u200blation"
    assert result["question_style"] == "calcu\u200blation"
    assert result["difficulty"] == "L2"
    assert result["difficulty_est"] == "L2"


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "token", "conflict"),
    [
        ("question_type", "question_style", "calculation", "legacy-conflict"),
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
        ("question_type", "question_style", "calculation", "legacy-conflict"),
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
        ("question_type", "question_style", "calculation"),
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
        ("question_type", "question_style", "calculation"),
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


def test_probe_preserves_internal_mixed_pair_and_latex_content():
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

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert "\\" + "\t" in parsed_value
    assert r"\frac{1}{2}" in parsed_value
    assert result["question_type"] == parsed_value
    assert result["question_style"] == parsed_value


def test_probe_preserves_literal_escape_sequences_inside_question_type():
    components = _components()
    provider_value = "calcu\nla\ttion"
    repaired_literal_escapes = r"calcu\nla\ttion"
    payload = _valid_probe_payload(question_type=provider_value)
    client = RecordingAIClient(
        {"question_probe": json.dumps(payload, ensure_ascii=False)}
    )

    result = components.QuestionProbeComponent(client).run(
        components.QuestionInput(stem="solve x+1=2")
    )

    assert result["question_type"] == repaired_literal_escapes
    assert result["question_style"] == repaired_literal_escapes


@pytest.mark.parametrize(
    ("canonical_key", "legacy_key", "valid_value"),
    [
        ("question_type", "question_style", "calculation"),
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


def test_probe_rejects_question_type_when_both_aliases_are_blank():
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

    with pytest.raises(AIResponseError):
        components.QuestionProbeComponent(client).run(
            components.QuestionInput(stem="解方程 x+1=2")
        )


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
            "reference_answer": "数值2",
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
    assert result["questions"][0]["reference_answer"] == "数值2"


def test_service_close_does_not_close_injected_client():
    from apps.common.ai_service import AIReviewService

    borrowed_client = MagicMock()
    service = AIReviewService(ai_client=borrowed_client)

    service.close()

    borrowed_client.close.assert_not_called()
