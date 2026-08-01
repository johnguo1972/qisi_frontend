"""Behavior tests for database-free question AI components."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.common.ai.types import AIResult


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
              "grade": "七年级",
              "semester": "上学期",
              "chapter": "第三章",
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
              "knowledge_points": ["力与运动"]
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
    ("component_name", "task_key", "content", "expected"),
    [
        (
            "ModeAAnswerComponent",
            "mode_a_answer",
            '{"mode":"A","steps":[1,2,3],"final_answer":"2","summary":"完成"}',
            {
                "mode": "A",
                "steps": [1, 2, 3],
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
              "questions": [{
                "question": "第一步？",
                "options": {"A":"1","B":"2","C":"3","D":"4"},
                "correct_option": "B",
                "analysis": "代入"
              }]
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
              "questions": [{
                "question": "你观察到什么？",
                "reference_answer": "等式",
                "key_points": ["观察结构"],
                "followup_hint": "看等号两侧"
              }],
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
                '"knowledge_points":[{"module":"方程"}]}'
            ),
            "vision_fact_extract": '{"figure_present":false,"entities":[]}',
            "result_verify": '{"pass":true,"issues":[],"retry_needed":false}',
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
    assert verified == {"pass": True, "issues": [], "retry_needed": False}


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
