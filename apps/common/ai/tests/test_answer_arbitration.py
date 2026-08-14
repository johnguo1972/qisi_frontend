"""Decision-table coverage for the pure mode-answer arbitrator."""

from __future__ import annotations

from copy import deepcopy

import pytest

from apps.common.ai.answer_arbitration import (
    ArbitrationProviderError,
    HumanReviewRequired,
    ModeAnswerArbitrator,
)
from apps.common.ai.components.base import QuestionInput
from apps.common.exceptions import AIRequestError


QWEN_MARKER = "UNIQUE_QWEN_MARKER_MUST_NOT_REACH_INDEPENDENT"


def _context(*, answer="C", analysis="Reference analysis.", question_type="single_choice"):
    return QuestionInput(
        stem="Which statement is correct?",
        options=[
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
        answer=answer,
        solution="Use the supplied facts.",
        metadata={"question_type": question_type, "reference_analysis": analysis},
    )


def _mode_content(mode="A", answer="C"):
    if mode == "A":
        return {
            "mode": "A",
            "steps": [
                {"step": 1, "content": "Read the facts."},
                {"step": 2, "content": "Eliminate unsupported choices."},
                {"step": 3, "content": "Select the supported choice."},
            ],
            "final_answer": answer,
            "summary": "The facts select the answer.",
            "missing_conditions": [],
        }
    if mode == "B":
        return {
            "mode": "B",
            "questions": [
                {
                    "question": f"Prompt {index}",
                    "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
                    "correct_option": answer,
                    "reference_answer": answer,
                    "analysis": "Use the facts.",
                    "correct_answer": answer,
                    "explanation": "The facts select this choice.",
                }
                for index in range(3)
            ],
            "final_answer": answer,
            "summary": "Practise the same fact pattern.",
        }
    return {
        "mode": "C",
        "questions": [
            {
                "question": f"Prompt {index}",
                "reference_answer": answer,
                "key_points": ["Use the stated fact."],
                "followup_hint": "Check the stated condition.",
            }
            for index in range(3)
        ],
        "final_answer": answer,
        "summary": "Use the key fact consistently.",
    }


def _qwen(mode="A", answer="C", **overrides):
    result = _mode_content(mode, answer)
    result.update(overrides)
    return result


def _independent(mode="A", answer="C", **overrides):
    result = {
        "independent_answer": answer,
        "independent_reasoning_summary": "Independent result used the supplied facts.",
        "key_facts": ["The supplied fact determines the answer."],
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "confidence": 0.9,
        "mode_content": _mode_content(mode, answer),
    }
    result.update(overrides)
    return result


def _final(mode="A", answer="C", **overrides):
    result = {
        "trusted_answer": answer,
        "qwen_content_valid": True,
        "candidate_issues": [],
        "confidence": 0.95,
        "mode_content": _mode_content(mode, answer),
    }
    result.update(overrides)
    return result


class _Calls:
    def __init__(self, qwen, independent, final):
        self.qwen_result = qwen
        self.independent_result = independent
        self.final_result = final
        self.generate_calls = []
        self.independent_calls = []
        self.final_calls = []

    def generate(self, mode, context):
        self.generate_calls.append((mode, context))
        if isinstance(self.qwen_result, Exception):
            raise self.qwen_result
        return self.qwen_result

    def independent_verify(self, mode, context):
        self.independent_calls.append((mode, context))
        if isinstance(self.independent_result, Exception):
            raise self.independent_result
        return self.independent_result

    def final_review(self, mode, context, qwen_result, independent_result, conflicts):
        self.final_calls.append((mode, context, qwen_result, independent_result, conflicts))
        if isinstance(self.final_result, Exception):
            raise self.final_result
        return self.final_result


def _arbitrator(calls):
    return ModeAnswerArbitrator(
        generate=calls.generate,
        independent_verify=calls.independent_verify,
        final_review=calls.final_review,
    )


def _assert_counts(calls, generate, independent, final):
    assert (len(calls.generate_calls), len(calls.independent_calls), len(calls.final_calls)) == (
        generate,
        independent,
        final,
    )


def test_import_contract_is_available():
    """Catch a missing public state-machine interface before branch coverage."""
    assert callable(ModeAnswerArbitrator)


def test_matching_reference_and_qwen_accepts_qwen_without_deepseek():
    calls = _Calls(_qwen(answer="C"), _independent(), _final())

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 0, 0)
    assert outcome.answer["final_answer"] == "C"
    assert outcome.verification["selected_content_provider"] == "qwen"
    assert outcome.verification["deepseek_thinking_enabled"] is False
    assert outcome.shared_verifier_result is None


def test_matching_answer_with_invalid_qwen_content_uses_complete_independent_content():
    calls = _Calls(
        _qwen(answer="C", steps=[]),
        _independent(answer="C"),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "deepseek_independent"
    assert outcome.answer["steps"] == _mode_content()["steps"]


def test_matching_answer_with_invalid_content_escalates_when_independent_content_cannot_repair_mode():
    calls = _Calls(
        _qwen(answer="C", steps=[]),
        _independent(answer="C", mode_content={"mode": "A", "final_answer": "C"}),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


def test_matching_answer_with_invalid_content_escalates_when_independent_answer_disagrees():
    calls = _Calls(
        _qwen(answer="C", steps=[]),
        _independent(answer="B"),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


def test_reference_qwen_mismatch_and_independent_reference_uses_deepseek_content():
    calls = _Calls(_qwen(answer="B"), _independent(answer="C"), _final())

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)
    assert outcome.answer["final_answer"] == "C"
    assert outcome.verification["selected_content_provider"] == "deepseek_independent"


def test_reference_qwen_mismatch_and_incomplete_independent_content_requires_final_review():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="C", mode_content={"mode": "A", "final_answer": "C"}),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"


def test_reference_qwen_mismatch_and_matching_independent_accepts_qwen_with_confidence():
    calls = _Calls(_qwen(answer="B"), _independent(answer="B"), _final())

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)
    assert outcome.answer["final_answer"] == "B"
    assert outcome.verification["selected_content_provider"] == "qwen"
    assert "reference_answer_conflict" in outcome.verification["warnings"]


def test_all_three_different_answers_require_final_review():
    calls = _Calls(_qwen(answer="B"), _independent(answer="D"), _final(answer="C"))

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"


def test_no_valid_reference_with_matching_candidates_accepts_qwen_when_valid_and_confident():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="B", reference_answer_valid=None, reference_analysis_valid=None),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", _context(answer=""))

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"


def test_no_valid_reference_with_different_candidates_requires_final_review():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="D", reference_answer_valid=None, reference_analysis_valid=None),
        _final(answer="B"),
    )

    outcome = _arbitrator(calls).process("A", _context(answer=""))

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "B"


def test_low_independent_confidence_requires_final_review_at_documented_threshold():
    calls = _Calls(_qwen(answer="B"), _independent(answer="B", confidence=0.79), _final(answer="B"))

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["confidence"] == 0.95


def test_explicit_invalid_reference_analysis_requires_final_review():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="B", reference_analysis_valid=False),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"


def test_malformed_independent_result_fails_closed():
    calls = _Calls(_qwen(answer="B"), {"independent_answer": "B"}, _final())

    with pytest.raises(ArbitrationProviderError, match="arbitration_provider_failure"):
        _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)


def test_genuine_missing_conditions_requires_human_review_and_never_selects_qwen():
    calls = _Calls(_qwen(answer="B"), _independent(answer="missing_conditions"), _final())

    with pytest.raises(HumanReviewRequired, match="missing_conditions"):
        _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)


def test_independent_stage_never_receives_qwen_marker_or_context_mutation():
    qwen = _qwen(answer="B", marker=QWEN_MARKER)
    calls = _Calls(qwen, _independent(answer="B"), _final())
    context = _context()
    original_metadata = context.metadata

    _arbitrator(calls).process("A", context)

    independent_context = calls.independent_calls[0][1]
    assert QWEN_MARKER not in repr(independent_context.metadata)
    assert context.metadata == original_metadata
    assert "qwen_result" not in independent_context.metadata


def test_matching_context_hash_reuses_only_safe_cached_first_stage_fields():
    calls = _Calls(_qwen(answer="B"), _independent(answer="D"), _final(answer="B"))
    cache = {
        "context_hash": ModeAnswerArbitrator.context_hash(_context()),
        "independent_answer": "B",
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "key_facts": ["The supplied fact determines the answer."],
        "confidence": 0.9,
        "mode_content": _mode_content("A", "B"),
    }

    outcome = _arbitrator(calls).process("A", _context(), cached_verification=cache)

    _assert_counts(calls, 1, 0, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"
    assert outcome.shared_verifier_result["independent_answer"] == "B"
    assert "mode_content" not in outcome.shared_verifier_result


def test_mismatching_cache_hash_forces_a_new_independent_call():
    calls = _Calls(_qwen(answer="B"), _independent(answer="B"), _final())
    cache = {
        "context_hash": "wrong",
        "independent_answer": "B",
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "key_facts": ["fact"],
        "confidence": 0.9,
    }

    _arbitrator(calls).process("A", _context(), cached_verification=cache)

    _assert_counts(calls, 1, 1, 0)


def test_incomplete_cached_verification_forces_a_new_independent_call():
    calls = _Calls(_qwen(answer="B"), _independent(answer="B"), _final())
    cache = {
        "context_hash": ModeAnswerArbitrator.context_hash(_context()),
        "independent_answer": "B",
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "confidence": 0.9,
    }

    _arbitrator(calls).process("A", _context(), cached_verification=cache)

    _assert_counts(calls, 1, 1, 0)


def test_confidence_at_threshold_accepts_the_matching_qwen_candidate():
    calls = _Calls(_qwen(answer="B"), _independent(answer="B", confidence=0.80), _final())

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"


@pytest.mark.parametrize("mode", ["B", "C"])
def test_cached_mode_content_is_never_reused_across_modes(mode):
    calls = _Calls(_qwen(mode, "B"), _independent(mode, "B"), _final(mode, "B"))
    cache = {
        "context_hash": ModeAnswerArbitrator.context_hash(_context()),
        "independent_answer": "C",
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "key_facts": ["fact"],
        "confidence": 0.9,
        "mode_content": _mode_content("A", "C"),
    }

    outcome = _arbitrator(calls).process(mode, _context(), cached_verification=cache)

    _assert_counts(calls, 1, 0, 1)
    assert outcome.answer["mode"] == mode
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


@pytest.mark.parametrize("required_stage", ["generate", "independent", "final"])
def test_required_provider_failure_fails_closed(required_stage):
    failure = AIRequestError("provider failed")
    qwen = failure if required_stage == "generate" else _qwen(answer="B")
    independent = failure if required_stage == "independent" else _independent(answer="D")
    final = failure if required_stage == "final" else _final(answer="C")
    calls = _Calls(qwen, independent, final)

    with pytest.raises(ArbitrationProviderError, match="arbitration_provider_failure"):
        _arbitrator(calls).process("A", _context())

    expected = {
        "generate": (1, 0, 0),
        "independent": (1, 1, 0),
        "final": (1, 1, 1),
    }[required_stage]
    _assert_counts(calls, *expected)


@pytest.mark.parametrize("malformed", [None, {}, {"trusted_answer": "C"}])
def test_malformed_final_review_fails_closed(malformed):
    calls = _Calls(_qwen(answer="B"), _independent(answer="D"), malformed)

    with pytest.raises(ArbitrationProviderError, match="arbitration_provider_failure"):
        _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)


def test_final_review_trusted_answer_and_content_conflict_fails_closed():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="D"),
        _final(answer="C", mode_content=_mode_content("A", "B")),
    )

    with pytest.raises(ArbitrationProviderError, match="arbitration_provider_failure"):
        _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)


def test_injected_results_and_context_are_not_mutated_and_verification_has_no_reasoning_or_raw_data():
    qwen = _qwen(answer="B")
    independent = _independent(answer="B")
    final = _final(answer="C")
    before = deepcopy((qwen, independent, final))
    calls = _Calls(qwen, independent, final)

    outcome = _arbitrator(calls).process("A", _context())

    assert (qwen, independent, final) == before
    assert "independent_reasoning_summary" not in outcome.verification
    assert "raw_response" not in outcome.verification
    assert "mode_content" not in outcome.shared_verifier_result
    assert outcome.answer["verification"] == outcome.verification


@pytest.mark.parametrize("mode", ["B", "C"])
def test_mode_specific_content_shapes_are_preserved(mode):
    calls = _Calls(_qwen(mode, "C"), _independent(mode, "C"), _final(mode, "C"))

    outcome = _arbitrator(calls).process(mode, _context())

    _assert_counts(calls, 1, 0, 0)
    assert outcome.answer["mode"] == mode
    assert ("questions" in outcome.answer) is True
