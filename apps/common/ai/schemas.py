"""Pydantic schemas for provider response envelopes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    question_type: str = Field(min_length=1)
    grade: str
    semester: str
    chapter: str
    difficulty: Literal["L1", "L2", "L3", "L4", "L5"]
    knowledge_points: list[str]
    multi_part: bool
    proof_or_calc: Literal["proof", "calc"]
    visual_risk_score: int = Field(ge=0, le=100)
    reasoning_risk_score: int = Field(ge=0, le=100)
    recommended_route: Literal["VISION_LIGHT", "STANDARD", "DEEP"]
    brief_reason: str
    normalized_text: str


class KnowledgePointResponse(_StrictResponseModel):
    module: str = Field(min_length=1)
    reason: str | None = None


class KnowledgeAnalysisResponse(_StrictResponseModel):
    subject: Literal["math", "physics"] | None = None
    difficulty: Literal["L1", "L2", "L3", "L4", "L5"] | None = None
    knowledge_points: list[KnowledgePointResponse] = Field(
        min_length=1, max_length=5
    )
    grade_term: dict[str, Any] | None = None
    solving_methods: list[str] | None = None

    @model_validator(mode="after")
    def require_canonical_or_legacy_contract(self):
        canonical = self.subject is not None and self.difficulty is not None
        legacy = self.grade_term is not None and self.solving_methods is not None
        if not (canonical or legacy):
            raise ValueError("knowledge response contract is incomplete")
        if canonical and any(not point.reason for point in self.knowledge_points):
            raise ValueError("canonical knowledge point reason is required")
        return self


class VisionFactResponse(_StrictResponseModel):
    subject: Literal["math", "physics"]
    figure_present: bool
    figure_type: str
    visual_summary: str
    diagram_facts: list[str]
    text_marks_in_figure: list[Any]
    variables_and_symbols: list[Any] | dict[str, Any]
    target_related_visual_info: list[Any] | dict[str, Any] | str
    unclear_parts: list[Any]
    ocr_conflicts: list[Any]
    confidence: Literal["high", "medium", "low"]


class ModeAResponse(_StrictResponseModel):
    mode: Literal["A"]
    steps: list[Any] = Field(min_length=1)
    final_answer: str
    summary: str


class ModeBQuestionResponse(_StrictResponseModel):
    question: str = Field(min_length=1)
    options: dict[str, Any] = Field(min_length=1)
    correct_answer: str = Field(min_length=1)
    explanation: str


class ModeBResponse(_StrictResponseModel):
    mode: Literal["B"]
    questions: list[ModeBQuestionResponse] = Field(min_length=1)


class ModeCQuestionResponse(_StrictResponseModel):
    question: str = Field(min_length=1)
    reference_answer: str
    key_points: list[str] = Field(min_length=1)
    followup_hint: str


class ModeCResponse(_StrictResponseModel):
    mode: Literal["C"]
    questions: list[ModeCQuestionResponse] = Field(min_length=1)
    final_answer: str
    summary: str


class ResultVerifierResponse(_StrictResponseModel):
    passed: bool = Field(alias="pass")
    consistency: Any
    fact_violation: Any
    calc_suspect: Any
    issues: list[Any]
    retry_needed: bool
    retry_reason: str
