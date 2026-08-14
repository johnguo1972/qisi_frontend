from __future__ import annotations

from copy import deepcopy

import pytest

from apps.common.ai.answer_validation import AnswerNormalizer, ModeContentValidator


NORMALIZER = AnswerNormalizer()
VALIDATOR = ModeContentValidator()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("c", "C"),
        ("\u9009C", "C"),
        ("\u7b54\u6848\uff1aC", "C"),
        ("C\u3002", "C"),
        ("閫塁", "C"),
        ("绛旀锛欳", "C"),
        ("C銆俙", "C"),
    ],
)
def test_normalize_single_choice_recognized_forms(raw, expected):
    normalized = NORMALIZER.normalize(
        raw, question_type="single_choice", option_labels=("A", "B", "C", "D")
    )

    assert normalized.value == expected
    assert normalized.valid is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CA", "AC"),
        ("A,C", "AC"),
        ("C\u3001A\u3001A", "AC"),
        ("\u7b54\u6848\uff1a C\uff0cA", "AC"),
    ],
)
def test_normalize_multiple_choice_sorts_deduplicates_and_accepts_separators(raw, expected):
    normalized = NORMALIZER.normalize(
        raw,
        question_type="multiple_choice",
        option_labels=("A", "B", "C", "D"),
    )

    assert normalized.value == expected
    assert normalized.valid is True


def test_normalize_multiple_choice_rejects_an_option_not_in_the_context():
    normalized = NORMALIZER.normalize(
        "A,E", question_type="multiple_choice", option_labels=("A", "B", "C", "D")
    )

    assert normalized.valid is False
    assert normalized.reason == "option_out_of_range"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", "TRUE"),
        ("\u6b63\u786e", "TRUE"),
        ("\u221a", "TRUE"),
        ("false", "FALSE"),
        ("\u9519\u8bef", "FALSE"),
        ("\u00d7", "FALSE"),
    ],
)
def test_normalize_true_false_aliases_to_stable_boolean_values(raw, expected):
    normalized = NORMALIZER.normalize(raw, question_type="true_false")

    assert normalized.value == expected
    assert normalized.valid is True


@pytest.mark.parametrize(
    ("raw", "reason"),
    [("   ", "blank_answer"), ("missing_conditions", "missing_conditions")],
)
def test_normalize_rejects_blank_and_missing_conditions(raw, reason):
    normalized = NORMALIZER.normalize(raw, question_type="fill_blank")

    assert normalized.valid is False
    assert normalized.reason == reason


def test_normalize_fill_and_unknown_text_only_trim_without_changing_meaning():
    numeric = NORMALIZER.normalize("  -1.5 / 2 m  ", question_type="fill_blank")
    subjective = NORMALIZER.normalize("  I think A is correct.  ", question_type="essay")
    unknown = NORMALIZER.normalize("  explanation mentioning A  ", question_type="unknown")

    assert numeric.value == "-1.5 / 2 m"
    assert subjective.value == "I think A is correct."
    assert unknown.value == "explanation mentioning A"
    assert numeric.valid is subjective.valid is unknown.valid is True


def _mode_a():
    return {
        "mode": "A",
        "steps": [
            {"step": 1, "content": "Read the question."},
            {"step": 2, "content": "Compare the options."},
            {"step": 3, "content": "Choose C."},
        ],
        "final_answer": "C",
        "summary": "The result is C.",
        "missing_conditions": [],
    }


def _mode_b():
    return {
        "mode": "B",
        "questions": [
            {
                "question": "Which option follows?",
                "options": {"A": "one", "B": "two", "C": "three", "D": "four"},
                "correct_option": "C",
                "reference_answer": "C is correct.",
                "analysis": "The rule selects C.",
                "correct_answer": "C",
                "explanation": "The rule selects C.",
            }
            for _ in range(3)
        ],
        "final_answer": "C",
        "summary": "The result is C.",
    }


def _mode_c():
    return {
        "mode": "C",
        "questions": [
            {
                "question": "What is the first observation?",
                "reference_answer": "Use the stated condition.",
                "key_points": ["condition"],
                "followup_hint": "Read the condition again.",
            }
            for _ in range(3)
        ],
        "final_answer": "C",
        "summary": "The result is C.",
    }


CHOICE_CONTEXT = {
    "question_type": "single_choice",
    "options": [
        {"label": "A", "content": "one"},
        {"label": "B", "content": "two"},
        {"label": "C", "content": "three"},
        {"label": "D", "content": "four"},
    ],
}


@pytest.mark.parametrize("mode,result_factory", [("A", _mode_a), ("B", _mode_b), ("C", _mode_c)])
def test_all_modes_reject_a_normalized_final_answer_conflict(mode, result_factory):
    validation = VALIDATOR.validate(
        mode, result_factory(), trusted_answer="A", context=CHOICE_CONTEXT
    )

    assert validation.valid is False
    assert validation.issues == ("final_answer_conflict",)


def test_mode_a_rejects_missing_conditions_for_a_complete_choice_context():
    result = _mode_a()
    result["missing_conditions"] = ["Need the choices."]

    validation = VALIDATOR.validate("A", result, trusted_answer="C", context=CHOICE_CONTEXT)

    assert validation.valid is False
    assert validation.issues == ("false_missing_conditions",)


@pytest.mark.parametrize(
    "claim",
    [
        "\u672a\u63d0\u4f9b\u9009\u9879",
        "\u6ca1\u6709\u63d0\u4f9b\u9009\u9879",
        "鏈彁渚涢€夐」",
        "娌℃湁鎻愪緵閫夐」",
    ],
)
def test_complete_choice_content_rejects_explicit_claims_that_options_are_missing(claim):
    result = _mode_a()
    result["steps"][0]["content"] = claim

    validation = VALIDATOR.validate("A", result, trusted_answer="C", context=CHOICE_CONTEXT)

    assert validation.valid is False
    assert validation.issues == ("claims_options_missing",)


@pytest.mark.parametrize("mode,result_factory", [("A", _mode_a), ("B", _mode_b), ("C", _mode_c)])
def test_valid_representative_mode_shapes_pass(mode, result_factory):
    validation = VALIDATOR.validate(
        mode, result_factory(), trusted_answer="\u7b54\u6848\uff1aC", context=CHOICE_CONTEXT
    )

    assert validation.valid is True
    assert validation.issues == ()


def test_mode_a_accepts_its_optional_missing_conditions_field_when_omitted():
    result = _mode_a()
    result.pop("missing_conditions")

    validation = VALIDATOR.validate("A", result, trusted_answer="C", context=CHOICE_CONTEXT)

    assert validation.valid is True
    assert validation.issues == ()


def test_validator_orders_and_deduplicates_issues_without_mutating_inputs():
    result = _mode_a()
    result["final_answer"] = "E"
    result["missing_conditions"] = ["Need choices.", "Need choices."]
    result["steps"][0]["content"] = "\u672a\u63d0\u4f9b\u9009\u9879"
    result["steps"] = result["steps"][:2]
    original_result = deepcopy(result)
    original_context = deepcopy(CHOICE_CONTEXT)

    validation = VALIDATOR.validate("A", result, trusted_answer="C", context=CHOICE_CONTEXT)

    assert validation.valid is False
    assert validation.issues == (
        "invalid_final_answer",
        "false_missing_conditions",
        "claims_options_missing",
        "mode_schema_incomplete",
    )
    assert result == original_result
    assert CHOICE_CONTEXT == original_context


def test_mode_b_rejects_reviewer_a_d_c_answer_field_contradiction():
    result = _mode_b()
    result["questions"][0].update(
        correct_option="A",
        correct_answer="D",
        reference_answer="C",
    )

    validation = VALIDATOR.validate(
        "B", result, trusted_answer="C", context=CHOICE_CONTEXT
    )

    assert validation.valid is False
    assert "mode_b_answer_conflict" in validation.issues


def test_mode_b_accepts_consistent_option_keys_and_ignores_explanatory_reference_text():
    result = _mode_b()
    result["questions"][0]["reference_answer"] = "C follows from the stated rule."

    validation = VALIDATOR.validate(
        "B", result, trusted_answer="C", context=CHOICE_CONTEXT
    )

    assert validation.valid is True


def test_mode_c_checks_exact_option_key_reference_but_not_explanatory_text():
    conflicting = _mode_c()
    conflicting["questions"][0]["reference_answer"] = "D"
    explanatory = _mode_c()
    explanatory["questions"][0]["reference_answer"] = "D is a distractor; C is correct."

    conflict = VALIDATOR.validate(
        "C", conflicting, trusted_answer="C", context=CHOICE_CONTEXT
    )
    valid = VALIDATOR.validate(
        "C", explanatory, trusted_answer="C", context=CHOICE_CONTEXT
    )

    assert "mode_c_answer_conflict" in conflict.issues
    assert valid.valid is True
