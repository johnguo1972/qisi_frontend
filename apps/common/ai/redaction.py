"""Centralized redaction for AI logs and diagnostic previews."""

from __future__ import annotations

import base64
import binascii
import re


DEFAULT_PREVIEW_LIMIT = 160


def safe_preview(text: str, *, limit: int = DEFAULT_PREVIEW_LIMIT) -> str:
    """Return a compact diagnostic preview without common secrets or PII."""
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
    if len(preview) > limit:
        return preview[:limit] + "…"
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
