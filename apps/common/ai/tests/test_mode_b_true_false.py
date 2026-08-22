"""Regression coverage for multipart true/false A/B/C mode generation.

The fixtures below mirror the shape of production questions
019ff9fc-42a4-7bf2-87d3-555cc5c66d84 and
019ff9fc-42bc-7951-8d9d-e8351a94d131.  They intentionally contain no
multiple-choice options: every child statement must be judged independently.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from apps.common.ai.answer_validation import AnswerNormalizer, ModeContentValidator
from apps.common.ai.components import (
    ModeAAnswerComponent,
    ModeBAnswerComponent,
    ModeCAnswerComponent,
    QuestionInput,
)
from apps.common.ai.types import AIResult
from apps.common.ai_service import AIReviewService


class _StaticPromptRegistry:
    def render(self, _task_key, **_variables):
        return "system", "user"


class _StaticAIClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def complete(self, task_key, **_kwargs) -> AIResult:
        self.calls.append(task_key)
        return AIResult(
            content=json.dumps(self.payload, ensure_ascii=False),
            provider="qwen",
            model="test-model",
            latency_ms=1,
            raw_response={},
        )


MULTIPART_TRUE_FALSE_FIXTURES = (
    {
        "id": "019ff9fc-42a4-7bf2-87d3-555cc5c66d84",
        "stem": "请判断下列说法是否正确。",
        "subquestions": [
            {"label": "（1）", "stem": "扩散现象只能发生在气体和液体之间。"},
            {"label": "（2）", "stem": "扩散现象说明分子在不停地做无规则运动。"},
            {"label": "（3）", "stem": "粉笔灰飞扬属于扩散现象。"},
            {"label": "（4）", "stem": "炒菜时闻到香味属于扩散现象。"},
            {"label": "（5）", "stem": "扩散现象说明分子间存在间隙。"},
            {"label": "（6）", "stem": "温度越高，扩散现象越剧烈。"},
            {"label": "（7）", "stem": "水和酒精混合后总体积变小，说明分子间有间隙。"},
        ],
    },
    {
        "id": "019ff9fc-42bc-7951-8d9d-e8351a94d131",
        "stem": "判断下列结论是否正确。",
        "subquestions": [
            {"label": "（1）", "stem": "静止的物体没有动能。"},
            {"label": "（2）", "stem": "机械能大的物体，速度一定大。"},
            {"label": "（3）", "stem": "水具有内能，但冰没有内能。"},
            {"label": "（4）", "stem": "同一物体温度越高，内能越大。"},
            {"label": "（5）", "stem": "同一水壶在高处的重力势能比低处大。"},
            {"label": "（6）", "stem": "做功和热传递都可以改变物体内能。"},
            {"label": "（7）", "stem": "晶体熔化时温度不变，内能也不变。"},
            {"label": "（8）", "stem": "物体温度越高，含有的热量一定越多。"},
        ],
    },
)


def _question(fixture: dict) -> QuestionInput:
    return QuestionInput(
        stem=fixture["stem"],
        metadata={
            "question_type": "true_false",
            "subquestions": fixture["subquestions"],
            "normalized_text": fixture["stem"],
        },
    )


def _mode_b_judgment_payload(fixture: dict) -> dict:
    judgments = []
    for index, child in enumerate(fixture["subquestions"], start=1):
        judgment = "TRUE" if index % 2 else "FALSE"
        judgments.append(
            {
                "subquestion_label": child["label"],
                "question": child["stem"],
                "correct_option": judgment,
                "reference_answer": judgment,
                "analysis": "依据题干中的物理概念作出判断。",
                "correct_answer": judgment,
                "explanation": "先辨析概念，再判断该说法。",
            }
        )
    return {
        "mode": "B",
        "questions": judgments,
        "final_answer": ";".join(item["correct_answer"] for item in judgments),
        "summary": "逐项判断全部子题，并给出对应依据。",
    }


def _mode_a_judgment_payload(fixture: dict) -> dict:
    steps = []
    for index, child in enumerate(fixture["subquestions"], start=1):
        judgment = "TRUE" if index % 2 else "FALSE"
        steps.append(
            {
                "step": index,
                "subquestion_label": child["label"],
                "judgment": judgment,
                "content": f"{child['label']} 判断：{judgment}。依据题干概念逐项分析。",
            }
        )
    return {
        "mode": "A",
        "steps": steps,
        "final_answer": ";".join(item["judgment"] for item in steps),
        "summary": "逐项给出判断及依据。",
        "missing_conditions": [],
    }


def _mode_c_judgment_payload(fixture: dict) -> dict:
    questions = []
    for index, child in enumerate(fixture["subquestions"], start=1):
        judgment = "TRUE" if index % 2 else "FALSE"
        questions.append(
            {
                "subquestion_label": child["label"],
                "question": child["stem"],
                "reference_answer": judgment,
                "key_points": ["先确定判断依据", "再核对该说法"],
                "followup_hint": "请用一句话说明判断理由。",
            }
        )
    return {
        "mode": "C",
        "questions": questions,
        "final_answer": ";".join(item["reference_answer"] for item in questions),
        "summary": "通过逐项追问巩固判断依据。",
    }


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_mode_b_accepts_judgment_guidance_without_forcing_abcd_options(fixture):
    """A multipart judgment question must use one judgment guide per child item."""
    client = _StaticAIClient(_mode_b_judgment_payload(fixture))

    result = ModeBAnswerComponent(
        client, prompt_registry=_StaticPromptRegistry()
    ).run(_question(fixture))

    assert client.calls == ["mode_b_answer"]
    assert len(result["questions"]) == len(fixture["subquestions"])
    assert all("options" not in item for item in result["questions"])
    assert [item["subquestion_label"] for item in result["questions"]] == [
        item["label"] for item in fixture["subquestions"]
    ]


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_mode_a_accepts_one_explanation_step_per_judgment_subquestion(fixture):
    """Mode A must preserve every child judgment instead of its legacy 3-5 steps."""
    client = _StaticAIClient(_mode_a_judgment_payload(fixture))

    result = ModeAAnswerComponent(
        client, prompt_registry=_StaticPromptRegistry()
    ).run(_question(fixture))

    assert len(result["steps"]) == len(fixture["subquestions"])
    assert [item["subquestion_label"] for item in result["steps"]] == [
        item["label"] for item in fixture["subquestions"]
    ]
    assert all(item["judgment"] in {"TRUE", "FALSE"} for item in result["steps"])


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_mode_c_accepts_one_guiding_question_per_judgment_subquestion(fixture):
    """Mode C must preserve every child judgment instead of its legacy 3-5 questions."""
    client = _StaticAIClient(_mode_c_judgment_payload(fixture))

    result = ModeCAnswerComponent(
        client, prompt_registry=_StaticPromptRegistry()
    ).run(_question(fixture))

    assert len(result["questions"]) == len(fixture["subquestions"])
    assert [item["subquestion_label"] for item in result["questions"]] == [
        item["label"] for item in fixture["subquestions"]
    ]
    assert all(item["reference_answer"] in {"TRUE", "FALSE"} for item in result["questions"])


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_mode_b_prompt_context_includes_every_judgment_subquestion(fixture):
    """The model must never receive only the generic parent stem of a multipart question."""
    variables = ModeBAnswerComponent(
        _StaticAIClient(_mode_b_judgment_payload(fixture)),
        prompt_registry=_StaticPromptRegistry(),
    ).prompt_variables(_question(fixture))

    question_text = variables["normalized_text"]
    assert fixture["stem"] in question_text
    for child in fixture["subquestions"]:
        assert child["label"] in question_text
        assert child["stem"] in question_text


@pytest.mark.parametrize(
    ("component_type", "payload_factory"),
    (
        (ModeAAnswerComponent, _mode_a_judgment_payload),
        (ModeBAnswerComponent, _mode_b_judgment_payload),
        (ModeCAnswerComponent, _mode_c_judgment_payload),
    ),
)
@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_all_mode_prompts_include_every_judgment_subquestion(
    component_type, payload_factory, fixture
):
    """Every mode must see the full child-question context, not only the parent stem."""
    variables = component_type(
        _StaticAIClient(payload_factory(fixture)),
        prompt_registry=_StaticPromptRegistry(),
    ).prompt_variables(_question(fixture))

    question_text = variables["normalized_text"]
    for child in fixture["subquestions"]:
        assert child["label"] in question_text
        assert child["stem"] in question_text


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_multipart_true_false_answers_are_normalized_and_validated_per_child(fixture):
    """B arbitration compares a stable TRUE/FALSE sequence, never an A-D answer key."""
    result = _mode_b_judgment_payload(fixture)
    answer_contract = result["final_answer"]
    context = {
        "question_type": "true_false",
        "subquestions": fixture["subquestions"],
        "options": [],
    }

    normalized = AnswerNormalizer().normalize(
        answer_contract,
        question_type=context["question_type"],
        subquestion_labels=[item["label"] for item in fixture["subquestions"]],
    )
    validation = ModeContentValidator().validate(
        "B", result, trusted_answer=answer_contract, context=context
    )

    assert normalized.valid is True
    assert normalized.value == answer_contract
    assert validation.valid is True


@pytest.mark.parametrize("mode,payload_factory", (
    ("A", _mode_a_judgment_payload),
    ("B", _mode_b_judgment_payload),
    ("C", _mode_c_judgment_payload),
))
@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_all_modes_validate_multipart_true_false_content(mode, payload_factory, fixture):
    """Arbitration must retain one valid child result in every mode."""
    result = payload_factory(fixture)
    context = {
        "question_type": "true_false",
        "subquestions": fixture["subquestions"],
        "options": [],
    }

    validation = ModeContentValidator().validate(
        mode,
        result,
        trusted_answer=result["final_answer"],
        context=context,
    )

    assert validation.valid is True


@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_unanswered_mode_b_arbitration_keeps_a_valid_multipart_judgment_payload(fixture):
    """The final service boundary must not re-apply the legacy A-D Mode B schema."""
    payload = _mode_b_judgment_payload(fixture)
    component = MagicMock()
    component.run.return_value = payload

    service = AIReviewService(component_factory=lambda _component_type: component)
    question = SimpleNamespace(
        stem=fixture["stem"],
        question_type="true_false",
        subquestions=fixture["subquestions"],
        answer="",
        analysis="",
        solution="",
        options=[],
    )

    outcome = service.solve_unanswered_mode_with_arbitration(
        question,
        mode="B",
        baseline={
            "canonical_answer": payload["final_answer"],
            "canonical_analysis": "逐项判断的基线解析。",
            "key_facts": ["每个子题均需独立判断。"],
            "confidence": 0.95,
        },
    )

    assert outcome.answer["final_answer"] == payload["final_answer"]
    assert outcome.answer["questions"] == payload["questions"]


@pytest.mark.parametrize(
    ("mode", "payload_factory", "content_field"),
    (
        ("A", _mode_a_judgment_payload, "steps"),
        ("C", _mode_c_judgment_payload, "questions"),
    ),
)
@pytest.mark.parametrize("fixture", MULTIPART_TRUE_FALSE_FIXTURES, ids=lambda row: row["id"])
def test_unanswered_a_and_c_arbitration_keep_every_child_judgment(
    mode, payload_factory, content_field, fixture
):
    """The final service boundary must use the true/false schema in A and C too."""
    payload = payload_factory(fixture)
    component = MagicMock()
    component.run.return_value = payload
    service = AIReviewService(component_factory=lambda _component_type: component)
    question = SimpleNamespace(
        stem=fixture["stem"],
        question_type="true_false",
        subquestions=fixture["subquestions"],
        answer="",
        analysis="",
        solution="",
        options=[],
    )

    outcome = service.solve_unanswered_mode_with_arbitration(
        question,
        mode=mode,
        baseline={
            "canonical_answer": payload["final_answer"],
            "canonical_analysis": "逐项判断的基线解析。",
            "key_facts": ["每个子题均需独立判断。"],
            "confidence": 0.95,
        },
    )

    assert outcome.answer["final_answer"] == payload["final_answer"]
    assert len(outcome.answer[content_field]) == len(fixture["subquestions"])


def test_small_parallel_multipart_judgment_load_keeps_each_question_contract_isolated():
    """A small local pressure run must not mix child labels between concurrent items."""

    def run_fixture(fixture: dict) -> tuple[str, list[str]]:
        result = ModeBAnswerComponent(
            _StaticAIClient(_mode_b_judgment_payload(fixture)),
            prompt_registry=_StaticPromptRegistry(),
        ).run(_question(fixture))
        return fixture["id"], [item["subquestion_label"] for item in result["questions"]]

    sample = [
        MULTIPART_TRUE_FALSE_FIXTURES[0],
        MULTIPART_TRUE_FALSE_FIXTURES[1],
        MULTIPART_TRUE_FALSE_FIXTURES[0],
        MULTIPART_TRUE_FALSE_FIXTURES[1],
        MULTIPART_TRUE_FALSE_FIXTURES[0],
        MULTIPART_TRUE_FALSE_FIXTURES[1],
    ]
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(run_fixture, sample))

    for fixture, (question_id, labels) in zip(sample, results, strict=True):
        assert question_id == fixture["id"]
        assert labels == [item["label"] for item in fixture["subquestions"]]
