"""Explicit, redacted smoke checks for configured AI providers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.question_probe import QuestionProbeComponent
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import (
    AIConfigError,
    AIPromptError,
    AIResponseError,
)
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError


_SUPPORTED_PROVIDERS = ("qwen", "deepseek")
_HTTP_FAILURE_PATTERN = re.compile(
    r"AI provider request failed with HTTP (?P<status>[1-5][0-9]{2})"
)


@dataclass(frozen=True)
class _SmokeSuccess:
    provider: str
    model: str
    latency_ms: int


@dataclass(frozen=True)
class _SmokeFailure:
    category: str
    returncode: int
    http_status: int | None = None


class _ResultRecorder:
    """Record safe response metadata while delegating to the shared client."""

    def __init__(self, delegate) -> None:
        self._delegate = delegate
        self.last_result: AIResult | None = None

    def complete(self, task_key: str, **kwargs) -> AIResult:
        result = self._delegate.complete(task_key, **kwargs)
        self.last_result = result
        return result

    def clear(self) -> None:
        self.last_result = None
        self._delegate = None


class Command(BaseCommand):
    help = "Run one explicitly authorized, redacted AI provider smoke check"

    ai_client_factory = staticmethod(AIClient)
    config_loader = staticmethod(load_ai_config)
    prompt_registry_factory = staticmethod(PromptRegistry)

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--provider",
            choices=_SUPPORTED_PROVIDERS,
            required=True,
        )
        parser.add_argument(
            "--live",
            action="store_true",
            help="Explicitly authorize one real provider request",
        )

    def handle(self, *args, **options) -> None:
        provider = options["provider"]
        if not options.get("live", False):
            raise CommandError(
                _failure_summary(
                    provider,
                    _SmokeFailure(category="live_required", returncode=1),
                ),
                returncode=1,
            )

        success: _SmokeSuccess | None = None
        failure: _SmokeFailure | None = None
        try:
            success = self._run_live(provider)
        except Exception as error:
            failure = _classify_failure(error)

        if failure is not None:
            raise CommandError(
                _failure_summary(provider, failure),
                returncode=failure.returncode,
            ) from None
        if success is None:
            raise CommandError(
                _failure_summary(
                    provider,
                    _SmokeFailure(category="unknown", returncode=6),
                ),
                returncode=6,
            )

        self.stdout.write(
            " ".join(
                (
                    f"provider={success.provider}",
                    f"model={success.model}",
                    "status=ok",
                    f"latency_ms={success.latency_ms}",
                    "schema=valid",
                )
            )
        )

    def _run_live(self, provider: str) -> _SmokeSuccess:
        task_key = ""
        config = None
        task = None
        client = None
        recorder = None
        registry = None
        question = None
        original: dict[str, str] | None = None
        candidate: dict[str, str] | None = None
        result: AIResult | None = None
        try:
            task_key = (
                "question_probe"
                if provider == "qwen"
                else "variant_verify_deepseek"
            )
            config = self.config_loader()
            task = config.get_task_config(task_key)
            registry = self.prompt_registry_factory(config)
            client = self.ai_client_factory()
            recorder = _ResultRecorder(client)

            if provider == "qwen":
                question = QuestionInput(
                    stem="计算 1+1 的结果。",
                    metadata={"ocr_confidence": "smoke"},
                )
                QuestionProbeComponent(recorder, registry).run(question)
            else:
                original = {"stem": "计算 1+1。", "answer": "2"}
                candidate = {"stem": "计算 2+1。", "answer": "3"}
                ResultVerifierComponent(recorder, registry).verify(
                    "variant_verify_deepseek",
                    original,
                    candidate,
                )

            result = recorder.last_result
            if (
                result is None
                or result.provider != provider
                or result.model != task.model
            ):
                raise AIResponseError(
                    "AI smoke response provider identity is invalid"
                )
            return _SmokeSuccess(
                provider=provider,
                model=task.model,
                latency_ms=result.latency_ms,
            )
        finally:
            had_active_error = sys.exc_info()[0] is not None
            result = None
            question = None
            if original is not None:
                original.clear()
            if candidate is not None:
                candidate.clear()
            original = None
            candidate = None
            registry = None
            if recorder is not None:
                recorder.clear()
            recorder = None
            task = None
            config = None
            task_key = ""
            client_to_close = client
            client = None
            close_succeeded = _close_client(client_to_close)
            client_to_close = None
            if not close_succeeded and not had_active_error:
                raise AIRequestError("AI provider request failed") from None


def _classify_failure(error: Exception) -> _SmokeFailure:
    if isinstance(error, (AIConfigError, AIPromptError)):
        return _SmokeFailure(category="configuration", returncode=2)
    if isinstance(error, AIResponseError):
        return _SmokeFailure(category="schema_response", returncode=5)
    if isinstance(error, AIRequestError):
        message = str(error)
        if message == "AI provider request timed out":
            return _SmokeFailure(category="transport_timeout", returncode=3)
        if message == "AI provider request failed":
            return _SmokeFailure(category="transport", returncode=3)
        match = _HTTP_FAILURE_PATTERN.fullmatch(message)
        if match is not None:
            return _SmokeFailure(
                category="http_status",
                returncode=4,
                http_status=int(match.group("status")),
            )
    return _SmokeFailure(category="unknown", returncode=6)


def _failure_summary(provider: str, failure: _SmokeFailure) -> str:
    fields = (
        f"provider={provider}",
        "status=error",
        f"category={failure.category}",
    )
    if failure.http_status is not None:
        fields += (f"http_status={failure.http_status}",)
    return " ".join(fields)


def _close_client(client) -> bool:
    if client is None:
        return True
    try:
        client.close()
    except Exception:
        return False
    return True
