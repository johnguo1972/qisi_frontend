"""Question classification, knowledge analysis, and vision fact components."""

from __future__ import annotations

from apps.common.ai.schemas import (
    KnowledgeAnalysisResponse,
    QuestionProbeResponse,
    VisionFactResponse,
)

from .base import QuestionAIComponent, QuestionInput


_BOUNDARY_FORMAT_CHARACTERS = frozenset(
    {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
)


def _normalize_scalar_token(value: object) -> object:
    """Trim visual boundary padding without changing token internals."""
    if not isinstance(value, str):
        return value

    start = 0
    end = len(value)
    while start < end and (
        value[start].isspace() or value[start] in _BOUNDARY_FORMAT_CHARACTERS
    ):
        start += 1
    while end > start and (
        value[end - 1].isspace()
        or value[end - 1] in _BOUNDARY_FORMAT_CHARACTERS
    ):
        end -= 1
    return value[start:end]


def _is_nonempty(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and value != "" and value != [] and value != {}


def _normalize_alias_pair(
    result: dict, canonical: str, legacy: str, default: object
) -> None:
    canonical_value = result.get(canonical)
    legacy_value = result.get(legacy)
    if _is_nonempty(canonical_value):
        selected = canonical_value
    elif _is_nonempty(legacy_value):
        selected = legacy_value
    else:
        selected = default
    result[canonical] = selected
    result[legacy] = selected


def _normalize_scalar_alias_pair(
    result: dict, canonical: str, legacy: str, default: object
) -> None:
    canonical_value = _normalize_scalar_token(result.get(canonical))
    legacy_value = _normalize_scalar_token(result.get(legacy))
    if _is_nonempty(canonical_value):
        selected = canonical_value
    elif _is_nonempty(legacy_value):
        selected = legacy_value
    else:
        selected = default
    result[canonical] = selected
    result[legacy] = selected


class QuestionProbeComponent(QuestionAIComponent):
    task_key = "question_probe"
    response_schema = QuestionProbeResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "ocr_text": question.stem,
            "has_figure": bool(question.image_urls),
            "ocr_confidence": question.metadata.get("ocr_confidence", "unknown"),
        }

    def normalize(self, result: dict) -> dict:
        normalized = dict(result)
        normalized.setdefault("subject", "")
        normalized.setdefault("grade", "")
        normalized.setdefault("semester", "")
        normalized.setdefault("chapter", "")
        _normalize_scalar_alias_pair(
            normalized, "question_type", "question_style", ""
        )
        _normalize_scalar_alias_pair(
            normalized, "difficulty", "difficulty_est", ""
        )
        _normalize_alias_pair(
            normalized, "knowledge_points", "topic_tags_top3", []
        )
        return normalized


class KnowledgeAnalysisComponent(QuestionAIComponent):
    task_key = "knowledge_analysis"
    response_schema = KnowledgeAnalysisResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            ),
            "subject_hint": question.metadata.get("subject_hint", ""),
        }


class VisionExtractionComponent(QuestionAIComponent):
    task_key = "vision_fact_extract"
    response_schema = VisionFactResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            )
        }
