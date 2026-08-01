"""Value types returned by the shared AI runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AIResult:
    content: str
    provider: str
    model: str
    latency_ms: int
    raw_response: dict
