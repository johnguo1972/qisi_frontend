"""Safe extraction, repair, and validation of AI responses."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from apps.common.utils import repair_json_string

from .exceptions import AIResponseError
from .redaction import safe_preview
from .schemas import AIResponseEnvelope, has_visible_text


class ResponseParser:
    @staticmethod
    def extract_content(payload: dict) -> str:
        validation_failed = False
        try:
            envelope = AIResponseEnvelope.model_validate(payload)
        except (TypeError, ValidationError):
            validation_failed = True
        if validation_failed:
            raise AIResponseError("AI response content is missing or invalid")
        return envelope.choices[0].message.content

    @staticmethod
    def parse_json(
        text: str, schema: type[BaseModel] | None = None
    ) -> dict | list:
        if not isinstance(text, str):
            raise AIResponseError("AI response JSON must be text")

        candidate = _extract_json_candidate(text)
        if candidate.startswith("["):
            repaired = repair_json_string('{"_root":' + candidate + "}")
            try:
                parsed = json.loads(repaired)["_root"]
                parse_failed = False
            except (json.JSONDecodeError, KeyError, TypeError):
                parse_failed = True
        else:
            repaired = repair_json_string(candidate)
            try:
                parsed = json.loads(repaired)
                parse_failed = False
            except (json.JSONDecodeError, TypeError):
                parse_failed = True

        if parse_failed or not isinstance(parsed, (dict, list)):
            raise AIResponseError(
                "AI response is not valid JSON; preview=" + safe_preview(text)
            )

        if schema is None:
            return parsed

        schema_failed = False
        try:
            validated = schema.model_validate(parsed)
        except (AttributeError, TypeError, ValidationError):
            schema_failed = True
        if schema_failed:
            raise AIResponseError("AI response failed schema validation")
        return validated.model_dump()

    @staticmethod
    def parse_text(text: object) -> str:
        if not isinstance(text, str) or not has_visible_text(text):
            raise AIResponseError("AI response text is missing or invalid")
        return text.strip()


def _extract_json_candidate(text: str) -> str:
    stripped = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```\s*$", "", stripped).strip()
    object_start = stripped.find("{")
    array_start = stripped.find("[")
    starts = [index for index in (object_start, array_start) if index >= 0]
    if not starts:
        return stripped
    start = min(starts)
    closing = "}" if stripped[start] == "{" else "]"
    end = stripped.rfind(closing)
    return stripped[start : end + 1] if end > start else stripped[start:]
