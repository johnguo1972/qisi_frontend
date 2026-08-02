"""Mode A, B, and C question-answer components."""

from __future__ import annotations

import json
from collections.abc import Mapping

from apps.common.ai.schemas import (
    ModeAResponse,
    ModeBResponse,
    ModeCResponse,
)

from .base import QuestionAIComponent, QuestionInput, to_plain_data


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


class _ModeAnswerComponent(QuestionAIComponent):
    mode: str

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        vision = question.metadata.get("vision_result", {})
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            ),
            "vision_json": json.dumps(
                to_plain_data(vision), ensure_ascii=False
            ),
            "knowledge_refs": _knowledge_refs(question),
        }

    def normalize(self, result: dict) -> dict:
        return dict(result)


class ModeAAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_a_answer"
    mode = "A"
    response_schema = ModeAResponse

    def normalize(self, result: dict) -> dict:
        normalized = super().normalize(result)
        missing = normalized.get("missing_conditions")
        if missing is None:
            normalized["missing_conditions"] = []
        elif isinstance(missing, str):
            normalized["missing_conditions"] = [missing] if missing.strip() else []
        return normalized


class ModeBAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_b_answer"
    mode = "B"
    response_schema = ModeBResponse

    def normalize(self, result: dict) -> dict:
        normalized = super().normalize(result)
        questions = normalized.get("questions")
        if isinstance(questions, list):
            normalized_questions = []
            for item in questions:
                if not isinstance(item, dict):
                    normalized_questions.append(item)
                    continue
                question = dict(item)
                correct_answer = question.get("correct_option")
                if not correct_answer:
                    legacy_answer = question.get("correct_answer")
                    correct_answer = (
                        legacy_answer
                        if legacy_answer in ("A", "B", "C", "D")
                        else ""
                    )
                explanation = (
                    question.get("analysis")
                    or question.get("explanation")
                    or ""
                )
                question["correct_answer"] = correct_answer
                question["correct_option"] = correct_answer
                question["explanation"] = explanation
                question["analysis"] = explanation
                normalized_questions.append(question)
            normalized["questions"] = normalized_questions
        return normalized


class ModeCAnswerComponent(_ModeAnswerComponent):
    task_key = "mode_c_answer"
    mode = "C"
    response_schema = ModeCResponse
