"""Shared answer consistency verifier."""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.schemas import NonBlankStr
from apps.common.ai.schemas import ResultVerifierResponse

from .base import QuestionAIComponent, QuestionInput, to_plain_data


class _VariantVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    passed: bool
    issues: list[NonBlankStr]
    score: float = Field(ge=0, le=1)
    summary: NonBlankStr


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

    def verify(
        self, task_key: str, original: dict, candidate: dict
    ) -> dict:
        """Verify a candidate using an explicitly configured verifier task."""
        if task_key != "variant_verify_deepseek":
            raise ValueError("Unsupported result verifier task")

        system, user = self._prompt_registry.render(
            task_key,
            variant_json=json.dumps(candidate, ensure_ascii=False),
            original_question_context=json.dumps(
                original, ensure_ascii=False
            ),
        )
        result = self._ai_client.complete(
            task_key,
            system=system,
            user=user,
            images=(),
            trace_id=None,
        )
        if result.provider != "deepseek":
            raise AIResponseError(
                "Variant verification requires the DeepSeek provider"
            )
        parsed = ResponseParser.parse_json(result.content)
        if not isinstance(parsed, dict):
            raise AIResponseError(
                "Variant verification response must be a JSON object"
            )
        try:
            validated = _VariantVerificationResponse.model_validate(parsed)
        except ValidationError:
            raise AIResponseError(
                "Variant verification response failed schema validation"
            ) from None
        return {
            **validated.model_dump(exclude_none=True),
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
        }
