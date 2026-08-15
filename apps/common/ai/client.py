"""Shared OpenAI-compatible client for configured AI tasks."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from apps.common.exceptions import AIRequestError

from .config import AIConfig, AITaskConfig, load_ai_config
from .exceptions import AIConfigError, AIResponseError
from .response_parser import ResponseParser
from .types import AIResult


logger = logging.getLogger(__name__)
_TRACE_HMAC_KEY = secrets.token_bytes(32)


@dataclass(frozen=True)
class _Failure:
    kind: Literal["config", "request", "response"]
    message: str


@dataclass(frozen=True)
class _Outcome:
    result: AIResult | None = None
    failure: _Failure | None = None


class _BorrowedTransport(httpx.BaseTransport):
    """Delegate requests without taking ownership of an injected transport."""

    def __init__(self, transport: httpx.BaseTransport) -> None:
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self._transport.handle_request(request)

    def close(self) -> None:
        return None


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
        self._sleeper = sleeper
        self._owns_client = client is None
        if client is not None:
            self._client = client
        else:
            borrowed = _BorrowedTransport(transport) if transport else None
            self._client = httpx.Client(
                transport=borrowed,
                trust_env=False,
            )

    def __enter__(self) -> "AIClient":
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close only the HTTP client and transport owned by this instance."""
        if self._owns_client and not self._client.is_closed:
            self._client.close()

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images: Sequence[str] = (),
        trace_id: str | None = None,
    ) -> AIResult:
        outcome: _Outcome | None = None
        try:
            outcome = self._execute(
                task_key,
                system=system,
                user=user,
                images=images,
                trace_id=trace_id,
                max_attempts=None,
            )
        finally:
            system = ""
            user = ""
            images = ()
            trace_id = None
        return _result_from_outcome(outcome)

    def complete_once(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images: Sequence[str] = (),
        trace_id: str | None = None,
    ) -> AIResult:
        """Execute exactly one HTTP attempt for a component-owned budget."""
        outcome: _Outcome | None = None
        try:
            outcome = self._execute(
                task_key,
                system=system,
                user=user,
                images=images,
                trace_id=trace_id,
                max_attempts=1,
            )
        finally:
            system = ""
            user = ""
            images = ()
            trace_id = None
        return _result_from_outcome(outcome)

    def _execute(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images: Sequence[str],
        trace_id: str | None,
        max_attempts: int | None,
    ) -> _Outcome:
        try:
            task = self._config.get_task_config(task_key)
            provider = self._config.get_provider_config(task.provider)
            if not provider.api_key:
                raise AIConfigError(
                    "AI provider credentials are not configured"
                )
            payload = _build_payload(
                task,
                system=system,
                user=user,
                images=images,
            )
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
            return self._complete_with_client(
                task=task,
                url=provider.api_url,
                headers=headers,
                payload=payload,
                log_fields=log_fields,
                started=time.perf_counter(),
                max_attempts=max_attempts,
            )
        except AIConfigError as error:
            return _Outcome(
                failure=_Failure(kind="config", message=str(error))
            )
        except Exception:
            logger.error("AI request failed before completion")
            return _Outcome(
                failure=_Failure(
                    kind="request",
                    message="AI provider request failed",
                )
            )
        finally:
            system = ""
            user = ""
            images = ()
            trace_id = None

    def _complete_with_client(
        self,
        *,
        task: AITaskConfig,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        log_fields: dict[str, str | None],
        started: float,
        max_attempts: int | None,
    ) -> _Outcome:
        attempts = task.retry_count + 1 if max_attempts is None else max_attempts

        for attempt_index in range(attempts):
            response: httpx.Response | None = None
            failure_kind: str | None = None
            status_code: int | None = None
            try:
                request = httpx.Request(
                    "POST",
                    url,
                    headers=headers,
                    json=payload,
                    extensions={
                        "timeout": httpx.Timeout(
                            task.timeout_seconds
                        ).as_dict()
                    },
                )
                response = self._client.send(
                    request,
                    auth=None,
                    follow_redirects=False,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                status_code = error.response.status_code
                failure_kind = "http_status"
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                failure_kind = "timeout"
            except httpx.HTTPError:
                failure_kind = "transport"
            except Exception:
                failure_kind = "transport"

            if failure_kind is None:
                return _outcome_from_response(
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

            logger.error(
                "AI request failed",
                extra={
                    **log_fields,
                    "status_code": status_code,
                    "latency_ms": _latency_ms(started),
                },
            )
            if failure_kind == "http_status":
                return _Outcome(
                    failure=_Failure(
                        kind="request",
                        message=(
                            "AI provider request failed with HTTP "
                            f"{status_code}"
                        ),
                    )
                )
            if failure_kind == "timeout":
                return _Outcome(
                    failure=_Failure(
                        kind="request",
                        message="AI provider request timed out",
                    )
                )
            return _Outcome(
                failure=_Failure(
                    kind="request",
                    message="AI provider request failed",
                )
            )

        return _Outcome(
            failure=_Failure(
                kind="request",
                message="AI provider request failed",
            )
        )


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
    if task.enable_thinking is not None:
        payload["enable_thinking"] = task.enable_thinking
    if task.reasoning_effort is not None:
        payload["reasoning_effort"] = task.reasoning_effort
    return payload


def _outcome_from_response(
    response: httpx.Response | None,
    *,
    task: AITaskConfig,
    started: float,
    log_fields: dict[str, str | None],
) -> _Outcome:
    if response is None:
        return _Outcome(
            failure=_Failure(
                kind="response",
                message="AI response is missing",
            )
        )

    try:
        raw_response = response.json()
    except ValueError:
        return _Outcome(
            failure=_Failure(
                kind="response",
                message="AI response is not a JSON object",
            )
        )
    if not isinstance(raw_response, dict):
        return _Outcome(
            failure=_Failure(
                kind="response",
                message="AI response is not a JSON object",
            )
        )

    try:
        content = ResponseParser.extract_content(raw_response)
    except AIResponseError as error:
        return _Outcome(
            failure=_Failure(kind="response", message=str(error))
        )

    latency_ms = _latency_ms(started)
    logger.info(
        "AI request completed",
        extra={**log_fields, "latency_ms": latency_ms},
    )
    return _Outcome(
        result=AIResult(
            content=content,
            provider=task.provider,
            model=task.model,
            latency_ms=latency_ms,
            raw_response=raw_response,
        )
    )


def _result_from_outcome(outcome: _Outcome | None) -> AIResult:
    if outcome is None:
        raise AIRequestError("AI provider request failed")
    if outcome.failure is not None:
        _raise_failure(outcome.failure)
    if outcome.result is None:
        raise AIResponseError("AI response is missing")
    return outcome.result


def _raise_failure(failure: _Failure) -> None:
    if failure.kind == "config":
        raise AIConfigError(failure.message)
    if failure.kind == "response":
        raise AIResponseError(failure.message)
    raise AIRequestError(failure.message)


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
    return hmac.new(
        _TRACE_HMAC_KEY,
        trace_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]
