"""Database-free student and teacher guidance AI component."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.schemas import NonBlankStr

from .base import AICompleter, QuestionInput


class _GuidanceEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evaluation: NonBlankStr


class _GuidanceStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: NonBlankStr
    hint: NonBlankStr


class _GuidanceGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    steps: list[_GuidanceStep] = Field(min_length=3, max_length=5)


@dataclass(frozen=True)
class GuidanceContext:
    question_text: str
    reference_answer: str = ""
    student_answer: str = ""
    trace_id: str | None = None


class GuidanceComponent:
    """Render, execute, and parse the three configured guidance tasks."""

    def __init__(
        self,
        ai_client: AICompleter | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._prompt_registry = prompt_registry or PromptRegistry()

    def generate(self, question: QuestionInput) -> dict:
        system, user = self._prompt_registry.render(
            "guidance_generate",
            stem=question.stem,
            answer=question.answer,
        )
        result = self._complete(
            "guidance_generate",
            system=system,
            user=user,
            trace_id=_trace_id(question.metadata.get("trace_id")),
        )
        parsed = ResponseParser.parse_json(result.content, _GuidanceGeneration)
        if not isinstance(parsed, dict):
            raise AIResponseError("AI guidance response must be an object")
        return parsed

    def evaluate_student_reply(self, context: GuidanceContext) -> str:
        return self._evaluate("guidance_evaluate", context)

    def evaluate_teacher_reply(self, context: GuidanceContext) -> dict:
        return {
            "evaluation": self._evaluate(
                "teacher_guidance_evaluate", context
            )
        }

    def _evaluate(self, task_key: str, context: GuidanceContext) -> str:
        system, user = self._prompt_registry.render(
            task_key,
            question_text=context.question_text,
            reference_answer=context.reference_answer,
            student_answer=context.student_answer,
        )
        result = self._complete(
            task_key,
            system=system,
            user=user,
            trace_id=context.trace_id,
        )
        return _parse_evaluation(result.content)

    def _complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        trace_id: str | None,
    ):
        if self._ai_client is not None:
            return self._ai_client.complete(
                task_key,
                system=system,
                user=user,
                trace_id=trace_id,
            )
        with AIClient() as client:
            return client.complete(
                task_key,
                system=system,
                user=user,
                trace_id=trace_id,
            )


_JSON_FENCE = re.compile(
    r"\A```(?P<label>[^\r\n`]*)[ \t]*\r?\n"
    r"(?P<body>.*?)\r?\n```[ \t]*\Z",
    re.IGNORECASE | re.DOTALL,
)
_PLAIN_MARKER_LIMIT = 64


def _parse_evaluation(content: str) -> str:
    stripped = ResponseParser.parse_text(content)
    if stripped.startswith("```"):
        fence = _JSON_FENCE.fullmatch(stripped)
        if (
            fence is None
            or fence.group("label").strip().lower() not in ("", "json")
        ):
            raise AIResponseError("AI guidance evaluation fence is malformed")
        return _parse_structured_evaluation(fence.group("body").strip())

    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            if _is_plain_marker(stripped):
                return stripped
            raise AIResponseError("AI guidance evaluation JSON is malformed")
        return _parse_structured_evaluation(stripped)

    return stripped


def _parse_structured_evaluation(content: str) -> str:
    try:
        json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise AIResponseError("AI guidance evaluation JSON is malformed")

    parsed = ResponseParser.parse_json(content, _GuidanceEvaluation)
    return ResponseParser.parse_text(parsed["evaluation"])


def _is_plain_marker(content: str) -> bool:
    if len(content) > _PLAIN_MARKER_LIMIT:
        return False
    pairs = {"{": "}", "[": "]"}
    closing = pairs.get(content[0])
    if closing is None or not content.endswith(closing):
        return False
    marker = content[1:-1]
    if not marker.strip():
        return False
    return not any(character in marker for character in '\"\\:,{}[]')


def _trace_id(value: object) -> str | None:
    return str(value) if value is not None else None


__all__ = [
    "GuidanceComponent",
    "GuidanceContext",
    "QuestionInput",
]
