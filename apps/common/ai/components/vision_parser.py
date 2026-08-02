"""Database-free vision parsing through the shared AI runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import (
    AIConfigError,
    AIPromptError,
    AIResponseError,
)
from apps.common.ai.image_codec import prepare_image_sources
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.schemas import CourseMaterialRecognitionResponse
from apps.common.exceptions import AIRequestError

from .base import AICompleter


@dataclass(frozen=True)
class _Failure:
    kind: Literal["config", "prompt", "request", "response", "schema"]


@dataclass(frozen=True)
class _Outcome:
    value: dict[str, Any] | None = None
    failure: _Failure | None = None


class VisionParserComponent:
    """Run fixed vision tasks without credentials, prompts, HTTP, or DB access."""

    def __init__(
        self,
        ai_client: AICompleter | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._ai_client = ai_client or AIClient()
        self._prompt_registry = prompt_registry or PromptRegistry()

    def detect_positions(self, image_path: str) -> dict[str, Any]:
        outcome = self._execute(
            "vision_position_detect", (image_path,), {}, trace_id=None
        )
        image_path = ""
        return _unwrap(outcome)

    def parse_page(self, image_path: str) -> dict[str, Any]:
        outcome = self._execute(
            "vision_page_parse", (image_path,), {}, trace_id=None
        )
        image_path = ""
        return _unwrap(outcome)

    def parse_question(
        self, images, context: dict[str, object]
    ) -> dict[str, Any]:
        prompt_context = {
            "question_no": context.get("question_no", "?"),
            "question_type": context.get("question_type", "unknown"),
            "question_type_label": context.get("question_type_label", "未知"),
            "section_title": context.get("section_title", ""),
            "page_start": context.get("page_start", 1),
            "page_end": context.get(
                "page_end", context.get("page_start", 1)
            ),
            "multi_page_notice": context.get("multi_page_notice", ""),
        }
        trace_id = context.get("trace_id")
        outcome = self._execute(
            "vision_question_parse",
            images,
            prompt_context,
            trace_id=str(trace_id) if trace_id is not None else None,
        )
        images = ()
        context = {}
        prompt_context = {}
        trace_id = None
        return _unwrap(outcome)

    def recognize_photo(self, images) -> dict:
        outcome = self._execute(
            "photo_recognize", images, {}, trace_id=None
        )
        images = ()
        return _unwrap(outcome)["parsed"]

    def recognize_course_material(self, images) -> dict:
        outcome = self._execute(
            "course_material_recognize",
            images,
            {},
            trace_id=None,
            schema=CourseMaterialRecognitionResponse,
        )
        images = ()
        return _unwrap(outcome)["parsed"]

    def extract_facts(self, images, stem: str) -> dict:
        outcome = self._execute(
            "vision_fact_extract",
            images,
            {"normalized_text": stem},
            trace_id=None,
        )
        images = ()
        stem = ""
        return _unwrap(outcome)["parsed"]

    def _execute(
        self,
        task_key: str,
        images,
        variables: dict[str, object],
        *,
        trace_id: str | None,
        schema=None,
    ) -> _Outcome:
        prepared_images: tuple[str, ...] = ()
        system = ""
        user = ""
        try:
            prepared_images = prepare_image_sources(images)
            system, user = self._prompt_registry.render(task_key, **variables)
            result = self._ai_client.complete(
                task_key,
                system=system,
                user=user,
                images=prepared_images,
                trace_id=trace_id,
            )
            parsed = ResponseParser.parse_json(result.content, schema)
            if not isinstance(parsed, dict):
                return _Outcome(failure=_Failure("response"))
            return _Outcome(
                value={
                    "raw_response": result.content,
                    "response_json": json.dumps(
                        result.raw_response, ensure_ascii=False
                    ),
                    "latency_ms": result.latency_ms,
                    "parsed": parsed,
                    "provider": result.provider,
                    "model": result.model,
                }
            )
        except AIConfigError:
            return _Outcome(failure=_Failure("config"))
        except AIPromptError:
            return _Outcome(failure=_Failure("prompt"))
        except AIResponseError:
            return _Outcome(
                failure=_Failure("schema" if schema is not None else "response")
            )
        except AIRequestError:
            return _Outcome(failure=_Failure("request"))
        except Exception:
            return _Outcome(failure=_Failure("request"))
        finally:
            images = ()
            variables = {}
            prepared_images = ()
            system = ""
            user = ""
            trace_id = None


def _raise_failure(failure: _Failure) -> None:
    if failure.kind == "config":
        raise AIConfigError("Vision AI configuration is unavailable")
    if failure.kind == "prompt":
        raise AIPromptError("Vision AI prompt is unavailable")
    if failure.kind == "response":
        raise AIResponseError("Vision AI response must be a valid JSON object")
    if failure.kind == "schema":
        raise AIResponseError("Vision AI response failed schema validation")
    raise AIRequestError("Vision AI request failed")


def _unwrap(outcome: _Outcome) -> dict[str, Any]:
    if outcome.failure is not None:
        _raise_failure(outcome.failure)
    if outcome.value is None:
        raise AIResponseError("Vision AI response is missing")
    return outcome.value
