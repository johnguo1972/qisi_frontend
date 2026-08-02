"""Pydantic schemas for provider response envelopes."""

from __future__ import annotations

import unicodedata
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def has_visible_text(value: str) -> bool:
    """Return whether text contains content beyond whitespace/format controls."""
    return any(
        not (character.isspace() or unicodedata.category(character) == "Cf")
        for character in value
    )


def _require_non_blank(value: str) -> str:
    if not has_visible_text(value):
        raise ValueError("value must not be blank")
    return value


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: str


class AIChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: AIMessage


class AIResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    choices: list[AIChoice] = Field(min_length=1)


class _StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, populate_by_name=True)


class QuestionProbeResponse(_StrictResponseModel):
    subject: Literal["math", "physics"]
    question_type: NonBlankStr
    grade: str
    semester: str
    chapter: str
    difficulty: Literal["L1", "L2", "L3", "L4", "L5"]
    knowledge_points: list[NonBlankStr] = Field(min_length=1, max_length=5)
    multi_part: bool
    proof_or_calc: Literal["proof", "calc"]
    visual_risk_score: int = Field(ge=0, le=100)
    reasoning_risk_score: int = Field(ge=0, le=100)
    recommended_route: Literal["VISION_LIGHT", "STANDARD", "DEEP"]
    brief_reason: str
    normalized_text: NonBlankStr


class KnowledgePointResponse(_StrictResponseModel):
    module: NonBlankStr
    reason: NonBlankStr | None = None


class KnowledgeAnalysisResponse(_StrictResponseModel):
    subject: Literal["math", "physics"] | None = None
    difficulty: Literal["L1", "L2", "L3", "L4", "L5"] | None = None
    knowledge_points: list[KnowledgePointResponse] = Field(
        min_length=1, max_length=5
    )
    grade_term: dict[str, Any] | None = None
    solving_methods: list[NonBlankStr] | None = None

    @model_validator(mode="after")
    def require_canonical_or_legacy_contract(self):
        canonical = self.subject is not None and self.difficulty is not None
        legacy = self.grade_term is not None and self.solving_methods is not None
        if not (canonical or legacy):
            raise ValueError("knowledge response contract is incomplete")
        if canonical and any(point.reason is None for point in self.knowledge_points):
            raise ValueError("canonical knowledge point reason is required")
        return self


class VisionFactResponse(_StrictResponseModel):
    subject: Literal["math", "physics"]
    figure_present: bool
    figure_type: str
    visual_summary: str
    diagram_facts: list[NonBlankStr]
    text_marks_in_figure: list[Any]
    variables_and_symbols: list[Any] | dict[str, Any]
    target_related_visual_info: list[Any] | dict[str, Any] | str
    unclear_parts: list[Any]
    ocr_conflicts: list[Any]
    confidence: Literal["high", "medium", "low"]


class ModeAStepResponse(_StrictResponseModel):
    step: int
    content: NonBlankStr


class ModeAResponse(_StrictResponseModel):
    mode: Literal["A"]
    steps: list[ModeAStepResponse] = Field(min_length=3, max_length=4)
    final_answer: NonBlankStr
    summary: NonBlankStr


class ModeBOptionsResponse(_StrictResponseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    A: NonBlankStr
    B: NonBlankStr
    C: NonBlankStr
    D: NonBlankStr


class ModeBQuestionResponse(_StrictResponseModel):
    question: NonBlankStr
    options: ModeBOptionsResponse
    correct_option: Literal["A", "B", "C", "D"]
    reference_answer: NonBlankStr
    analysis: NonBlankStr
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: NonBlankStr


class ModeBResponse(_StrictResponseModel):
    mode: Literal["B"]
    questions: list[ModeBQuestionResponse] = Field(min_length=3, max_length=4)
    final_answer: NonBlankStr
    summary: NonBlankStr


class ModeCQuestionResponse(_StrictResponseModel):
    question: NonBlankStr
    reference_answer: NonBlankStr
    key_points: list[NonBlankStr] = Field(min_length=1)
    followup_hint: NonBlankStr


class ModeCResponse(_StrictResponseModel):
    mode: Literal["C"]
    questions: list[ModeCQuestionResponse] = Field(min_length=3, max_length=5)
    final_answer: NonBlankStr
    summary: NonBlankStr


class ResultVerifierResponse(_StrictResponseModel):
    passed: bool = Field(alias="pass")
    consistency: NonBlankStr
    fact_violation: bool
    calc_suspect: bool
    issues: list[NonBlankStr]
    retry_needed: bool
    retry_reason: str

    @model_validator(mode="after")
    def require_retry_reason_when_retry_is_needed(self):
        if self.retry_needed and not self.retry_reason.strip():
            raise ValueError("retry reason is required when retry is needed")
        return self
