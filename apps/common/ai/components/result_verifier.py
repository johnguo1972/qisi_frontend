"""Shared answer consistency verifier."""

from __future__ import annotations

import json

from apps.common.ai.schemas import ResultVerifierResponse

from .base import QuestionAIComponent, QuestionInput, to_plain_data


class ResultVerifierComponent(QuestionAIComponent):
    task_key = "result_verify"
    response_schema = ResultVerifierResponse

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            ),
            "vision_json": json.dumps(
                to_plain_data(question.metadata.get("vision_result", {})),
                ensure_ascii=False,
            ),
            "solver_output": json.dumps(
                to_plain_data(question.metadata.get("solver_output", {})),
                ensure_ascii=False,
            ),
        }
