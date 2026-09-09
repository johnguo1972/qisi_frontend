"""Database-free student and teacher guidance AI component."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.image_codec import prepare_image_sources
from apps.common.ai.schemas import (
    NonBlankStr,
    has_visible_text,
    strip_visual_boundaries,
)

from .base import AICompleter, QuestionInput


class _GuidanceEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    result: Literal["correct", "partial", "incorrect", "unclear"]
    error_type: Literal[
        "none",
        "concept_error",
        "diagram_error",
        "calculation_error",
        "missing_condition",
        "incomplete_expression",
        "off_topic",
        "unclear",
    ] | None
    evaluation: NonBlankStr
    correction_direction: NonBlankStr
    next_question: NonBlankStr | None
    next_hint: NonBlankStr | None
    confidence: float = Field(ge=0, le=1)


class _FixedGuidanceEvaluation(BaseModel):
    """AI response contract for one fixed-option learning action."""

    model_config = ConfigDict(extra="forbid", strict=True)

    feedback: NonBlankStr
    known_information: NonBlankStr
    guidance: NonBlankStr
    next_question: NonBlankStr | None = None
    next_hint: NonBlankStr | None = None
    confidence: float = Field(ge=0, le=1)


class _LegacyGuidanceEvaluation(BaseModel):
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
    mode: str = ""
    current_question: str = ""
    current_reference_answer: str = ""
    key_points: tuple[object, ...] = ()
    question_options: tuple[object, ...] = ()
    question_analysis: str = ""
    knowledge_points: tuple[object, ...] = ()
    visual_facts: tuple[object, ...] = ()
    image_urls: tuple[str, ...] = ()
    history: tuple[object, ...] = ()
    program_is_correct: bool | None = None
    # Explicit semantic fields for student guidance.  The legacy fields above
    # remain for compatibility with existing callers and tests.
    original_question_text: str = ""
    original_question_options: tuple[object, ...] = ()
    fixed_guidance_step: dict[str, object] | None = None
    student_selected_guidance_step: str = ""
    guidance_step_is_correct: bool | None = None


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

    def evaluate_student_reply(self, context: GuidanceContext) -> dict | str:
        if not context.mode:
            # Keep the old synchronous helper contract for non-student callers.
            return self._evaluate("guidance_evaluate", context)
        return self._evaluate_structured("guidance_evaluate", context)

    def evaluate_fixed_guidance_reply(self, context: GuidanceContext) -> dict:
        """Evaluate one B-mode action without solving the original question."""
        if context.mode != "B":
            raise ValueError("fixed guidance evaluation requires B mode")
        system, user = self._prompt_registry.render(
            "guidance_fixed_evaluate",
            question_text=_evaluation_question_text(context),
            reference_answer="仅分析当前解题动作，不提供原题答案",
            student_answer=context.student_selected_guidance_step or context.student_answer,
        )
        result = self._complete(
            "guidance_fixed_evaluate",
            system=system,
            user=user,
            # The question API exposes browser-facing URLs such as
            # ``/media/...``.  The provider cannot fetch those relative URLs;
            # prepare local media as bounded data URIs and preserve valid
            # HTTPS/data sources.
            images=(
                prepare_image_sources(context.image_urls)
                if context.image_urls else ()
            ),
            trace_id=context.trace_id,
        )
        parsed = ResponseParser.parse_json(
            strip_visual_boundaries(result.content)
        )
        return _normalize_fixed_guidance_payload(parsed)

    def evaluate_teacher_reply(self, context: GuidanceContext) -> dict:
        return {
            "evaluation": self._evaluate(
                "teacher_guidance_evaluate", context
            )
        }

    def _evaluate_structured(
        self, task_key: str, context: GuidanceContext
    ) -> dict:
        result = self._complete_evaluation(task_key, context)
        return _parse_guidance_evaluation(result.content)

    def _evaluate(self, task_key: str, context: GuidanceContext) -> str:
        result = self._complete_evaluation(task_key, context)
        return _parse_evaluation(result.content)

    def _complete_evaluation(self, task_key: str, context: GuidanceContext):
        # In a student guidance session, the reference answer belongs to the
        # current guidance step.  Falling back to the original answer here
        # makes a fixed guidance option such as "B. 使用公式" look like the
        # original question's option B to the model.
        if context.mode:
            evaluation_reference_answer = (
                context.current_reference_answer
                or "当前引导步骤暂无预设参考答案"
            )
        else:
            evaluation_reference_answer = (
                context.current_reference_answer or context.reference_answer
            )
        evaluation_student_answer = context.student_answer
        if context.mode == "B" and context.student_selected_guidance_step:
            evaluation_student_answer = context.student_selected_guidance_step
        system, user = self._prompt_registry.render(
            task_key,
            question_text=_evaluation_question_text(context),
            reference_answer=evaluation_reference_answer,
            student_answer=evaluation_student_answer,
        )
        result = self._complete(
            task_key,
            system=system,
            user=user,
            trace_id=context.trace_id,
        )
        return result

    def _complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None,
    ):
        if self._ai_client is not None:
            return self._ai_client.complete(
                task_key,
                system=system,
                user=user,
                images=images,
                trace_id=trace_id,
            )
        with AIClient() as client:
            return client.complete(
                task_key,
                system=system,
                user=user,
                images=images,
                trace_id=trace_id,
            )


def _evaluation_question_text(context: GuidanceContext) -> str:
    """Render unambiguous original-question and guidance-step semantics."""
    # Preserve the historical prompt text for non-student/legacy callers.
    # The explicit semantic contract is required only for B/C student flows.
    if not context.mode and not any(
        (
            context.original_question_text,
            context.original_question_options,
            context.fixed_guidance_step,
            context.student_selected_guidance_step,
            context.guidance_step_is_correct is not None,
        )
    ):
        return context.question_text
    original_question_text = context.original_question_text or context.question_text
    sections = [f"【原题内容】\n{original_question_text}"]
    if context.mode:
        sections.append(
            f"引导模式：{context.mode}\n"
            "以下字段含义必须严格区分：原题内容、原题答案选项、固定引导步骤、"
            "学生选择的引导步骤、引导步骤是否正确。固定引导步骤中的 A/B/C/D "
            "只是引导方法标签，不能当作原题答案选项。"
        )
    # For student guidance, ``question_options`` is a legacy field whose old
    # callers may use for the current step.  Never reinterpret it as original
    # answer options when the explicit semantic field is absent.
    original_question_options = context.original_question_options
    if not context.mode:
        original_question_options = original_question_options or context.question_options
    if original_question_options:
        sections.append(
            "【原题答案选项】"
            + json.dumps(
                list(original_question_options), ensure_ascii=False, default=str
            )
        )
    fixed_guidance_step = context.fixed_guidance_step
    if fixed_guidance_step is None and (
        context.current_question or context.question_options
    ):
        fixed_guidance_step = {
            "question": context.current_question,
            "options": list(context.question_options),
        }
    if fixed_guidance_step:
        sections.append(
            "【固定引导步骤】"
            + json.dumps(fixed_guidance_step, ensure_ascii=False, default=str)
        )
    student_selected_guidance_step = (
        context.student_selected_guidance_step or context.student_answer
    )
    if student_selected_guidance_step:
        sections.append(
            f"【学生选择的引导步骤】\n{student_selected_guidance_step}"
        )
    guidance_step_is_correct = context.guidance_step_is_correct
    if guidance_step_is_correct is None and context.mode == "B":
        guidance_step_is_correct = context.program_is_correct
    if guidance_step_is_correct is not None:
        sections.append(
            f"【引导步骤是否正确】{guidance_step_is_correct}"
        )
    if context.current_question and fixed_guidance_step is None:
        sections.append(f"当前引导问题：{context.current_question}")
    if context.key_points:
        sections.append(
            "当前步骤关键点："
            + json.dumps(list(context.key_points), ensure_ascii=False, default=str)
        )
    if context.question_analysis:
        sections.append(f"题目解析：{context.question_analysis}")
    if context.knowledge_points:
        sections.append(
            "知识点："
            + json.dumps(
                list(context.knowledge_points), ensure_ascii=False, default=str
            )
        )
    if context.visual_facts:
        sections.append(
            "图像事实："
            + json.dumps(
                list(context.visual_facts), ensure_ascii=False, default=str
            )
        )
    if context.history:
        sections.append(
            "历史回答："
            + json.dumps(list(context.history), ensure_ascii=False, default=str)
        )
    if context.program_is_correct is not None:
        sections.append(f"B模式程序判定：{context.program_is_correct}")
    return "\n".join(sections)


def _normalize_fixed_guidance_payload(payload: object) -> dict:
    """Normalize harmless provider variations without weakening B semantics."""
    if not isinstance(payload, dict):
        raise AIResponseError("AI fixed guidance response must be an object")

    def required_text(name: str) -> str:
        value = _fixed_guidance_text_value(payload.get(name))
        if value is None:
            raise AIResponseError(f"AI fixed guidance field {name} is invalid")
        value = strip_visual_boundaries(value)
        if not has_visible_text(value):
            raise AIResponseError(f"AI fixed guidance field {name} is blank")
        return value

    def optional_text(name: str) -> str | None:
        value = _fixed_guidance_text_value(payload.get(name))
        if value is None:
            return None
        value = strip_visual_boundaries(value)
        return value if has_visible_text(value) else None

    confidence = payload.get("confidence")
    if isinstance(confidence, bool):
        raise AIResponseError("AI fixed guidance confidence is invalid")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        raise AIResponseError("AI fixed guidance confidence is invalid") from None
    if not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise AIResponseError("AI fixed guidance confidence is invalid")

    normalized = {
        "feedback": required_text("feedback"),
        "known_information": required_text("known_information"),
        "guidance": required_text("guidance"),
        "next_question": optional_text("next_question"),
        "next_hint": optional_text("next_hint"),
        "confidence": confidence,
    }
    try:
        return _FixedGuidanceEvaluation.model_validate(normalized).model_dump()
    except (AttributeError, TypeError, ValueError):
        raise AIResponseError("AI fixed guidance response failed validation") from None


def _fixed_guidance_text_value(value: object) -> str | None:
    """Accept text or a simple list of text items from the provider."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if not isinstance(item, (str, int, float)) or isinstance(item, bool):
                return None
            text = str(item).strip()
            if text:
                items.append(text)
        return "；".join(items)
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return None
    return None


def _parse_guidance_evaluation(content: str) -> dict:
    """Parse the strict one-call student analysis response."""
    stripped = strip_visual_boundaries(ResponseParser.parse_text(content))
    if stripped.startswith("```"):
        fence = _JSON_FENCE.fullmatch(stripped)
        if (
            fence is None
            or fence.group("label").strip().lower() not in ("", "json")
        ):
            raise AIResponseError("AI guidance evaluation fence is malformed")
        stripped = fence.group("body").strip()
    if not stripped.startswith("{"):
        raise AIResponseError("AI guidance evaluation must be a JSON object")
    return ResponseParser.parse_json(stripped, _GuidanceEvaluation)


_JSON_FENCE = re.compile(
    r"\A```(?P<label>[^\r\n`]*)[ \t]*\r?\n"
    r"(?P<body>.*?)\r?\n```[ \t]*\Z",
    re.IGNORECASE | re.DOTALL,
)
_PLAIN_MARKER_LIMIT = 64


def _parse_evaluation(content: str) -> str:
    stripped = strip_visual_boundaries(ResponseParser.parse_text(content))
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

    parsed = ResponseParser.parse_json(content, _LegacyGuidanceEvaluation)
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
