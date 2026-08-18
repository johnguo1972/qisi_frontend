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
from apps.common.ai.schemas import IndependentVerificationResponse
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


def test_trusted_cross_mode_evidence_avoids_repeating_independent_solution():
    """A verified canonical conclusion may validate another mode's Qwen content."""
    context = _context(question_type="calculation")
    first_calls = _Calls(_qwen("A", answer="C"), _independent("A", answer="C"), _final())
    first = _arbitrator(first_calls).process("A", context)

    second_calls = _Calls(
        _qwen(
            "B",
            answer="C",
            key_facts=["The supplied fact determines the answer."],
        ),
        AssertionError("a trusted canonical answer must be reused"),
        _final("B", answer="C"),
    )
    second = _arbitrator(second_calls).process(
        "B", context, cached_verification=first.shared_verifier_result
    )

    _assert_counts(first_calls, 1, 1, 0)
    _assert_counts(second_calls, 1, 0, 0)
    assert second.answer["final_answer"] == "C"
    assert second.verification["deepseek_thinking_enabled"] is True
    assert "independent_verification_cached" in second.verification["warnings"]


def test_trusted_cross_mode_evidence_never_accepts_a_conflicting_qwen_answer():
    """Cross-mode reuse is a proof source, not permission to bypass conflicts."""
    context = _context(question_type="calculation")
    first_calls = _Calls(_qwen("A", answer="C"), _independent("A", answer="C"), _final())
    first = _arbitrator(first_calls).process("A", context)

    second_calls = _Calls(
        _qwen("B", answer="B"),
        _independent("B", answer="C"),
        _final("B", answer="C"),
    )
    second = _arbitrator(second_calls).process(
        "B", context, cached_verification=first.shared_verifier_result
    )

    _assert_counts(second_calls, 1, 0, 1)
    assert second.answer["final_answer"] == "C"


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


def test_reference_qwen_mismatch_and_contradictory_independent_requires_final_review():
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="B"),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"
    assert "reference_answer_conflict" in outcome.verification["warnings"]


def test_matching_candidates_accept_qwen_when_explicit_qwen_key_facts_cover_independent_facts():
    context = _reference_context(answer="", analysis="")
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(
            answer="B",
            reference_answer_valid=None,
            reference_analysis_valid=None,
        ),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"


@pytest.mark.parametrize(
    "qwen_overrides",
    [
        {},
        {"key_facts": []},
        {"key_facts": ["A different fact."]},
    ],
    ids=["fact_unproven", "fact_empty", "fact_conflict"],
)
def test_matching_candidates_require_final_review_when_qwen_facts_do_not_cover_independent_facts(qwen_overrides):
    calls = _Calls(
        _qwen(answer="B", **qwen_overrides),
        _independent(answer="B"),
        _final(answer="B"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


def test_no_reference_matching_candidates_require_final_review_when_qwen_facts_are_unproven():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="B", reference_answer_valid=None),
        _final(answer="B"),
    )

    outcome = _arbitrator(calls).process("A", _context(answer=""))

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


def test_matching_candidates_accept_qwen_when_canonical_visible_content_exactly_covers_facts():
    context = _reference_context(answer="", analysis="")
    calls = _Calls(
        _qwen(answer="B", summary="  The supplied fact determines the answer.  "),
        _independent(
            answer="B",
            reference_answer_valid=None,
            reference_analysis_valid=None,
        ),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"


def test_all_three_different_answers_require_final_review():
    calls = _Calls(_qwen(answer="B"), _independent(answer="D"), _final(answer="C"))

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"


def test_no_valid_reference_with_matching_candidates_accepts_qwen_when_valid_and_confident():
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="B", reference_answer_valid=None),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", _context(answer=""))

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"


def test_no_valid_reference_with_different_candidates_requires_final_review():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="D", reference_answer_valid=None),
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


@pytest.mark.parametrize("reference_answer_valid", [False])
def test_available_reference_with_missing_or_invalid_independent_reference_finding_requires_final_review(
    reference_answer_valid,
):
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="C", reference_answer_valid=reference_answer_valid),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 1)
    assert outcome.verification["selected_content_provider"] == "deepseek_final_review"


def test_available_reference_with_null_independent_reference_finding_fails_closed():
    calls = _Calls(
        _qwen(answer="B"),
        _independent(answer="C", reference_answer_valid=None),
        _final(answer="C"),
    )

    with pytest.raises(ArbitrationProviderError):
        _arbitrator(calls).process("A", _context())


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
    context = _reference_context(answer="", analysis="")
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="D"),
        _final(answer="B"),
    )
    cache = {
        "context_hash": ModeAnswerArbitrator.context_hash(context),
        "independent_answer": "B",
        "reference_answer_valid": None,
        "reference_analysis_valid": None,
        "reference_issues": [],
        "key_facts": ["The supplied fact determines the answer."],
        "confidence": 0.9,
        "mode_content": _mode_content("A", "B"),
    }

    outcome = _arbitrator(calls).process("A", context, cached_verification=cache)

    _assert_counts(calls, 1, 0, 0)
    assert outcome.verification["selected_content_provider"] == "qwen"
    assert outcome.shared_verifier_result["independent_answer"] == "B"
    assert "mode_content" not in outcome.shared_verifier_result


def test_mismatching_cache_hash_forces_a_new_independent_call():
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="C"),
        _final(),
    )
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
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="C"),
        _final(),
    )
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
    context = _reference_context(answer="", analysis="")
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(
            answer="B",
            confidence=0.80,
            reference_answer_valid=None,
            reference_analysis_valid=None,
        ),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", context)

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


def _reference_context(*, answer="C", analysis="Reference analysis."):
    return QuestionInput(
        stem="Which statement is correct?",
        options=[
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ],
        answer=answer,
        solution=analysis,
        metadata={
            "question_type": "single_choice",
            "reference_analysis": analysis,
        },
    )


def _component_shaped_independent(*, answer="C", answer_flag=True, analysis_flag=True):
    return IndependentVerificationResponse.model_validate(
        {
            "independent_answer": answer,
            "independent_reasoning_summary": "Solved independently from the question facts.",
            "key_facts": ["The supplied fact determines the answer."],
            "reference_answer_valid": answer_flag,
            "reference_analysis_valid": analysis_flag,
            "reference_issues": [],
            "confidence": 0.93,
            "mode_content": _mode_content("A", answer),
        }
    ).model_dump(exclude_none=True)


@pytest.mark.parametrize(
    ("reference_answer", "reference_analysis", "answer_flag", "analysis_flag"),
    [
        ("", "", None, None),
        ("C", "", True, None),
        ("", "Reference analysis.", None, True),
        ("C", "Reference analysis.", True, True),
    ],
    ids=["no_references", "answer_only", "analysis_only", "both_references"],
)
def test_component_shaped_nullable_reference_flags_follow_the_canonical_context(
    reference_answer, reference_analysis, answer_flag, analysis_flag
):
    context = _reference_context(
        answer=reference_answer, analysis=reference_analysis
    )
    selected = reference_answer or "B"
    independent = _component_shaped_independent(
        answer=selected,
        answer_flag=answer_flag,
        analysis_flag=analysis_flag,
    )
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        independent,
        _final(answer=selected),
    )

    outcome = _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)
    assert outcome.verification["trusted_answer"] == selected
    assert outcome.shared_verifier_result["reference_answer_valid"] is answer_flag
    assert outcome.shared_verifier_result["reference_analysis_valid"] is analysis_flag


@pytest.mark.parametrize(
    ("reference_answer", "reference_analysis", "missing_flag"),
    [
        ("C", "", "reference_answer_valid"),
        ("", "Reference analysis.", "reference_analysis_valid"),
        ("C", "Reference analysis.", "reference_answer_valid"),
        ("C", "Reference analysis.", "reference_analysis_valid"),
    ],
)
def test_missing_reference_flag_fails_closed_when_that_reference_exists(
    reference_answer, reference_analysis, missing_flag
):
    independent = _component_shaped_independent(
        answer=reference_answer or "B",
        answer_flag=True if reference_answer else None,
        analysis_flag=True if reference_analysis else None,
    )
    independent.pop(missing_flag, None)
    calls = _Calls(_qwen(answer="B"), independent, _final())

    with pytest.raises(ArbitrationProviderError):
        _arbitrator(calls).process(
            "A",
            _reference_context(
                answer=reference_answer, analysis=reference_analysis
            ),
        )


def test_independent_result_cannot_validate_a_different_reference_answer():
    calls = _Calls(
        _qwen(
            answer="B",
            key_facts=["The supplied fact determines the answer."],
        ),
        _independent(answer="B", reference_answer_valid=True),
        _final(answer="C"),
    )

    outcome = _arbitrator(calls).process("A", _context(answer="C"))

    _assert_counts(calls, 1, 1, 1)
    assert outcome.answer["final_answer"] == "C"
    assert "independent_reference_answer_conflict" in outcome.verification["warnings"]


@pytest.mark.parametrize(
    "options",
    [
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "C", "content": "four"},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "three"},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": ""},
        ],
        [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "1", "content": "four"},
        ],
    ],
    ids=["duplicate_label", "duplicate_content", "blank_content", "invalid_label"],
)
def test_invalid_choice_options_cannot_take_the_qwen_only_fast_path(options):
    context = QuestionInput(
        stem="Choose the correct option.",
        options=options,
        answer="C",
        solution="Use the facts.",
        metadata={
            "question_type": "single_choice",
            "reference_analysis": "Use the facts.",
        },
    )
    calls = _Calls(_qwen(answer="C"), _independent(answer="C"), _final())

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)


def test_insufficient_choice_count_cannot_take_the_qwen_only_fast_path():
    context = QuestionInput(
        stem="Choose the correct option.",
        options=[{"label": "A", "content": "one"}],
        answer="A",
        solution="Use the fact.",
        metadata={
            "question_type": "single_choice",
            "reference_analysis": "Use the fact.",
        },
    )
    calls = _Calls(
        _qwen(answer="A"),
        _independent(answer="A", mode_content=_mode_content("A", "A")),
        _final(answer="A"),
    )

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)


def test_visual_dependent_context_without_image_or_usable_facts_requires_independent_verification():
    context = QuestionInput(
        stem="As shown in the figure, which option is correct?",
        options=_context().options,
        answer="C",
        solution="Use the figure.",
        metadata={
            "question_type": "single_choice",
            "reference_analysis": "Use the figure.",
            "vision_result": {"figure_present": True, "diagram_facts": []},
        },
    )
    calls = _Calls(_qwen(answer="C"), _independent(answer="C"), _final())

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)


def test_visual_dependent_context_with_usable_facts_keeps_the_approved_fast_path():
    context = QuestionInput(
        stem="As shown in the figure, which option is correct?",
        options=_context().options,
        answer="C",
        solution="Use the figure.",
        metadata={
            "question_type": "single_choice",
            "reference_analysis": "Use the figure.",
            "vision_result": {
                "figure_present": True,
                "diagram_facts": ["The marked angle is 60 degrees."],
            },
        },
    )
    calls = _Calls(_qwen(answer="C"), _independent(answer="C"), _final())

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 0, 0)


@pytest.mark.parametrize(
    ("context", "qwen"),
    [
        (
            QuestionInput(
                stem="",
                answer="C",
                solution="Reference analysis.",
                metadata={"question_type": "calculation"},
            ),
            _qwen(answer="C"),
        ),
        (_context(), _qwen(answer="C", missing_conditions=["A condition is missing."])),
        (
            QuestionInput(
                stem="Explain your view.",
                answer="A reasoned opinion.",
                solution="Reference analysis.",
                metadata={"question_type": "essay"},
            ),
            _qwen(answer="A reasoned opinion."),
        ),
    ],
    ids=["blank_stem", "reported_missing_conditions", "subjective_text_match"],
)
def test_incomplete_or_subjective_context_cannot_take_the_qwen_only_fast_path(
    context, qwen
):
    answer = context.answer
    calls = _Calls(
        qwen,
        _independent(
            answer=answer,
            mode_content=_mode_content("A", answer),
        ),
        _final(answer=answer),
    )

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)


@pytest.mark.parametrize(
    "question_type",
    ["computation", "fill_blank", "future_constructed_response"],
)
def test_only_allowlisted_objective_types_can_take_the_qwen_only_fast_path(
    question_type,
):
    context = QuestionInput(
        stem="Compute the requested value.",
        answer="2",
        solution="Apply the stated operation.",
        metadata={
            "question_type": question_type,
            "reference_analysis": "Apply the stated operation.",
        },
    )
    calls = _Calls(
        _qwen(answer="2"),
        _independent(
            answer="2",
            mode_content=_mode_content("A", "2"),
        ),
        _final(answer="2"),
    )

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 1, 0)


@pytest.mark.parametrize("question_type", ["true_false", "judgment", "判断题"])
def test_complete_true_false_aliases_keep_the_approved_qwen_fast_path(
    question_type,
):
    context = QuestionInput(
        stem="The statement is true or false.",
        answer="true",
        solution="The statement follows directly from the given fact.",
        metadata={
            "question_type": question_type,
            "reference_analysis": "The statement follows directly.",
        },
    )
    calls = _Calls(
        _qwen(answer="true"),
        _independent(
            answer="true",
            mode_content=_mode_content("A", "true"),
        ),
        _final(answer="true"),
    )

    _arbitrator(calls).process("A", context)

    _assert_counts(calls, 1, 0, 0)


@pytest.mark.parametrize("confidence", [0.01, -0.1, 1.1, "high", True, None])
def test_explicit_low_or_invalid_qwen_confidence_forces_independent_verification(
    confidence,
):
    calls = _Calls(
        _qwen(answer="C", confidence=confidence),
        _independent(answer="C"),
        _final(),
    )

    _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 1, 0)


def test_valid_explicit_qwen_confidence_is_preserved_on_fast_acceptance():
    calls = _Calls(
        _qwen(answer="C", confidence=0.81),
        _independent(answer="C"),
        _final(),
    )

    outcome = _arbitrator(calls).process("A", _context())

    _assert_counts(calls, 1, 0, 0)
    assert outcome.verification["confidence"] == 0.81


def test_accepted_final_answer_is_a_canonical_copy_without_mutating_candidate():
    candidate = _qwen(answer="c")
    original = deepcopy(candidate)
    calls = _Calls(candidate, _independent(answer="C"), _final())

    outcome = _arbitrator(calls).process("A", _context(answer="C"))

    assert outcome.answer["final_answer"] == "C"
    assert outcome.verification["trusted_answer"] == "C"
    assert candidate == original
