"""Isolated DeepSeek stages for answer verification and final arbitration."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from pydantic import BaseModel

from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.question_context import question_context_payload
from apps.common.ai.schemas import (
    FinalReviewResponse,
    IndependentVerificationResponse,
    ModeAResponse,
    ModeBResponse,
    ModeCResponse,
    has_visible_text,
)

from .base import QuestionAIComponent, QuestionInput


_DROP = object()
_ISOLATED_KEYS = frozenset({"qwen_result", "independent_result", "conflicts"})
_PROVIDER_KEYS = frozenset({"provider", "model", "provider_name", "model_name"})
_PROVIDER_NAMES = ("qwen", "deepseek")
_MODE_SCHEMAS = {"A": ModeAResponse, "B": ModeBResponse, "C": ModeCResponse}


def _plain_json(value: object, *, redact_provider_names: bool = False) -> object:
    """Keep only JSON values, including Pydantic output, without object reprs."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if not redact_provider_names:
            return value
        result = value
        for provider_name in _PROVIDER_NAMES:
            result = re.sub(
                re.escape(provider_name),
                "candidate source",
                result,
                flags=re.IGNORECASE,
            )
        return result
    if isinstance(value, BaseModel):
        return _plain_json(
            value.model_dump(), redact_provider_names=redact_provider_names
        )
    if isinstance(value, Mapping):
        plain: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            normalized_key = key.casefold()
            if normalized_key in _ISOLATED_KEYS:
                continue
            if redact_provider_names and normalized_key in _PROVIDER_KEYS:
                continue
            normalized = _plain_json(
                item, redact_provider_names=redact_provider_names
            )
            if normalized is not _DROP:
                plain[key] = normalized
        return plain
    if isinstance(value, (list, tuple)):
        return [
            normalized
            for item in value
            if (
                normalized := _plain_json(
                    item, redact_provider_names=redact_provider_names
                )
            )
            is not _DROP
        ]
    if isinstance(value, (set, frozenset)):
        items = _plain_json(
            list(value), redact_provider_names=redact_provider_names
        )
        return sorted(
            items,
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
    return _DROP


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _safe_question_input(question: QuestionInput) -> QuestionInput:
    """Copy only JSON-safe question values before canonical context rendering."""
    metadata = _plain_json(question.metadata)
    options = _plain_json(question.options)
    image_urls = _plain_json(question.image_urls)
    return QuestionInput(
        stem=_safe_text(question.stem),
        options=None if options is _DROP else options,
        answer=_safe_text(question.answer),
        solution=_safe_text(question.solution),
        image_urls=tuple(
            value for value in image_urls if isinstance(value, str)
        )
        if isinstance(image_urls, list)
        else (),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _target_mode(question: QuestionInput) -> str:
    target_mode = question.metadata.get("target_mode", "")
    mode = target_mode.strip().upper() if isinstance(target_mode, str) else ""
    if mode not in _MODE_SCHEMAS:
        raise ValueError("target_mode must be one of A, B, or C")
    return mode


def _mode_schema_json(target_mode: str) -> str:
    return _json_text(_MODE_SCHEMAS[target_mode].model_json_schema())


def _clean_question_context(question: QuestionInput) -> dict[str, object]:
    payload = question_context_payload(_safe_question_input(question))
    cleaned = _plain_json(payload)
    if not isinstance(cleaned, dict):  # pragma: no cover - fixed payload contract
        raise AIResponseError("Question context must be a JSON object")
    return cleaned


def _has_reference_answer(question: QuestionInput) -> bool:
    return isinstance(question.answer, str) and has_visible_text(question.answer)


def _has_reference_analysis(question: QuestionInput) -> bool:
    analysis = question.metadata.get("reference_analysis", "")
    return any(
        isinstance(value, str) and has_visible_text(value)
        for value in (analysis, question.solution)
    )


class DeepSeekIndependentVerifierComponent(QuestionAIComponent):
    """Solve independently, without any candidate or conflict information."""

    task_key = "deepseek_independent_verify"
    response_schema = IndependentVerificationResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        target_mode = _target_mode(question)
        return {
            "question_context_json": _json_text(_clean_question_context(question)),
            "target_mode": target_mode,
            "mode_schema_json": _mode_schema_json(target_mode),
        }

    def run(self, question: QuestionInput) -> dict:
        safe_question = _safe_question_input(question)
        result = super().run(safe_question)
        answer_available = _has_reference_answer(safe_question)
        analysis_available = _has_reference_analysis(safe_question)
        if ("reference_answer_valid" in result) != answer_available:
            raise AIResponseError(
                "Independent verification reference-answer flag mismatches context"
            )
        if ("reference_analysis_valid" in result) != analysis_available:
            raise AIResponseError(
                "Independent verification reference-analysis flag mismatches context"
            )
        return result


class DeepSeekFinalReviewComponent(QuestionAIComponent):
    """Resolve escalated conflicts using anonymous, JSON-safe candidate evidence."""

    task_key = "deepseek_final_review"
    response_schema = FinalReviewResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        target_mode = _target_mode(question)
        qwen_candidate = _plain_json(
            question.metadata.get("qwen_result", {}), redact_provider_names=True
        )
        independent_candidate = _plain_json(
            question.metadata.get("independent_result", {}), redact_provider_names=True
        )
        conflicts = _plain_json(question.metadata.get("conflicts", []))
        return {
            "question_context_json": _json_text(_clean_question_context(question)),
            "target_mode": target_mode,
            "qwen_result_json": _json_text(
                {
                    "candidate": "candidate A",
                    "content": (
                        qwen_candidate if qwen_candidate is not _DROP else {}
                    ),
                }
            ),
            "independent_result_json": _json_text(
                {
                    "candidate": "candidate B",
                    "content": independent_candidate
                    if independent_candidate is not _DROP
                    else {},
                }
            ),
            "conflicts_json": _json_text(conflicts if conflicts is not _DROP else []),
            "mode_schema_json": _mode_schema_json(target_mode),
        }
