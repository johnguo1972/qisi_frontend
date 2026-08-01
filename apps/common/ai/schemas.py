"""Pydantic schemas for provider response envelopes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    content: str


class AIChoice(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: AIMessage


class AIResponseEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    choices: list[AIChoice] = Field(min_length=1)
