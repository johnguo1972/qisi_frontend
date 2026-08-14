"""Explicit, redacted smoke checks for configured AI providers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.answer_verification import (
    DeepSeekFinalReviewComponent,
    DeepSeekIndependentVerifierComponent,
)
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
_TASK_PROVIDERS = {
    "question_probe": "qwen",
    "variant_verify_deepseek": "deepseek",
    "deepseek_independent_verify": "deepseek",
    "deepseek_final_review": "deepseek",
}
_SUPPORTED_TASKS = tuple(_TASK_PROVIDERS)
_DEFAULT_TASKS = {
    "qwen": "question_probe",
    "deepseek": "variant_verify_deepseek",
}
_HTTP_FAILURE_PATTERN = re.compile(
    r"AI provider request failed with HTTP (?P<status>[1-5][0-9]{2})"
)


@dataclass(frozen=True)
class _SmokeSuccess:
    provider: str
    model: str
    task: str
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
        parser.add_argument(
            "--task",
            choices=_SUPPORTED_TASKS,
            required=False,
            help="Run one fixed, provider-compatible smoke task",
        )

    def handle(self, *args, **options) -> None:
        provider = options["provider"]
        requested_task = options.get("task")
        if requested_task is not None and requested_task not in _TASK_PROVIDERS:
            raise CommandError(
                _failure_summary(
                    provider,
                    "invalid",
                    _SmokeFailure(category="task_not_allowed", returncode=1),
                ),
                returncode=1,
            )
        task_key = requested_task or _DEFAULT_TASKS[provider]
        if _TASK_PROVIDERS[task_key] != provider:
            raise CommandError(
                _failure_summary(
                    provider,
                    task_key,
                    _SmokeFailure(
                        category="provider_task_mismatch", returncode=1
                    ),
                ),
                returncode=1,
            )
        if not options.get("live", False):
            raise CommandError(
                _failure_summary(
                    provider,
                    task_key,
                    _SmokeFailure(category="live_required", returncode=1),
                ),
                returncode=1,
            )

        success: _SmokeSuccess | None = None
        failure: _SmokeFailure | None = None
        try:
            success = self._run_live(provider, task_key)
        except Exception as error:
            failure = _classify_failure(error)

        if failure is not None:
            raise CommandError(
                _failure_summary(provider, task_key, failure),
                returncode=failure.returncode,
            ) from None
        if success is None:
            raise CommandError(
                _failure_summary(
                    provider,
                    task_key,
                    _SmokeFailure(category="unknown", returncode=6),
                ),
                returncode=6,
            )

        self.stdout.write(
            " ".join(
                (
                    f"provider={success.provider}",
                    f"model={success.model}",
                    f"task={success.task}",
                    "status=ok",
                    f"latency_ms={success.latency_ms}",
                    "schema=valid",
                )
            )
        )

    def _run_live(self, provider: str, task_key: str | None = None) -> _SmokeSuccess:
        task_key = task_key or _DEFAULT_TASKS[provider]
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
            elif task_key == "variant_verify_deepseek":
                original = {"stem": "计算 1+1。", "answer": "2"}
                candidate = {"stem": "计算 2+1。", "answer": "3"}
                ResultVerifierComponent(recorder, registry).verify(
                    "variant_verify_deepseek",
                    original,
                    candidate,
                )
            else:
                question = _deepseek_question(task_key)
                component_type = (
                    DeepSeekIndependentVerifierComponent
                    if task_key == "deepseek_independent_verify"
                    else DeepSeekFinalReviewComponent
                )
                component_type(recorder, registry).run(question)

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
                task=task_key,
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


def _failure_summary(
    provider: str, task_key: str, failure: _SmokeFailure
) -> str:
    fields = (
        f"provider={provider}",
        f"task={task_key}",
        "status=error",
        f"category={failure.category}",
    )
    if failure.http_status is not None:
        fields += (f"http_status={failure.http_status}",)
    return " ".join(fields)


def _deepseek_question(task_key: str) -> QuestionInput:
    metadata: dict[str, object] = {
        "reference_analysis": "利用加法定义。",
        "question_type": "calculation",
        "subject": "math",
        "difficulty": "L1",
        "material": "",
        "tables": [],
        "subquestions": [],
        "normalized_text": "计算 1+1 的结果。",
        "vision_result": {"figure_present": False},
        "knowledge_refs": ["整数加法"],
        "target_mode": "A",
    }
    if task_key == "deepseek_final_review":
        metadata.update(
            {
                "qwen_result": {
                    "provider": "qwen",
                    "answer": "2",
                    "mode_content": {
                        "mode": "A",
                        "steps": [
                            {"step": 1, "content": "识别加法"},
                            {"step": 2, "content": "完成计算"},
                            {"step": 3, "content": "核对结果"},
                        ],
                        "final_answer": "2",
                        "summary": "计算完成",
                        "missing_conditions": [],
                    },
                },
                "independent_result": {
                    "provider": "deepseek",
                    "independent_answer": "2",
                    "independent_reasoning_summary": "一加一等于二。",
                    "key_facts": ["一加一等于二"],
                    "reference_answer_valid": False,
                    "reference_analysis_valid": True,
                    "reference_issues": ["参考答案不是规范数值答案"],
                    "confidence": 0.99,
                    "mode_content": {
                        "mode": "A",
                        "steps": [
                            {"step": 1, "content": "识别加法"},
                            {"step": 2, "content": "完成计算"},
                            {"step": 3, "content": "核对结果"},
                        ],
                        "final_answer": "2",
                        "summary": "计算完成",
                        "missing_conditions": [],
                    },
                },
                "conflicts": ["smoke_fixture_conflict"],
            }
        )
    return QuestionInput(
        stem="计算 1+1 的结果。",
        options=[
            {"label": "A", "content": "1"},
            {"label": "B", "content": "2"},
            {"label": "C", "content": "3"},
            {"label": "D", "content": "4"},
        ],
        answer="unique-reference-answer-must-not-leak",
        solution="把两个单位相加。",
        metadata=metadata,
    )


def _close_client(client) -> bool:
    if client is None:
        return True
    try:
        client.close()
    except Exception:
        return False
    return True
