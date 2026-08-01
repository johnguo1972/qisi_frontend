"""Shared OpenAI-compatible client for configured AI tasks."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from apps.common.exceptions import AIRequestError

from .config import AIConfig, AITaskConfig, load_ai_config
from .exceptions import AIResponseError
from .response_parser import ResponseParser
from .types import AIResult


logger = logging.getLogger(__name__)


class AIClient:
    """Execute configured AI tasks through an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if client is not None and transport is not None:
            raise ValueError("client and transport cannot both be provided")
        self._config: AIConfig = load_ai_config()
        self._client = client
        self._transport = transport
        self._sleeper = sleeper

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images: Sequence[str] = (),
        trace_id: str | None = None,
    ) -> AIResult:
        task = self._config.get_task_config(task_key)
        provider = self._config.get_provider_config(task.provider)
        payload = _build_payload(task, system=system, user=user, images=images)
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        log_fields = {
            "task_key": task.key,
            "provider": provider.name,
            "model": task.model,
            "trace_id": _trace_id_hash(trace_id),
        }
        logger.info("AI request started", extra=log_fields)
        started = time.perf_counter()

        if self._client is not None:
            return self._complete_with_client(
                self._client,
                task=task,
                url=provider.api_url,
                headers=headers,
                payload=payload,
                log_fields=log_fields,
                started=started,
            )

        with httpx.Client(
            transport=self._transport,
            trust_env=False,
        ) as client:
            return self._complete_with_client(
                client,
                task=task,
                url=provider.api_url,
                headers=headers,
                payload=payload,
                log_fields=log_fields,
                started=started,
            )

    def _complete_with_client(
        self,
        client: httpx.Client,
        *,
        task: AITaskConfig,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        log_fields: dict[str, str | None],
        started: float,
    ) -> AIResult:
        terminal_error: tuple[str, int | None] | None = None
        attempts = task.retry_count + 1

        for attempt_index in range(attempts):
            response: httpx.Response | None = None
            failure_kind: str | None = None
            status_code: int | None = None
            try:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=task.timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                status_code = error.response.status_code
                failure_kind = "http_status"
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                failure_kind = "timeout"
            except httpx.HTTPError:
                failure_kind = "transport"

            if failure_kind is None:
                return _result_from_response(
                    response,
                    task=task,
                    started=started,
                    log_fields=log_fields,
                )

            retryable = _is_retryable(failure_kind, status_code)
            if retryable and attempt_index + 1 < attempts:
                delay = _retry_delay(task, attempt_index)
                logger.warning(
                    "AI request will retry",
                    extra={
                        **log_fields,
                        "attempt": attempt_index + 1,
                        "status_code": status_code,
                        "retry_delay_seconds": delay,
                    },
                )
                self._sleeper(delay)
                continue

            terminal_error = (failure_kind, status_code)
            break

        assert terminal_error is not None
        failure_kind, status_code = terminal_error
        logger.error(
            "AI request failed",
            extra={
                **log_fields,
                "status_code": status_code,
                "latency_ms": _latency_ms(started),
            },
        )
        if failure_kind == "http_status":
            raise AIRequestError(
                f"AI provider request failed with HTTP {status_code}"
            )
        if failure_kind == "timeout":
            raise AIRequestError("AI provider request timed out")
        raise AIRequestError("AI provider request failed")


def _build_payload(
    task: AITaskConfig,
    *,
    system: str,
    user: str,
    images: Sequence[str],
) -> dict[str, Any]:
    user_content: str | list[dict[str, Any]]
    if images:
        user_content = [{"type": "text", "text": user}]
        user_content.extend(
            {"type": "image_url", "image_url": {"url": image}}
            for image in images
        )
    else:
        user_content = user

    payload: dict[str, Any] = {
        "model": task.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": task.temperature,
        "max_tokens": task.max_tokens,
    }
    if task.response_format:
        response_type = task.response_format
        if response_type == "json":
            response_type = "json_object"
        payload["response_format"] = {"type": response_type}
    return payload


def _result_from_response(
    response: httpx.Response | None,
    *,
    task: AITaskConfig,
    started: float,
    log_fields: dict[str, str | None],
) -> AIResult:
    if response is None:
        raise AIResponseError("AI response is missing")

    invalid_json = False
    try:
        raw_response = response.json()
    except ValueError:
        invalid_json = True
        raw_response = None
    if invalid_json or not isinstance(raw_response, dict):
        raise AIResponseError("AI response is not a JSON object")

    content = ResponseParser.extract_content(raw_response)
    latency_ms = _latency_ms(started)
    logger.info(
        "AI request completed",
        extra={**log_fields, "latency_ms": latency_ms},
    )
    return AIResult(
        content=content,
        provider=task.provider,
        model=task.model,
        latency_ms=latency_ms,
        raw_response=raw_response,
    )


def _is_retryable(failure_kind: str, status_code: int | None) -> bool:
    if failure_kind == "timeout":
        return True
    is_server_error = status_code is not None and 500 <= status_code <= 599
    return failure_kind == "http_status" and (
        status_code == 429 or is_server_error
    )


def _retry_delay(task: AITaskConfig, retry_index: int) -> float:
    if not task.retry_backoff_seconds:
        return 0.0
    return task.retry_backoff_seconds[
        min(retry_index, len(task.retry_backoff_seconds) - 1)
    ]


def _latency_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _trace_id_hash(trace_id: str | None) -> str | None:
    if trace_id is None:
        return None
    return hashlib.sha256(trace_id.encode("utf-8")).hexdigest()[:16]
