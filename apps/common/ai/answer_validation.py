"""Deterministic answer normalization and structural mode-content checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class NormalizedAnswer:
    value: str
    valid: bool
    reason: str = ""


@dataclass(frozen=True)
class ContentValidation:
    valid: bool
    issues: tuple[str, ...]


_QUESTION_TYPE_ALIASES = {
    "single_choice": "single_choice",
    "\u5355\u9009\u9898": "single_choice",
    "multiple_choice": "multiple_choice",
    "\u591a\u9009\u9898": "multiple_choice",
    "fill_blank": "fill_blank",
    "\u586b\u7a7a\u9898": "fill_blank",
    "true_false": "true_false",
    "judgement": "true_false",
    "judgment": "true_false",
    "\u5224\u65ad\u9898": "true_false",
}
_TRUE_FALSE_ALIASES = {
    "true": "TRUE",
    "t": "TRUE",
    "\u6b63\u786e": "TRUE",
    "\u5bf9": "TRUE",
    "\u662f": "TRUE",
    "\u221a": "TRUE",
    "false": "FALSE",
    "f": "FALSE",
    "\u9519\u8bef": "FALSE",
    "\u9519": "FALSE",
    "\u5426": "FALSE",
    "\u00d7": "FALSE",
}
_SINGLE_MOJIBAKE_ALIASES = {
    "閫塁": "C",
    "绛旀锛欳": "C",
    "C銆俙": "C",
}
_ANSWER_PREFIX = re.compile(
    r"^(?:\u7b54\u6848(?:\u662f)?|\u9009(?:\u62e9)?|answer(?:\s+is)?)\s*[:\uff1a]?\s*(.+)$",
    re.IGNORECASE,
)
_SINGLE_OPTION = re.compile(r"^\(?\s*([A-Za-z])\s*\)?\s*[.\u3002]?$" )
_MULTIPLE_OPTION_TEXT = re.compile(r"^[A-Za-z\s,\uff0c\u3001;\uff1b/]+$")
_OPTION_MISSING_CLAIMS = (
    "\u672a\u63d0\u4f9b\u9009\u9879",
    "\u6ca1\u6709\u63d0\u4f9b\u9009\u9879",
    "\u672a\u7ed9\u51fa\u9009\u9879",
    "\u6ca1\u6709\u7ed9\u51fa\u9009\u9879",
    "no options provided",
    "options not provided",
    "鏈彁渚涢€夐」",
    "娌℃湁鎻愪緵閫夐」",
)


def _question_type(value: object) -> str:
    if not isinstance(value, str):
        return "free_response"
    return _QUESTION_TYPE_ALIASES.get(value.strip().casefold(), "free_response")


def _trimmed_text(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    return raw.strip()


def _strip_answer_prefix(value: str) -> str:
    matched = _ANSWER_PREFIX.fullmatch(value)
    return matched.group(1).strip() if matched else value


def _allowed_labels(option_labels: object) -> tuple[str, ...]:
    if not isinstance(option_labels, (list, tuple, set, frozenset)):
        return ()
    labels = {
        value.strip().upper()
        for value in option_labels
        if isinstance(value, str) and len(value.strip()) == 1 and value.strip().isalpha()
    }
    return tuple(sorted(labels))


class AnswerNormalizer:
    """Normalize only established answer notation; preserve all other text."""

    def normalize(
        self, raw: object, *, question_type: object, option_labels=()
    ) -> NormalizedAnswer:
        value = _trimmed_text(raw)
        if value is None:
            return NormalizedAnswer("", False, "answer_not_text")
        if not value:
            return NormalizedAnswer("", False, "blank_answer")
        if value.casefold() == "missing_conditions":
            return NormalizedAnswer(value, False, "missing_conditions")

        kind = _question_type(question_type)
        if kind == "single_choice":
            return self._normalize_single(value, _allowed_labels(option_labels))
        if kind == "multiple_choice":
            return self._normalize_multiple(value, _allowed_labels(option_labels))
        if kind == "true_false":
            canonical = _TRUE_FALSE_ALIASES.get(value.casefold())
            if canonical is None:
                return NormalizedAnswer(value, False, "unrecognized_true_false")
            return NormalizedAnswer(canonical, True)
        return NormalizedAnswer(value, True)

    @staticmethod
    def _normalize_single(value: str, allowed: tuple[str, ...]) -> NormalizedAnswer:
        direct = _SINGLE_MOJIBAKE_ALIASES.get(value)
        if direct is not None:
            candidate = direct
        else:
            matched = _SINGLE_OPTION.fullmatch(_strip_answer_prefix(value))
            if matched is None:
                return NormalizedAnswer(value, False, "unrecognized_single_choice")
            candidate = matched.group(1).upper()
        if allowed and candidate not in allowed:
            return NormalizedAnswer(candidate, False, "option_out_of_range")
        return NormalizedAnswer(candidate, True)

    @staticmethod
    def _normalize_multiple(value: str, allowed: tuple[str, ...]) -> NormalizedAnswer:
        candidate = _strip_answer_prefix(value)
        if not _MULTIPLE_OPTION_TEXT.fullmatch(candidate):
            return NormalizedAnswer(value, False, "unrecognized_multiple_choice")
        labels = sorted({letter.upper() for letter in candidate if letter.isascii() and letter.isalpha()})
        if not labels:
            return NormalizedAnswer(value, False, "unrecognized_multiple_choice")
        if allowed and any(label not in allowed for label in labels):
            return NormalizedAnswer("".join(labels), False, "option_out_of_range")
        return NormalizedAnswer("".join(labels), True)


def _plain_mapping(value: object) -> Mapping[object, object] | None:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            plain = dump()
        except (TypeError, ValueError):
            return None
        return plain if isinstance(plain, Mapping) else None
    return None


def _visible_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _visible_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _visible_strings(item)


def _nonblank_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _option_labels_from_context(context: Mapping[object, object]) -> tuple[str, ...]:
    options = context.get("options", ())
    if isinstance(options, Mapping):
        return _allowed_labels(tuple(options.keys()))
    if not isinstance(options, (list, tuple)):
        return ()
    labels: list[object] = []
    for option in options:
        item = _plain_mapping(option)
        if item is not None:
            labels.append(item.get("label", item.get("option_label", "")))
    return _allowed_labels(tuple(labels))


def _complete_choice_context(context: Mapping[object, object]) -> bool:
    question_type = context.get("question_type", context.get("question_style", ""))
    return _question_type(question_type) in {"single_choice", "multiple_choice"} and len(
        _option_labels_from_context(context)
    ) >= 2


def _has_missing_conditions(result: Mapping[object, object]) -> bool:
    value = result.get("missing_conditions", ())
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return any(_nonblank_string(item) for item in value)
    return False


def _has_option_missing_claim(result: Mapping[object, object]) -> bool:
    return any(
        marker in text.casefold()
        for text in _visible_strings(result)
        for marker in _OPTION_MISSING_CLAIMS
    )


def _valid_steps(value: object) -> bool:
    if not isinstance(value, (list, tuple)) or not 3 <= len(value) <= 5:
        return False
    for item in value:
        step = _plain_mapping(item)
        if step is None or not isinstance(step.get("step"), int) or isinstance(step.get("step"), bool):
            return False
        if not _nonblank_string(step.get("content")):
            return False
    return True


def _valid_mode_b_questions(value: object) -> bool:
    if not isinstance(value, (list, tuple)) or not 3 <= len(value) <= 4:
        return False
    required = (
        "question",
        "correct_option",
        "reference_answer",
        "analysis",
        "correct_answer",
        "explanation",
    )
    for item in value:
        question = _plain_mapping(item)
        options = _plain_mapping(question.get("options")) if question is not None else None
        if question is None or options is None or set(options) != {"A", "B", "C", "D"}:
            return False
        if not all(_nonblank_string(question.get(field)) for field in required):
            return False
        if question.get("correct_option") not in {"A", "B", "C", "D"}:
            return False
        if question.get("correct_answer") not in {"A", "B", "C", "D"}:
            return False
        if not all(_nonblank_string(options.get(label)) for label in ("A", "B", "C", "D")):
            return False
    return True


def _valid_mode_c_questions(value: object) -> bool:
    if not isinstance(value, (list, tuple)) or not 3 <= len(value) <= 5:
        return False
    for item in value:
        question = _plain_mapping(item)
        if question is None:
            return False
        if not all(
            _nonblank_string(question.get(field))
            for field in ("question", "reference_answer", "followup_hint")
        ):
            return False
        key_points = question.get("key_points")
        if not isinstance(key_points, (list, tuple)) or not key_points or not all(
            _nonblank_string(point) for point in key_points
        ):
            return False
    return True


def _schema_complete(mode: str, result: Mapping[object, object]) -> bool:
    if result.get("mode") != mode or not _nonblank_string(result.get("final_answer")) or not _nonblank_string(result.get("summary")):
        return False
    if mode == "A":
        missing = result.get("missing_conditions", ())
        return _valid_steps(result.get("steps")) and isinstance(missing, (list, tuple)) and all(
            _nonblank_string(item) for item in missing
        )
    if mode == "B":
        return _valid_mode_b_questions(result.get("questions"))
    if mode == "C":
        return _valid_mode_c_questions(result.get("questions"))
    return False


class ModeContentValidator:
    """Reject deterministic answer and visible-content defects before arbitration."""

    _ISSUE_ORDER = (
        "invalid_final_answer",
        "trusted_answer_invalid",
        "final_answer_conflict",
        "false_missing_conditions",
        "claims_options_missing",
        "mode_schema_incomplete",
    )

    def __init__(self, normalizer: AnswerNormalizer | None = None) -> None:
        self._normalizer = normalizer or AnswerNormalizer()

    def validate(
        self, mode: object, result: object, *, trusted_answer: object, context: object
    ) -> ContentValidation:
        normalized_mode = mode.strip().upper() if isinstance(mode, str) else ""
        plain_result = _plain_mapping(result)
        plain_context = _plain_mapping(context) or {}
        if plain_result is None:
            return ContentValidation(False, ("mode_schema_incomplete",))

        question_type = plain_context.get(
            "question_type", plain_context.get("question_style", "")
        )
        labels = _option_labels_from_context(plain_context)
        final = self._normalizer.normalize(
            plain_result.get("final_answer"),
            question_type=question_type,
            option_labels=labels,
        )
        trusted = self._normalizer.normalize(
            trusted_answer,
            question_type=question_type,
            option_labels=labels,
        )
        complete_choice = _complete_choice_context(plain_context)
        observed = set()
        if not final.valid:
            observed.add("invalid_final_answer")
        if not trusted.valid:
            observed.add("trusted_answer_invalid")
        elif final.valid and final.value != trusted.value:
            observed.add("final_answer_conflict")
        if normalized_mode == "A" and complete_choice and _has_missing_conditions(plain_result):
            observed.add("false_missing_conditions")
        if complete_choice and _has_option_missing_claim(plain_result):
            observed.add("claims_options_missing")
        if not _schema_complete(normalized_mode, plain_result):
            observed.add("mode_schema_incomplete")
        issues = tuple(issue for issue in self._ISSUE_ORDER if issue in observed)
        return ContentValidation(not issues, issues)
