"""Database-free course variant generation through the shared AI runtime."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.schemas import NonBlankStr

from .base import AICompleter, QuestionInput, to_plain_data


class _VariantOption(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    label: NonBlankStr
    content: NonBlankStr


class _VariantResponse(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    stem: NonBlankStr
    question_type: NonBlankStr
    answer: NonBlankStr
    options: list[_VariantOption] = Field(default_factory=list)
    analysis: str = ""
    solution: str = ""
    difficulty: int = Field(default=3, ge=1, le=5)
    knowledge_points: list[Any] = Field(default_factory=list)
    variant_mode: str = ""
    changes_from_original: str = ""

    @model_validator(mode="after")
    def require_choice_options(self):
        if self.question_type in {
            "single_choice",
            "multiple_choice",
            "单选题",
            "多选题",
        } and len(self.options) < 2:
            raise ValueError("choice variant requires at least two options")
        return self


class VariantGeneratorComponent:
    """Generate one validated variant with the configured Qwen task."""

    task_key = "variant_generate"

    def __init__(
        self,
        ai_client: AICompleter | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._ai_client = ai_client or AIClient()
        self._prompt_registry = prompt_registry or PromptRegistry()

    def generate(self, question: QuestionInput, variant_mode: str) -> dict:
        question_context = {
            "stem": question.stem,
            "question_type": question.metadata.get(
                "question_type", "unknown"
            ),
            "answer": question.answer,
            "analysis": question.metadata.get("analysis", ""),
            "solution": question.solution,
            "difficulty": question.metadata.get("difficulty", 3),
            "knowledge_points": to_plain_data(
                question.metadata.get("knowledge_points", [])
            ),
            "options": to_plain_data(question.options or []),
        }
        system, user = self._prompt_registry.render(
            self.task_key,
            question_context=json.dumps(
                question_context, ensure_ascii=False
            ),
            variant_mode=variant_mode,
            question_type=question_context["question_type"],
        )
        trace_id = question.metadata.get("trace_id")
        result = self._ai_client.complete(
            self.task_key,
            system=system,
            user=user,
            images=(),
            trace_id=str(trace_id) if trace_id is not None else None,
        )
        if result.provider != "qwen":
            raise AIResponseError(
                "Variant generation must use the configured Qwen provider"
            )
        parsed = ResponseParser.parse_json(result.content)
        if not isinstance(parsed, dict):
            raise AIResponseError(
                "Variant generation response must be a JSON object"
            )
        try:
            validated = _VariantResponse.model_validate(parsed)
        except ValidationError:
            raise AIResponseError(
                "Variant generation response failed schema validation"
            ) from None
        return {
            "parsed": validated.model_dump(exclude_none=True),
            "raw_response": result.content,
            "response_json": json.dumps(
                result.raw_response, ensure_ascii=False
            ),
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
        }
