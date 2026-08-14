"""Pure, explicit A/B/C answer arbitration with fail-closed provider stages.

The one accepted DeepSeek confidence threshold is 0.80, from the approved
mode-answer arbitration specification.  This module never performs I/O; all
provider work is supplied as injected callables.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import re
import unicodedata

from apps.common.exceptions import AIRequestError

from .answer_validation import AnswerNormalizer, ModeContentValidator
from .components.base import QuestionInput
from .question_context import question_context_hash, question_context_payload


class ArbitrationError(RuntimeError):
    """Base class for non-savable arbitration outcomes."""


class ArbitrationProviderError(ArbitrationError):
    """A required provider result was unavailable or did not meet its contract."""

    status = "arbitration_provider_failure"

    def __init__(self) -> None:
        super().__init__(self.status)


class HumanReviewRequired(ArbitrationError):
    """DeepSeek reported genuine missing conditions, so no answer is selected."""

    status = "human_review_required"

    def __init__(self) -> None:
        super().__init__("missing_conditions")


@dataclass(frozen=True)
class ArbitrationOutcome:
    answer: dict
    verification: dict
    shared_verifier_result: dict | None


def _plain_mapping(value: object) -> dict[str, object] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            plain = dump()
        except (TypeError, ValueError):
            return None
        return _plain_mapping(plain)
    return None


def _nonblank_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _copy_mapping(value: Mapping[str, object]) -> dict:
    try:
        copied = deepcopy(dict(value))
    except (TypeError, ValueError):
        raise ArbitrationProviderError() from None
    return copied


def _missing_conditions(value: Mapping[str, object]) -> bool:
    missing = value.get("missing_conditions", ())
    if isinstance(missing, str):
        return bool(missing.strip())
    return isinstance(missing, (list, tuple)) and any(
        _nonblank_text(item) for item in missing
    )


def _canonical_visible_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def _visible_text_values(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _visible_text_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _visible_text_values(item)


class ModeAnswerArbitrator:
    """Select a validated mode answer using the approved decision table only."""

    INDEPENDENT_CONFIDENCE_THRESHOLD = 0.80
    _CACHE_FIELDS = frozenset(
        {
            "context_hash",
            "independent_answer",
            "reference_answer_valid",
            "reference_analysis_valid",
            "reference_issues",
            "key_facts",
            "confidence",
        }
    )

    def __init__(
        self,
        *,
        generate: Callable[[str, QuestionInput], object],
        independent_verify: Callable[[str, QuestionInput], object],
        final_review: Callable[[str, QuestionInput, object, object, object], object],
        normalizer: AnswerNormalizer | None = None,
        content_validator: ModeContentValidator | None = None,
    ) -> None:
        self._generate = generate
        self._independent_verify = independent_verify
        self._final_review = final_review
        self._normalizer = normalizer or AnswerNormalizer()
        self._content_validator = content_validator or ModeContentValidator(self._normalizer)

    @staticmethod
    def context_hash(context: QuestionInput) -> str:
        return question_context_hash(context)

    def process(
        self,
        mode: str,
        context: QuestionInput,
        *,
        cached_verification: object = None,
    ) -> ArbitrationOutcome:
        normalized_mode = self._mode(mode)
        if not isinstance(context, QuestionInput):
            raise ArbitrationProviderError()
        context_hash = question_context_hash(context)
        payload = question_context_payload(context)
        question_type = payload.get("question_type", "")
        option_labels = tuple(
            item.get("label", "")
            for item in payload.get("options", ())
            if isinstance(item, Mapping)
        )

        qwen = self._call_generate(normalized_mode, context)
        normalized_reference = self._normalizer.normalize(
            context.answer, question_type=question_type, option_labels=option_labels
        )
        normalized_qwen = self._normalizer.normalize(
            qwen.get("final_answer"),
            question_type=question_type,
            option_labels=option_labels,
        )
        qwen_content = self._content_validator.validate(
            normalized_mode,
            qwen,
            trusted_answer=normalized_qwen.value,
            context=payload,
        )

        # Decision row 1: a valid reference and valid matching Qwen payload end here.
        if (
            normalized_reference.valid
            and normalized_qwen.valid
            and normalized_reference.value == normalized_qwen.value
            and qwen_content.valid
        ):
            return self._accepted(
                selected=qwen,
                provider="qwen",
                context_hash=context_hash,
                normalized_reference=normalized_reference.value,
                normalized_qwen=normalized_qwen.value,
                normalized_deepseek="",
                trusted_answer=normalized_qwen.value,
                deepseek_used=False,
                final_review_used=False,
                confidence=1.0,
                warnings=(),
                shared=None,
            )

        independent, used_cached = self._independent(
            normalized_mode, context, context_hash, cached_verification
        )
        normalized_deepseek = self._normalizer.normalize(
            independent["independent_answer"],
            question_type=question_type,
            option_labels=option_labels,
        )
        if normalized_deepseek.reason == "missing_conditions" or _missing_conditions(independent):
            raise HumanReviewRequired()
        if not normalized_deepseek.valid:
            raise ArbitrationProviderError()

        shared = self._shared(independent, context_hash)
        independent_content = self._content_validator.validate(
            normalized_mode,
            independent.get("mode_content", {}),
            trusted_answer=normalized_deepseek.value,
            context=payload,
        )
        warnings: list[str] = []
        if not qwen_content.valid:
            warnings.append("qwen_content_invalid")
        if normalized_reference.valid and normalized_qwen.valid and normalized_qwen.value != normalized_reference.value:
            warnings.append("reference_answer_conflict")
        if not independent_content.valid:
            warnings.append("independent_content_invalid")
        if used_cached:
            warnings.append("independent_verification_cached")
        qwen_facts_cover = self._qwen_facts_cover(qwen, independent)
        if (
            normalized_qwen.valid
            and normalized_deepseek.value == normalized_qwen.value
            and not qwen_facts_cover
        ):
            warnings.append("qwen_key_facts_unproven")

        # Required escalation conditions take precedence over answer equality.
        if independent["confidence"] < self.INDEPENDENT_CONFIDENCE_THRESHOLD:
            warnings.append("low_independent_confidence")
            return self._review(
                normalized_mode, context, qwen, independent, warnings, context_hash,
                normalized_reference.value, normalized_qwen.value,
                normalized_deepseek.value, shared,
            )
        if normalized_reference.valid and independent["reference_analysis_valid"] is False:
            warnings.append("reference_analysis_invalid")
            return self._review(
                normalized_mode, context, qwen, independent, warnings, context_hash,
                normalized_reference.value, normalized_qwen.value,
                normalized_deepseek.value, shared,
            )
        if (
            normalized_reference.valid
            and independent["reference_answer_valid"] is not True
        ):
            warnings.append("reference_answer_not_verified")
            return self._review(
                normalized_mode, context, qwen, independent, warnings, context_hash,
                normalized_reference.value, normalized_qwen.value,
                normalized_deepseek.value, shared,
            )

        if normalized_reference.valid:
            if normalized_qwen.valid and normalized_qwen.value == normalized_reference.value:
                if (
                    normalized_deepseek.value == normalized_reference.value
                    and independent_content.valid
                ):
                    return self._accepted(
                        selected=independent["mode_content"],
                        provider="deepseek_independent",
                        context_hash=context_hash,
                        normalized_reference=normalized_reference.value,
                        normalized_qwen=normalized_qwen.value,
                        normalized_deepseek=normalized_deepseek.value,
                        trusted_answer=normalized_deepseek.value,
                        deepseek_used=True,
                        final_review_used=False,
                        confidence=independent["confidence"],
                        warnings=warnings,
                        shared=shared,
                    )
                return self._review(
                    normalized_mode, context, qwen, independent, warnings, context_hash,
                    normalized_reference.value, normalized_qwen.value,
                    normalized_deepseek.value, shared,
                )
            if normalized_deepseek.value == normalized_reference.value:
                if independent_content.valid:
                    return self._accepted(
                        selected=independent["mode_content"],
                        provider="deepseek_independent",
                        context_hash=context_hash,
                        normalized_reference=normalized_reference.value,
                        normalized_qwen=normalized_qwen.value,
                        normalized_deepseek=normalized_deepseek.value,
                        trusted_answer=normalized_deepseek.value,
                        deepseek_used=True,
                        final_review_used=False,
                        confidence=independent["confidence"],
                        warnings=warnings,
                        shared=shared,
                    )
                return self._review(
                    normalized_mode, context, qwen, independent, warnings, context_hash,
                    normalized_reference.value, normalized_qwen.value,
                    normalized_deepseek.value, shared,
                )
            if (
                normalized_qwen.valid
                and normalized_deepseek.value == normalized_qwen.value
                and qwen_content.valid
                and qwen_facts_cover
            ):
                return self._accepted(
                    selected=qwen,
                    provider="qwen",
                    context_hash=context_hash,
                    normalized_reference=normalized_reference.value,
                    normalized_qwen=normalized_qwen.value,
                    normalized_deepseek=normalized_deepseek.value,
                    trusted_answer=normalized_qwen.value,
                    deepseek_used=True,
                    final_review_used=False,
                    confidence=independent["confidence"],
                    warnings=warnings,
                    shared=shared,
                )
        elif (
            normalized_qwen.valid
            and normalized_qwen.value == normalized_deepseek.value
            and qwen_content.valid
            and qwen_facts_cover
        ):
            return self._accepted(
                selected=qwen,
                provider="qwen",
                context_hash=context_hash,
                normalized_reference=normalized_reference.value,
                normalized_qwen=normalized_qwen.value,
                normalized_deepseek=normalized_deepseek.value,
                trusted_answer=normalized_qwen.value,
                deepseek_used=True,
                final_review_used=False,
                confidence=independent["confidence"],
                warnings=warnings,
                shared=shared,
            )

        return self._review(
            normalized_mode, context, qwen, independent, warnings, context_hash,
            normalized_reference.value, normalized_qwen.value,
            normalized_deepseek.value, shared,
        )

    @staticmethod
    def _mode(mode: object) -> str:
        normalized = mode.strip().upper() if isinstance(mode, str) else ""
        if normalized not in {"A", "B", "C"}:
            raise ArbitrationProviderError()
        return normalized

    def _call_generate(self, mode: str, context: QuestionInput) -> dict[str, object]:
        try:
            result = self._generate(mode, context)
        except (AIRequestError, TypeError, ValueError):
            raise ArbitrationProviderError() from None
        mapping = _plain_mapping(result)
        if mapping is None:
            raise ArbitrationProviderError()
        return mapping

    def _independent(
        self, mode: str, context: QuestionInput, context_hash: str, cached: object
    ) -> tuple[dict[str, object], bool]:
        cache = _plain_mapping(cached)
        if cache is not None and cache.get("context_hash") == context_hash:
            candidate = self._validated_independent(cache, cached=True)
            if candidate is not None:
                return candidate, True
        try:
            result = self._independent_verify(mode, context)
        except (AIRequestError, TypeError, ValueError):
            raise ArbitrationProviderError() from None
        candidate = self._validated_independent(_plain_mapping(result), cached=False)
        if candidate is None:
            raise ArbitrationProviderError()
        return candidate, False

    def _validated_independent(
        self, result: dict[str, object] | None, *, cached: bool
    ) -> dict[str, object] | None:
        required = set(self._CACHE_FIELDS - {"context_hash"})
        if not cached:
            required.update({"independent_reasoning_summary", "mode_content"})
        if result is None or not required.issubset(result):
            return None
        answer = result.get("independent_answer")
        facts = result.get("key_facts")
        issues = result.get("reference_issues")
        confidence = result.get("confidence")
        flags = (result.get("reference_answer_valid"), result.get("reference_analysis_valid"))
        if (
            not _nonblank_text(answer)
            or not isinstance(facts, (list, tuple))
            or not facts
            or not all(_nonblank_text(item) for item in facts)
            or not isinstance(issues, (list, tuple))
            or not all(isinstance(item, str) for item in issues)
            or any(flag is not None and not isinstance(flag, bool) for flag in flags)
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            return None
        if not cached and not _nonblank_text(result.get("independent_reasoning_summary")):
            return None
        try:
            safe = {
                key: deepcopy(result[key])
                for key in self._CACHE_FIELDS
                if key != "context_hash"
            }
        except (TypeError, ValueError):
            return None
        safe["confidence"] = float(confidence)
        if not cached:
            mode_content = _plain_mapping(result.get("mode_content"))
            if mode_content is None:
                return None
            safe["mode_content"] = _copy_mapping(mode_content)
        return safe

    def _review(
        self,
        mode: str,
        context: QuestionInput,
        qwen: dict[str, object],
        independent: dict[str, object],
        warnings: list[str],
        context_hash: str,
        normalized_reference: str,
        normalized_qwen: str,
        normalized_deepseek: str,
        shared: dict,
    ) -> ArbitrationOutcome:
        conflicts = tuple(warnings) or ("answer_conflict",)
        try:
            raw_final = self._final_review(mode, context, _copy_mapping(qwen), _copy_mapping(independent), conflicts)
        except (AIRequestError, TypeError, ValueError):
            raise ArbitrationProviderError() from None
        final = _plain_mapping(raw_final)
        if final is None or not self._valid_final(final):
            raise ArbitrationProviderError()
        payload = question_context_payload(context)
        option_labels = tuple(
            item.get("label", "")
            for item in payload.get("options", ())
            if isinstance(item, Mapping)
        )
        trusted = self._normalizer.normalize(
            final["trusted_answer"],
            question_type=payload.get("question_type", ""),
            option_labels=option_labels,
        )
        mode_content = _plain_mapping(final["mode_content"])
        if mode_content is None or not trusted.valid:
            raise ArbitrationProviderError()
        validation = self._content_validator.validate(
            mode, mode_content, trusted_answer=trusted.value, context=payload
        )
        if not validation.valid:
            raise ArbitrationProviderError()
        return self._accepted(
            selected=mode_content,
            provider="deepseek_final_review",
            context_hash=context_hash,
            normalized_reference=normalized_reference,
            normalized_qwen=normalized_qwen,
            normalized_deepseek=normalized_deepseek,
            trusted_answer=trusted.value,
            deepseek_used=True,
            final_review_used=True,
            confidence=float(final["confidence"]),
            warnings=tuple(warnings),
            shared=shared,
        )

    @staticmethod
    def _valid_final(result: Mapping[str, object]) -> bool:
        confidence = result.get("confidence")
        return (
            _nonblank_text(result.get("trusted_answer"))
            and isinstance(result.get("qwen_content_valid"), bool)
            and isinstance(result.get("candidate_issues"), (list, tuple))
            and all(_nonblank_text(item) for item in result["candidate_issues"])
            and not isinstance(confidence, bool)
            and isinstance(confidence, (int, float))
            and 0 <= confidence <= 1
            and _plain_mapping(result.get("mode_content")) is not None
        )

    @staticmethod
    def _qwen_facts_cover(
        qwen: Mapping[str, object], independent: Mapping[str, object]
    ) -> bool:
        independent_facts = {
            _canonical_visible_text(fact)
            for fact in independent["key_facts"]
        }
        if not independent_facts or "" in independent_facts:
            return False
        if "key_facts" in qwen:
            qwen_facts = qwen["key_facts"]
            if not isinstance(qwen_facts, (list, tuple)):
                return False
            qwen_fact_values = {
                _canonical_visible_text(fact) for fact in qwen_facts
            }
            return "" not in qwen_fact_values and independent_facts.issubset(
                qwen_fact_values
            )
        visible_values = {
            _canonical_visible_text(item) for item in _visible_text_values(qwen)
        }
        return "" not in visible_values and independent_facts.issubset(visible_values)

    def _shared(self, independent: Mapping[str, object], context_hash: str) -> dict:
        return {
            "context_hash": context_hash,
            "independent_answer": independent["independent_answer"],
            "reference_answer_valid": independent["reference_answer_valid"],
            "reference_analysis_valid": independent["reference_analysis_valid"],
            "reference_issues": deepcopy(independent["reference_issues"]),
            "key_facts": deepcopy(independent["key_facts"]),
            "confidence": independent["confidence"],
        }

    @staticmethod
    def _accepted(
        *,
        selected: Mapping[str, object],
        provider: str,
        context_hash: str,
        normalized_reference: str,
        normalized_qwen: str,
        normalized_deepseek: str,
        trusted_answer: str,
        deepseek_used: bool,
        final_review_used: bool,
        confidence: float,
        warnings: tuple[str, ...] | list[str],
        shared: dict | None,
    ) -> ArbitrationOutcome:
        verification = {
            "status": "accepted",
            "context_hash": context_hash,
            "reference_answer": normalized_reference,
            "qwen_answer": normalized_qwen,
            "deepseek_answer": normalized_deepseek,
            "trusted_answer": trusted_answer,
            "selected_content_provider": provider,
            "deepseek_thinking_enabled": deepseek_used,
            "final_review_used": final_review_used,
            "confidence": confidence,
            "warnings": list(warnings),
        }
        answer = _copy_mapping(selected)
        answer["verification"] = deepcopy(verification)
        return ArbitrationOutcome(answer, verification, deepcopy(shared))
