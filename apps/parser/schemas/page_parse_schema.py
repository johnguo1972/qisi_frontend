"""Pydantic schemas for AI parsing output validation."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class OptionBBox(BaseModel):
    label: str
    content: str
    bbox: Optional[list] = None


class QuestionImage(BaseModel):
    bbox: Optional[list] = None
    image_type: str = "other"
    description: str = ""


class ParsedQuestion(BaseModel):
    question_no: str
    section_title: str = ""
    question_type: str
    stem: str
    options: list[OptionBBox] = []
    answer: str = ""
    analysis: str = ""
    solution: str = ""
    comment: str = ""
    knowledge_points: list[str] = []
    difficulty: int = Field(default=3, ge=1, le=5)
    bbox: Optional[list] = None
    region_json: Optional[dict] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    images: list[QuestionImage] = []
    page_end: int = 1
    need_review_reason: str = ""
    raw_explanation: str = ""

    @field_validator('question_type')
    @classmethod
    def validate_question_type(cls, v):
        valid = {
            'single_choice', 'multiple_choice', 'fill_blank',
            'short_answer', 'essay', 'true_false', 'computation',
            'proof', 'unknown'
        }
        if v not in valid:
            return 'unknown'
        return v


class PageParseResult(BaseModel):
    page_no: int
    questions: list[ParsedQuestion]


def validate_parse_result(data: dict) -> PageParseResult:
    """Validate and return parsed result."""
    return PageParseResult(**data)


# --- Stage 1: Position detection schema (lightweight, no stem/type) ---

class QuestionPosition(BaseModel):
    question_no: str
    section_title: str = ""
    page_start: int = 1
    page_end: int = 1
    bbox: Optional[list] = None
    is_cross_page: bool = False


class PagePositionResult(BaseModel):
    page_no: int
    questions: list[QuestionPosition]


def validate_position_result(data: dict) -> PagePositionResult:
    """Validate Stage 1 position detection result."""
    return PagePositionResult(**data)
