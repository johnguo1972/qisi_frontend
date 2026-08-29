"""Question classification, knowledge analysis, and vision fact components."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.schemas import (
    KnowledgeAnalysisResponse,
    QuestionProbeResponse,
    TaxonomyKnowledgeResponse,
    TaxonomyScopeResponse,
    TaxonomySubtopicResponse,
    VisionFactResponse,
)

from .base import QuestionAIComponent, QuestionInput, to_plain_data


_BOUNDARY_FORMAT_CHARACTERS = frozenset(
    {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
)
_LITERAL_ESCAPED_WHITESPACE = frozenset({r"\t", r"\n", r"\f", r"\r"})


def _leading_boundary_width(value: str, start: int, end: int) -> int:
    """Return one complete leading boundary unit, preserving token internals."""
    if start + 1 < end and value[start] == "\\" and value[start + 1].isspace():
        return 2
    if value[start : start + 2] in _LITERAL_ESCAPED_WHITESPACE:
        return 2
    if value[start].isspace() or value[start] in _BOUNDARY_FORMAT_CHARACTERS:
        return 1
    return 0


def _trailing_boundary_width(value: str, start: int, end: int) -> int:
    """Return one complete trailing boundary unit, preserving token internals."""
    if end - 2 >= start and value[end - 2] == "\\" and value[end - 1].isspace():
        return 2
    if value[max(start, end - 2) : end] in _LITERAL_ESCAPED_WHITESPACE:
        return 2
    if value[end - 1].isspace() or value[end - 1] in _BOUNDARY_FORMAT_CHARACTERS:
        return 1
    return 0


def _normalize_scalar_token(value: object) -> object:
    """Trim taxonomy-token padding without changing token internals."""
    if not isinstance(value, str):
        return value

    start = 0
    end = len(value)
    while start < end:
        leading_width = _leading_boundary_width(value, start, end)
        if leading_width:
            start += leading_width
            continue
        trailing_width = _trailing_boundary_width(value, start, end)
        if trailing_width:
            end -= trailing_width
            continue
        break
    return value[start:end]


def _scalar_value_is_missing(value: object) -> bool:
    """Only absent or normalized-empty strings may use a legacy fallback."""
    return value is None or (isinstance(value, str) and value == "")


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
    if not _scalar_value_is_missing(canonical_value):
        selected = canonical_value
    elif not _scalar_value_is_missing(legacy_value):
        selected = legacy_value
    else:
        selected = default
    result[canonical] = selected
    result[legacy] = selected


def _enum_token(value: object) -> str:
    return str(_normalize_scalar_token(value) or "").lower()


def _normalize_probe_knowledge_points(value: object) -> list[str]:
    if isinstance(value, str):
        values = re.split(r"[,，;；、\n]+", value)
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return []

    normalized: list[str] = []
    for item in values:
        if isinstance(item, dict):
            item = next(
                (
                    item.get(key)
                    for key in ("module", "name", "knowledge_point", "title")
                    if _is_nonempty(item.get(key))
                ),
                "",
            )
        token = str(_normalize_scalar_token(item) or "")
        normalized.append(token)
    return normalized


def _normalize_probe_bool(value: object) -> object:
    if isinstance(value, bool):
        return value
    token = _enum_token(value)
    if token in {"true", "1", "yes", "y", "是", "多问", "多小题"}:
        return True
    if token in {"false", "0", "no", "n", "否", "单题"}:
        return False
    return value


def _normalize_probe_score(value: object) -> object:
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


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
        subject = _enum_token(normalized.get("subject"))
        normalized["subject"] = {
            "数学": "math",
            "數學": "math",
            "物理": "physics",
        }.get(subject, subject)
        normalized.setdefault("subject", "")
        # Grade, term, and chapter are owned by the local knowledge tree.
        # Drop provider-supplied values so only a matched local point can
        # populate them during persistence.
        normalized.pop("grade", None)
        normalized.pop("semester", None)
        normalized.pop("chapter", None)
        _normalize_scalar_alias_pair(
            normalized, "question_type", "question_style", ""
        )
        _normalize_scalar_alias_pair(
            normalized, "difficulty", "difficulty_est", ""
        )
        _normalize_alias_pair(
            normalized, "knowledge_points", "topic_tags_top3", []
        )
        normalized["knowledge_points"] = _normalize_probe_knowledge_points(
            normalized["knowledge_points"]
        )
        normalized["topic_tags_top3"] = normalized["knowledge_points"]

        difficulty = normalized.get("difficulty")
        if (
            not isinstance(difficulty, bool)
            and isinstance(difficulty, (int, float))
            and int(difficulty) == difficulty
        ):
            difficulty = f"L{int(difficulty)}"
        elif isinstance(difficulty, str):
            token = difficulty.strip().upper()
            difficulty = f"L{token}" if token.isdigit() else token
        normalized["difficulty"] = difficulty
        normalized["difficulty_est"] = difficulty

        normalized["multi_part"] = _normalize_probe_bool(
            normalized.get("multi_part")
        )
        proof_or_calc = _enum_token(normalized.get("proof_or_calc"))
        normalized["proof_or_calc"] = {
            "计算": "calc",
            "計算": "calc",
            "calculation": "calc",
            "证明": "proof",
            "證明": "proof",
        }.get(proof_or_calc, proof_or_calc)
        normalized["visual_risk_score"] = _normalize_probe_score(
            normalized.get("visual_risk_score")
        )
        normalized["reasoning_risk_score"] = _normalize_probe_score(
            normalized.get("reasoning_risk_score")
        )
        normalized["recommended_route"] = str(
            normalized.get("recommended_route") or ""
        ).strip().upper()
        return normalized

    def response_correction_messages(
        self,
        _question: QuestionInput,
        *,
        system: str,
        user: str,
        error,
    ) -> tuple[str, str]:
        correction = (
            "\n\nSTRICT_SCHEMA_CORRECTION: 上一次响应无法通过结构校验。"
            "请只返回一个 JSON 对象；不得使用 Markdown。subject 只能是 math/physics；"
            "difficulty 只能是 L1-L5；knowledge_points 必须是 1-5 个非空字符串；"
            "multi_part 必须是布尔值；proof_or_calc 只能是 proof/calc；"
            "两个 risk_score 必须是 0-100 的整数；recommended_route 只能是 "
            "VISION_LIGHT/STANDARD/DEEP；normalized_text 必须为非空字符串。"
        )
        return system, user + correction


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


class TaxonomyScopeComponent(QuestionAIComponent):
    """Select an enabled first-level topic from the supplied catalog only."""

    task_key = "controlled_taxonomy_scope"
    response_schema = TaxonomyScopeResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "ocr_text": question.stem,
            "has_figure": bool(question.image_urls),
            "topic_candidates_json": json.dumps(
                to_plain_data(question.metadata.get("topic_candidates", [])),
                ensure_ascii=False,
            ),
        }


class TaxonomySubtopicComponent(QuestionAIComponent):
    """Select an enabled child topic when the selected root has children."""

    task_key = "controlled_taxonomy_subtopic"
    response_schema = TaxonomySubtopicResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get("normalized_text", question.stem),
            "scope_json": json.dumps(
                to_plain_data(question.metadata.get("scope", {})), ensure_ascii=False
            ),
            "subtopic_candidates_json": json.dumps(
                to_plain_data(question.metadata.get("subtopic_candidates", [])),
                ensure_ascii=False,
            ),
        }

    def validate_result(self, result: dict, question: QuestionInput) -> dict:
        candidates = question.metadata.get("subtopic_candidates", []) or []
        candidate_ids = {
            str(candidate.get("id"))
            for candidate in candidates
            if isinstance(candidate, Mapping) and candidate.get("id")
        }
        selected_id = result.get("subtopic_id")
        if candidate_ids and str(selected_id or "") not in candidate_ids:
            raise AIResponseError(
                "controlled taxonomy subtopic must select an available subtopic"
            )
        return result


class TaxonomyKnowledgeComponent(QuestionAIComponent):
    """Select controlled standard point IDs and refine the coarse difficulty."""

    task_key = "controlled_taxonomy_knowledge"
    response_schema = TaxonomyKnowledgeResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get("normalized_text", question.stem),
            "scope_json": json.dumps(
                to_plain_data(question.metadata.get("scope", {})), ensure_ascii=False
            ),
            "knowledge_candidates_json": json.dumps(
                to_plain_data(question.metadata.get("candidates", [])),
                ensure_ascii=False,
            ),
        }

    def validate_result(self, result: dict, question: QuestionInput) -> dict:
        level = str(question.metadata.get("difficulty_level", "")).upper()
        if level not in {"L1", "L2", "L3", "L4", "L5"}:
            raise AIResponseError("controlled taxonomy difficulty level is missing")
        lower = float(level[1])
        upper = lower + 0.9
        score = float(result["difficulty_score"])
        if not lower <= score <= upper:
            raise AIResponseError(
                "controlled taxonomy difficulty score is outside the selected difficulty level"
            )
        return result


class VisionExtractionComponent(QuestionAIComponent):
    task_key = "vision_fact_extract"
    response_schema = VisionFactResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            )
        }
