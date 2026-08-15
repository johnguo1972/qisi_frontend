"""Mode A, B, and C question-answer components."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from apps.common.ai.schemas import (
    ModeAResponse,
    ModeBResponse,
    ModeCResponse,
    has_visible_text,
)
from apps.common.ai.exceptions import AIResponseError

from .base import QuestionAIComponent, QuestionInput, to_plain_data


_MODE_A_STEP_NUMBER_PATTERN = re.compile(
    r"(?:(?:步骤|step)\s*)?([1-9]\d*)", re.IGNORECASE
)
_MODE_A_NONPOSITIVE_OR_NONINTEGER_STEP_PATTERN = re.compile(
    r"(?:(?:步骤|step)\s*)?[+-]?\d+(?:\.\d+)?", re.IGNORECASE
)
_CORRUPTED_LATEX_CONTROL_PATTERN = re.compile(r"[\x08\x09\x0c\x0e\x0f][A-Za-z]{2,}")


def _knowledge_refs(question: QuestionInput) -> str:
    refs = question.metadata.get("knowledge_refs", "")
    if isinstance(refs, str):
        return refs
    if isinstance(refs, (list, tuple)):
        values: list[str] = []
        for ref in refs:
            if isinstance(ref, Mapping):
                value = ref.get("module") or ref.get("full_label")
            else:
                value = ref
            if value:
                values.append(str(value))
        return ", ".join(values)
    return str(refs) if refs else ""


def normalize_mode_answer_payload(mode: str, result: dict) -> dict:
    """Return a normalized mode payload without mutating the provider result."""
    normalized = dict(result)
    if mode == "A":
        steps = normalized.get("steps")
        if isinstance(steps, list):
            normalized_steps = []
            for step_position, item in enumerate(steps, start=1):
                if not isinstance(item, dict):
                    normalized_steps.append(item)
                    continue
                step = dict(item)
                step_number = step.get("step")
                step_text = ""
                if isinstance(step_number, str):
                    match = _MODE_A_STEP_NUMBER_PATTERN.fullmatch(step_number)
                    if match is not None:
                        step["step"] = int(match.group(1))
                    elif _MODE_A_NONPOSITIVE_OR_NONINTEGER_STEP_PATTERN.fullmatch(
                        step_number
                    ):
                        step["step"] = None
                    elif has_visible_text(step_number):
                        step["step"] = step_position
                        step_text = step_number
                elif isinstance(step_number, int) and step_number <= 0:
                    step["step"] = None
                content = step.get("content")
                description = step.get("description")
                reason = step.get("reason")
                reasoning = step.get("reasoning")
                content_missing = content is None or (
                    isinstance(content, str) and not has_visible_text(content)
                )
                if content_missing:
                    for fallback in (description, reason, reasoning, step_text):
                        if isinstance(fallback, str) and has_visible_text(fallback):
                            step["content"] = fallback
                            break
                step.pop("reason", None)
                step.pop("reasoning", None)
                normalized_steps.append(step)
            normalized["steps"] = normalized_steps
        missing = normalized.get("missing_conditions")
        if missing is None:
            normalized["missing_conditions"] = []
        elif isinstance(missing, str):
            normalized["missing_conditions"] = [missing] if missing.strip() else []
    elif mode == "B":
        questions = normalized.get("questions")
        if isinstance(questions, list):
            normalized_questions = []
            for item in questions:
                if not isinstance(item, dict):
                    normalized_questions.append(item)
                    continue
                question = dict(item)
                raw_options = question.get("options")
                if isinstance(raw_options, list):
                    normalized_options: dict[str, str] = {}
                    for option in raw_options:
                        if not isinstance(option, dict):
                            break
                        label = option.get("label")
                        content = option.get("content")
                        if (
                            not isinstance(label, str)
                            or not isinstance(content, str)
                            or not has_visible_text(content)
                        ):
                            break
                        label = label.strip().upper()
                        if (
                            label not in {"A", "B", "C", "D"}
                            or label in normalized_options
                        ):
                            break
                        normalized_options[label] = content
                    else:
                        if set(normalized_options) == {"A", "B", "C", "D"}:
                            question["options"] = {
                                label: normalized_options[label] for label in "ABCD"
                            }
                correct_option = question.get("correct_option")
                correct_answer = question.get("correct_answer")
                if not correct_option and correct_answer in ("A", "B", "C", "D"):
                    correct_option = correct_answer
                if not correct_answer and correct_option in ("A", "B", "C", "D"):
                    correct_answer = correct_option
                explanation = (
                    question.get("analysis")
                    or question.get("explanation")
                    or ""
                )
                question["correct_answer"] = correct_answer or ""
                question["correct_option"] = correct_option or ""
                question["explanation"] = explanation
                question["analysis"] = explanation
                normalized_questions.append(question)
            normalized["questions"] = normalized_questions
    return normalized


def _contains_corrupted_latex_control(value: object) -> bool:
    if isinstance(value, str):
        return _CORRUPTED_LATEX_CONTROL_PATTERN.search(value) is not None
    if isinstance(value, dict):
        return any(_contains_corrupted_latex_control(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_corrupted_latex_control(item) for item in value)
    return False


class _ModeAnswerComponent(QuestionAIComponent):
    mode: str

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        from apps.common.ai.question_context import question_context_payload

        vision = question.metadata.get("vision_result", {})
        context = question_context_payload(question)
        normalized_text = question.metadata.get("normalized_text") or question.stem
        options = context["options"]
        if options:
            normalized_text = "{}\n\n完整选项：\n{}".format(
                normalized_text,
                "\n".join(
                    f"{option['label']}: {option['content']}" for option in options
                ),
            )
        return {
            "question_context_json": json.dumps(
                context,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "normalized_text": normalized_text,
            "vision_json": json.dumps(
                to_plain_data(vision), ensure_ascii=False
            ),
            "knowledge_refs": _knowledge_refs(question),
        }

    def validate_result(self, result: dict, question: QuestionInput) -> dict:
        if _contains_corrupted_latex_control(result):
            raise AIResponseError(
                "AI mode answer contains corrupted LaTeX control characters"
            )
        return result


class ModeAAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_a_answer"
    mode = "A"
    response_schema = ModeAResponse

    def normalize(self, result: dict) -> dict:
        return normalize_mode_answer_payload(self.mode, result)


class ModeBAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_b_answer"
    mode = "B"
    response_schema = ModeBResponse

    def normalize(self, result: dict) -> dict:
        return normalize_mode_answer_payload(self.mode, result)


class ModeCAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_c_answer"
    mode = "C"
    response_schema = ModeCResponse

    def normalize(self, result: dict) -> dict:
        return normalize_mode_answer_payload(self.mode, result)
