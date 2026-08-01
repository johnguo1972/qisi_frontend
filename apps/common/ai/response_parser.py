"""Safe extraction, repair, and validation of AI responses."""

from __future__ import annotations

import base64
import binascii
import json
import re

from pydantic import BaseModel, ValidationError

from apps.common.utils import repair_json_string

from .exceptions import AIResponseError
from .schemas import AIResponseEnvelope


_PREVIEW_LIMIT = 160


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
                "AI response is not valid JSON; preview=" + _safe_preview(text)
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


def _safe_preview(text: str) -> str:
    preview = re.sub(
        r'''(?ix)
        (?P<prefix>
            (?<![A-Za-z0-9_])
            ["']?authorization["']?[ \t]*:[ \t]*
        )
        (?:
            "(?:\\[^\r\n]|[^"\\\r\n])*"?
            |
            '(?:\\[^\r\n]|[^'\\\r\n])*'?
            |
            Digest[ \t]+
            [!#$%&'*+\-.^_`|~A-Za-z0-9]+[ \t]*=[ \t]*
            (?:
                "(?:\\[^\r\n]|[^"\\\r\n])*"?
                |
                '(?:\\[^\r\n]|[^'\\\r\n])*'?
                |
                [^,\s;}\]\r\n]+
            )
            (?:
                [ \t]*,[ \t]*
                [!#$%&'*+\-.^_`|~A-Za-z0-9]+[ \t]*=[ \t]*
                (?:
                    "(?:\\[^\r\n]|[^"\\\r\n])*"?
                    |
                    '(?:\\[^\r\n]|[^'\\\r\n])*'?
                    |
                    [^,\s;}\]\r\n]+
                )
            )*
            |
            [^,}\]\r\n]+
        )
        ''',
        lambda match: match.group("prefix") + "[secret-redacted]",
        text,
    )
    preview = re.sub(
        r'''(?ix)
        (?P<prefix>
            (?<![A-Za-z0-9_])
            ["']?(?:key|api[_-]?key|access[_-]?token|refresh[_-]?token|
            token|secret)["']?[ \t]*[:=][ \t]*
        )
        (?:
            "(?:\\[^\r\n]|[^"\\\r\n])*"?
            |
            '(?:\\[^\r\n]|[^'\\\r\n])*'?
            |
            [^,\s;}\]]+
        )
        ''',
        lambda match: match.group("prefix") + "[secret-redacted]",
        preview,
    )
    preview = re.sub(
        r"data:[^,\s]+;base64,[A-Za-z0-9+/=]+",
        "[base64-redacted]",
        preview,
        flags=re.IGNORECASE,
    )
    preview = re.sub(r"\bBearer\s+\S+", "Bearer [redacted]", preview, flags=re.I)
    preview = re.sub(r"\bsk-[A-Za-z0-9._-]+", "[key-redacted]", preview)
    preview = re.sub(
        r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET)\s*[:=]\s*\S+",
        "[key-redacted]",
        preview,
        flags=re.I,
    )
    preview = re.sub(
        r"(?<![A-Za-z0-9+/_=-])[A-Za-z0-9+/_-]{32,}={0,2}"
        r"(?![A-Za-z0-9+/_=-])",
        _redact_encoded_token,
        preview,
    )
    preview = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[email-redacted]",
        preview,
    )
    preview = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[phone-redacted]", preview)
    preview = re.sub(r"\s+", " ", preview).strip()
    if len(preview) > _PREVIEW_LIMIT:
        return preview[:_PREVIEW_LIMIT] + "…"
    return preview


def _redact_encoded_token(match: re.Match[str]) -> str:
    token = match.group(0)
    unpadded = token.rstrip("=")
    is_urlsafe = "-" in unpadded or "_" in unpadded
    if is_urlsafe and ("+" in unpadded or "/" in unpadded):
        return token

    padded = unpadded + "=" * (-len(unpadded) % 4)
    altchars = b"-_" if is_urlsafe else None
    try:
        decoded = base64.b64decode(padded, altchars=altchars, validate=True)
    except (binascii.Error, ValueError):
        return token

    encoder = base64.urlsafe_b64encode if is_urlsafe else base64.b64encode
    canonical = encoder(decoded).decode("ascii").rstrip("=")
    if canonical != unpadded:
        return token
    return "[base64url-redacted]" if is_urlsafe else "[base64-redacted]"
