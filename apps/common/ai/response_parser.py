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

        candidate, ignored_structured_tail = _extract_json_candidate(text)
        parse_failed = True
        if ignored_structured_tail:
            try:
                parsed = json.loads(candidate)
                parse_failed = False
            except (json.JSONDecodeError, TypeError):
                pass

        if parse_failed and candidate.startswith("["):
            repaired = repair_json_string('{"_root":' + candidate + "}")
            try:
                parsed = json.loads(repaired)["_root"]
                parse_failed = False
            except (json.JSONDecodeError, KeyError, TypeError):
                parse_failed = True
        elif parse_failed:
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


def _extract_json_candidate(text: str) -> tuple[str, bool]:
    stripped = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```\s*$", "", stripped).strip()
    object_start = stripped.find("{")
    array_start = stripped.find("[")
    starts = [index for index in (object_start, array_start) if index >= 0]
    if not starts:
        return stripped, False
    start = min(starts)
    complete_end = _first_complete_json_end(stripped, start)
    if complete_end is not None:
        trailing = stripped[complete_end + 1 :].lstrip()
        return (
            stripped[start : complete_end + 1],
            trailing.startswith(("{", "[")),
        )
    closing = "}" if stripped[start] == "{" else "]"
    end = stripped.rfind(closing)
    return (
        stripped[start : end + 1] if end > start else stripped[start:],
        False,
    )


def _first_complete_json_end(text: str, start: int) -> int | None:
    opening = {"{": "}", "[": "]"}
    stack: list[str] = []
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
        elif character in opening:
            stack.append(opening[character])
        elif character in ("}", "]"):
            if not stack or character != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return index
    return None
