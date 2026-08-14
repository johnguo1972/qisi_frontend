"""Behavior tests for immutable question context used by answer solvers."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from importlib import import_module
import json
from types import SimpleNamespace

import pytest


class FakeOptionsManager:
    """Minimal related-manager double with deliberately unstable source rows."""

    def __init__(self, rows):
        self.rows = list(rows)
        self.all_called = False
        self.order_by_calls: list[tuple[str, ...]] = []

    def all(self):
        self.all_called = True
        return self

    def order_by(self, *fields):
        self.order_by_calls.append(fields)
        return self.rows

    def __repr__(self):  # pragma: no cover - catches accidental serialization
        return "<FakeRelatedManager options>"


def _question_context_module():
    """Import inside the test so a missing interface produces a RED failure."""
    return import_module("apps.common.ai.question_context")


def _question():
    manager = FakeOptionsManager(
        [
            SimpleNamespace(option_label="D", content="four", sort_order=3),
            SimpleNamespace(option_label="B", content="two", sort_order=1),
            SimpleNamespace(option_label="A", content="one", sort_order=0),
            SimpleNamespace(option_label="C", content="three", sort_order=2),
        ]
    )
    return SimpleNamespace(
        stem="Which option is correct?",
        options=manager,
        answer="C",
        analysis="Existing analysis explains the third option.",
        solution="Existing solution substitutes the values.",
        question_type="single_choice",
        subject="physics",
        difficulty="0.75",
        material="A material passage",
        tables=[{"title": "measurements", "rows": [["x", "1"]]}],
        subquestions=[{"stem": "sub-question"}],
    ), manager


def _build_context(*, target_mode="A", vision_result=None):
    context = _question_context_module()
    question, manager = _question()
    question_input = context.QuestionContextBuilder.build(
        question,
        image_urls=("https://example.test/diagram.png",),
        normalized_text="normalized option question",
        vision_result=(
            {"figure_present": True, "visual_summary": "a labelled diagram"}
            if vision_result is None
            else vision_result
        ),
        knowledge_refs="kinematics",
        target_mode=target_mode,
    )
    return context, question_input, manager


def test_builder_creates_immutable_plain_context_with_ordered_related_options():
    """Catch a builder that keeps a manager or trusts its shuffled iteration order."""
    _context, question_input, manager = _build_context()

    assert manager.all_called is True
    assert manager.order_by_calls
    assert question_input.options == (
        {"label": "A", "content": "one"},
        {"label": "B", "content": "two"},
        {"label": "C", "content": "three"},
        {"label": "D", "content": "four"},
    )
    assert question_input.answer == "C"
    assert question_input.solution == "Existing solution substitutes the values."
    assert question_input.metadata["reference_analysis"] == (
        "Existing analysis explains the third option."
    )
    with pytest.raises(FrozenInstanceError):
        question_input.stem = "changed"
    with pytest.raises(TypeError):
        question_input.metadata["subject"] = "math"


def test_payload_contains_complete_plain_question_data_and_safe_defaults():
    """Catch a payload that omits reference data or leaks a related manager."""
    context, question_input, manager = _build_context()

    payload = context.question_context_payload(question_input)

    assert payload == {
        "stem": "Which option is correct?",
        "options": [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
        "reference_answer": "C",
        "reference_analysis": "Existing analysis explains the third option.",
        "reference_solution": "Existing solution substitutes the values.",
        "question_type": "single_choice",
        "subject": "physics",
        "difficulty": "0.75",
        "material": "A material passage",
        "tables": [{"title": "measurements", "rows": [["x", "1"]]}],
        "subquestions": [{"stem": "sub-question"}],
        "image_urls": ["https://example.test/diagram.png"],
        "normalized_text": "normalized option question",
        "vision_result": {
            "figure_present": True,
            "visual_summary": "a labelled diagram",
        },
        "knowledge_refs": "kinematics",
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert repr(manager) not in serialized
    assert "FakeRelatedManager" not in serialized


def test_payload_defaults_are_json_safe_when_optional_question_data_is_absent():
    """Catch optional fields becoming null managers or non-JSON Python values."""
    context = _question_context_module()
    question_input = context.QuestionContextBuilder.build(SimpleNamespace(stem="only stem"))

    payload = context.question_context_payload(question_input)

    assert payload["options"] == []
    assert payload["reference_answer"] == ""
    assert payload["reference_analysis"] == ""
    assert payload["reference_solution"] == ""
    assert payload["tables"] == []
    assert payload["subquestions"] == []
    assert payload["image_urls"] == []
    assert payload["vision_result"] == {}
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload


def test_hash_is_deterministic_and_ignores_target_mode_but_covers_answer_facts():
    """Catch a hash that changes by route or misses solver-relevant question facts."""
    context, base, _manager = _build_context(target_mode="A")
    _context, mode_b, _manager = _build_context(target_mode="B")

    base_hash = context.question_context_hash(base)
    assert base_hash == context.question_context_hash(base)
    assert base_hash == context.question_context_hash(mode_b)

    changed_stem = replace(base, stem="A different stem")
    changed_options = replace(
        base,
        options=[
            {"label": "A", "content": "changed one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
    )
    changed_answer = replace(base, answer="A")
    changed_solution = replace(base, solution="A different solution")
    changed_analysis = replace(
        base,
        metadata={**dict(base.metadata), "reference_analysis": "changed analysis"},
    )
    changed_vision = replace(
        base,
        metadata={
            **dict(base.metadata),
            "vision_result": {"figure_present": False},
        },
    )

    for changed in (
        changed_stem,
        changed_options,
        changed_answer,
        changed_solution,
        changed_analysis,
        changed_vision,
    ):
        assert context.question_context_hash(changed) != base_hash


def test_payload_and_hash_canonically_sort_nested_sets():
    """Catch hash-seed-dependent ordering of set values inside question metadata."""
    context = _question_context_module()
    first = context.QuestionInput(
        stem="set ordering",
        metadata={
            "tables": [
                {
                    "groups": [
                        {"delta", "alpha", "charlie", "bravo"},
                        {"four", "one", "three", "two"},
                    ]
                }
            ],
            "vision_result": {"labels": {"south", "north", "east", "west"}},
        },
    )
    second = context.QuestionInput(
        stem="set ordering",
        metadata={
            "tables": [
                {
                    "groups": [
                        set(reversed(("alpha", "bravo", "charlie", "delta"))),
                        set(reversed(("one", "two", "three", "four"))),
                    ]
                }
            ],
            "vision_result": {
                "labels": set(reversed(("north", "east", "south", "west")))
            },
        },
    )

    payload = context.question_context_payload(first)

    assert payload["tables"] == [
        {
            "groups": [
                ["alpha", "bravo", "charlie", "delta"],
                ["four", "one", "three", "two"],
            ]
        }
    ]
    assert payload["vision_result"] == {
        "labels": ["east", "north", "south", "west"]
    }
    assert context.question_context_hash(first) == context.question_context_hash(second)
