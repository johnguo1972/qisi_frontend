"""Pydantic schemas for provider response envelopes."""

from __future__ import annotations

import unicodedata
import re
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from apps.common.ai.redaction import safe_preview


def _is_visual_blank_character(character: str) -> bool:
    return character.isspace() or unicodedata.category(character) == "Cf"


def has_visible_text(value: str) -> bool:
    """Return whether text contains content beyond whitespace/format controls."""
    return any(not _is_visual_blank_character(character) for character in value)


def strip_visual_boundaries(value: str) -> str:
    """Strip whitespace and format controls from both text boundaries."""
    start = 0
    end = len(value)
    while start < end and _is_visual_blank_character(value[start]):
        start += 1
    while end > start and _is_visual_blank_character(value[end - 1]):
        end -= 1
    return value[start:end]


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


_COURSE_IMAGE_SECURITY_MAX_INPUT_LENGTH = 4096
_COURSE_IMAGE_SECURITY_MAX_TRANSFORMS = 16
_SENSITIVE_MARKER_VALUE_PATTERN = re.compile(
    r"(?<![a-z0-9])"
    r"(?:access[\s_.-]*key|api[\s_.-]*key|bearer|credential|"
    r"password|secret|signature|token)"
    r"[\s_\-:=./\\]+"
    r"(?=[^\s_\-:=./\\])",
    re.IGNORECASE,
)


def _course_image_security_copy(value: str) -> str:
    def contains_format_control(text: str) -> bool:
        return any(
            unicodedata.category(character) == "Cf" for character in text
        )

    current = value
    for transform_count in range(
        _COURSE_IMAGE_SECURITY_MAX_TRANSFORMS + 1
    ):
        if (
            len(current) > _COURSE_IMAGE_SECURITY_MAX_INPUT_LENGTH
            or contains_format_control(current)
        ):
            raise ValueError("course image text is unsafe")
        candidate = unicodedata.normalize("NFKC", unquote(current))
        if (
            len(candidate) > _COURSE_IMAGE_SECURITY_MAX_INPUT_LENGTH
            or contains_format_control(candidate)
        ):
            raise ValueError("course image text is unsafe")
        if candidate == current:
            return current
        if transform_count == _COURSE_IMAGE_SECURITY_MAX_TRANSFORMS:
            raise ValueError("course image text is unsafe")
        current = candidate
    raise ValueError("course image text is unsafe")


def _contains_sensitive_course_image_text(value: str) -> bool:
    lowered = value.casefold()
    comparison = re.sub(r"\s+", " ", value).strip()
    redacted = safe_preview(value, limit=max(160, len(value) + 1))
    return redacted != comparison or bool(
        re.search(r"(^|[^a-z])(?:data|file)\s*:", lowered)
        or re.search(r"(^|[^a-z0-9])base64([^a-z0-9]|$)", lowered)
        or re.search(
            r"(^|[^a-z0-9])(?:provider[\s_-]*)?raw"
            r"(?:[\s_-]*(?:response|output|bytes|data))?"
            r"([^a-z0-9]|$)",
            lowered,
        )
        or re.search(r"(^|[\s('\"=])(?:[a-z]:[\\/]|[/\\]{1,2}\w)", lowered)
        or re.search(r"(^|[/\\])\.\.([/\\]|$)", lowered)
    )


def _contains_sensitive_marker_value(value: str) -> bool:
    return _SENSITIVE_MARKER_VALUE_PATTERN.search(value) is not None


def _validate_course_image_description(value: str) -> str:
    security_copy = _course_image_security_copy(value)
    if (
        _contains_sensitive_course_image_text(security_copy)
        or _contains_sensitive_marker_value(security_copy)
    ):
        raise ValueError("course image description is unsafe")
    return value


def _validate_course_image_url(value: str) -> str:
    normalized = strip_visual_boundaries(value)
    if not normalized or normalized != value or len(normalized) > 2048:
        raise ValueError("course image URL is unsafe")
    security_copy = _course_image_security_copy(value)
    if any(
        character.isspace() or ord(character) < 32
        for character in security_copy
    ):
        raise ValueError("course image URL is unsafe")

    decoded = security_copy.casefold()
    if (
        re.match(r"^[a-z]:[\\/]", decoded)
        or decoded.startswith(("/", "\\"))
    ):
        raise ValueError("course image URL is unsafe")

    parsed = urlsplit(security_copy)
    if parsed.scheme:
        if parsed.scheme.casefold() not in {"http", "https"}:
            raise ValueError("course image URL is unsafe")
        if not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("course image URL is unsafe")
    elif parsed.netloc:
        raise ValueError("course image URL is unsafe")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("course image URL is unsafe") from exc
    hostname = parsed.netloc
    if hostname.startswith("["):
        hostname = hostname[1 : hostname.find("]")]
    elif port is not None:
        hostname = hostname.rsplit(":", 1)[0]
    if (
        _contains_sensitive_course_image_text(hostname)
        or _contains_sensitive_marker_value(hostname)
    ):
        raise ValueError("course image URL is unsafe")
    path_segments = parsed.path.replace("\\", "/").split("/")
    if (
        ".." in path_segments
        or _contains_sensitive_marker_value(parsed.path)
        or any(
            _contains_sensitive_course_image_text(segment)
            for segment in path_segments
            if segment
        )
    ):
        raise ValueError("course image URL is unsafe")

    if any(
        _contains_sensitive_course_image_text(key)
        or _contains_sensitive_course_image_text(query_value)
        or _contains_sensitive_marker_value(f"{key}={query_value}")
        for key, query_value in parse_qsl(
            parsed.query, keep_blank_values=True
        )
    ):
        raise ValueError("course image URL is unsafe")
    if (
        _contains_sensitive_course_image_text(parsed.fragment)
        or _contains_sensitive_marker_value(parsed.fragment)
    ):
        raise ValueError("course image URL is unsafe")
    return value


class CourseMaterialRecognitionImage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    description: NonBlankStr
    url: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @field_validator("url")
    @classmethod
    def require_safe_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_course_image_url(value)

    @field_validator("description")
    @classmethod
    def require_safe_description(cls, value: str) -> str:
        return _validate_course_image_description(value)


class CourseMaterialRecognitionSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_type: Literal[
        "single_choice", "multiple_choice", "fill_blank", "solution"
    ]
    stem: NonBlankStr
    options: dict[NonBlankStr, NonBlankStr]
    answer: str
    analysis: str
    difficulty: int = Field(ge=1, le=5)
    knowledge_points: list[NonBlankStr]
    images: list[CourseMaterialRecognitionImage]


class CourseMaterialRecognitionError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: Literal["未识别到试题"]


class CourseMaterialRecognitionResponse(
    RootModel[
        CourseMaterialRecognitionSuccess | CourseMaterialRecognitionError
    ]
):
    pass
