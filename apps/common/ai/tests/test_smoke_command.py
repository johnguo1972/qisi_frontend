from __future__ import annotations

from io import StringIO
import json
from types import SimpleNamespace
import traceback

import pytest
from django.core.management.base import CommandError

from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError
from apps.common.management.commands.ai_smoke_test import Command


_SECRET = "sk-smoke-secret-must-not-leak"
_RAW_MARKER = "provider-raw-response-must-not-leak"


def _probe_payload() -> str:
    return json.dumps(
        {
            "subject": "math",
            "question_type": "calculation",
            "grade": "七年级",
            "semester": "上学期",
            "chapter": "第一章",
            "difficulty": "L1",
            "knowledge_points": ["有理数"],
            "multi_part": False,
            "proof_or_calc": "calc",
            "visual_risk_score": 0,
            "reasoning_risk_score": 5,
            "recommended_route": "STANDARD",
            "brief_reason": "最小分类样本",
            "normalized_text": "计算1+1",
        },
        ensure_ascii=False,
    )


def _deepseek_payload() -> str:
    return json.dumps(
        {
            "passed": True,
            "issues": [],
            "score": 1.0,
            "summary": "校验通过",
        },
        ensure_ascii=False,
    )


class FakeConfig:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.models = {
            "question_probe": "qwen3.7-flash",
            "variant_verify_deepseek": "deepseek-v4-pro",
        }

    def get_task_config(self, task_key: str):
        self.calls.append(task_key)
        return SimpleNamespace(model=self.models[task_key])


class RecordingRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def render(self, task_key: str, **variables: object):
        self.calls.append((task_key, variables))
        return f"system:{task_key}", f"user:{task_key}"


class RecordingClient:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        provider_override: str | None = None,
        model_override: str | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.error = error
        self.provider_override = provider_override
        self.model_override = model_override
        self.close_error = close_error
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def complete(self, task_key: str, **kwargs: object) -> AIResult:
        self.calls.append((task_key, kwargs))
        if self.error is not None:
            raise self.error
        if task_key == "question_probe":
            content = _probe_payload()
            provider = "qwen"
            model = "qwen3.7-flash"
        else:
            content = _deepseek_payload()
            provider = "deepseek"
            model = "deepseek-v4-pro"
        return AIResult(
            content=content,
            provider=self.provider_override or provider,
            model=self.model_override or model,
            latency_ms=17,
            raw_response={"marker": _RAW_MARKER},
        )

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _command(
    *,
    client: RecordingClient | None = None,
    config: FakeConfig | None = None,
    registry: RecordingRegistry | None = None,
):
    output = StringIO()
    command = Command(stdout=output, stderr=StringIO())
    created_clients: list[RecordingClient] = []
    loaded_configs: list[FakeConfig] = []
    client = client or RecordingClient()
    config = config or FakeConfig()
    registry = registry or RecordingRegistry()

    def client_factory():
        created_clients.append(client)
        return client

    def config_loader():
        loaded_configs.append(config)
        return config

    command.ai_client_factory = client_factory
    command.config_loader = config_loader
    command.prompt_registry_factory = lambda _config: registry
    return command, output, client, config, registry, created_clients, loaded_configs


def _fields(output: StringIO) -> dict[str, str]:
    return dict(token.split("=", 1) for token in output.getvalue().split())


def test_without_live_refuses_before_loading_config_or_constructing_client():
    command, output, client, _, _, created_clients, loaded_configs = _command()

    with pytest.raises(CommandError) as caught:
        command.handle(provider="qwen", live=False)

    assert caught.value.returncode == 1
    assert str(caught.value) == (
        "provider=qwen status=error category=live_required"
    )
    assert output.getvalue() == ""
    assert created_clients == []
    assert loaded_configs == []
    assert client.calls == []


def test_qwen_live_uses_shared_probe_task_with_minimal_text_and_no_image():
    command, output, client, config, registry, _, _ = _command()

    command.handle(provider="qwen", live=True)

    assert config.calls == ["question_probe"]
    assert [call[0] for call in client.calls] == ["question_probe"]
    assert client.calls[0][1]["images"] == ()
    assert registry.calls[0][0] == "question_probe"
    assert registry.calls[0][1] == {
        "ocr_text": "计算 1+1 的结果。",
        "has_figure": False,
        "ocr_confidence": "smoke",
    }
    assert client.closed is True
    assert _fields(output) == {
        "provider": "qwen",
        "model": "qwen3.7-flash",
        "status": "ok",
        "latency_ms": "17",
        "schema": "valid",
    }


def test_deepseek_live_uses_shared_variant_verifier_task_only():
    command, output, client, config, registry, _, _ = _command()

    command.handle(provider="deepseek", live=True)

    assert config.calls == ["variant_verify_deepseek"]
    assert [call[0] for call in client.calls] == [
        "variant_verify_deepseek"
    ]
    assert registry.calls[0][0] == "variant_verify_deepseek"
    variables = registry.calls[0][1]
    assert json.loads(variables["original_question_context"]) == {
        "stem": "计算 1+1。",
        "answer": "2",
    }
    assert json.loads(variables["variant_json"]) == {
        "stem": "计算 2+1。",
        "answer": "3",
    }
    assert client.closed is True
    assert _fields(output) == {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "status": "ok",
        "latency_ms": "17",
        "schema": "valid",
    }


def test_success_summary_has_only_allowlisted_fields_and_no_payload_data():
    command, output, _, _, _, _, _ = _command()

    command.handle(provider="qwen", live=True)

    rendered = output.getvalue()
    assert set(_fields(output)) == {
        "provider",
        "model",
        "status",
        "latency_ms",
        "schema",
    }
    for forbidden in (
        _SECRET,
        _RAW_MARKER,
        "system:question_probe",
        "user:question_probe",
        "计算 1+1",
        "https://",
    ):
        assert forbidden not in rendered


@pytest.mark.parametrize(
    ("error", "category", "returncode", "extra_field"),
    [
        (
            AIRequestError("AI provider request timed out"),
            "transport_timeout",
            3,
            None,
        ),
        (
            AIRequestError("AI provider request failed"),
            "transport",
            3,
            None,
        ),
        (
            AIRequestError("AI provider request failed with HTTP 503"),
            "http_status",
            4,
            ("http_status", "503"),
        ),
        (
            AIResponseError(f"schema failed {_RAW_MARKER}"),
            "schema_response",
            5,
            None,
        ),
        (RuntimeError(_SECRET), "unknown", 6, None),
    ],
)
def test_failures_use_safe_categories_and_distinct_exit_codes(
    error, category, returncode, extra_field
):
    command, output, client, _, _, _, _ = _command(
        client=RecordingClient(error=error)
    )

    with pytest.raises(CommandError) as caught:
        command.handle(provider="qwen", live=True)

    assert caught.value.returncode == returncode
    fields = dict(
        token.split("=", 1) for token in str(caught.value).split()
    )
    assert fields == {
        "provider": "qwen",
        "status": "error",
        "category": category,
        **({extra_field[0]: extra_field[1]} if extra_field else {}),
    }
    assert output.getvalue() == ""
    assert client.closed is True
    assert _SECRET not in str(caught.value)
    assert _RAW_MARKER not in str(caught.value)


def test_configuration_failure_is_safe_and_does_not_construct_client():
    command, _, _, _, _, created_clients, _ = _command()

    def failing_config_loader():
        raise AIConfigError(f"bad config {_SECRET}")

    command.config_loader = failing_config_loader

    with pytest.raises(CommandError) as caught:
        command.handle(provider="deepseek", live=True)

    assert caught.value.returncode == 2
    assert str(caught.value) == (
        "provider=deepseek status=error category=configuration"
    )
    assert created_clients == []
    assert _SECRET not in str(caught.value)


def test_provider_returned_model_must_match_configured_model():
    client = RecordingClient(
        model_override="unexpected-provider-model"
    )
    command, output, client, _, _, _, _ = _command(client=client)

    with pytest.raises(CommandError) as caught:
        command.handle(provider="qwen", live=True)

    assert caught.value.returncode == 5
    assert str(caught.value) == (
        "provider=qwen status=error category=schema_response"
    )
    assert output.getvalue() == ""
    assert client.closed is True


def test_identity_failure_traceback_does_not_retain_ai_result_payload():
    client = RecordingClient(provider_override="deepseek")
    command, _, _, _, _, _, _ = _command(client=client)

    with pytest.raises(AIResponseError) as caught:
        command._run_live("qwen")

    rendered = "".join(
        traceback.TracebackException.from_exception(
            caught.value, capture_locals=True
        ).format()
    )
    assert _RAW_MARKER not in rendered
    assert client.closed is True


def test_close_failure_is_replaced_after_sensitive_locals_are_cleared():
    client = RecordingClient(
        close_error=RuntimeError(f"{_SECRET} {_RAW_MARKER}")
    )
    command, _, _, _, _, _, _ = _command(client=client)

    with pytest.raises(AIRequestError) as caught:
        command._run_live("deepseek")

    rendered = "".join(
        traceback.TracebackException.from_exception(
            caught.value, capture_locals=True
        ).format()
    )
    assert str(caught.value) == "AI provider request failed"
    assert _SECRET not in rendered
    assert _RAW_MARKER not in rendered
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_failure_traceback_locals_and_exception_chain_do_not_retain_secret():
    command, _, _, _, _, _, _ = _command(
        client=RecordingClient(error=RuntimeError(_SECRET))
    )

    with pytest.raises(CommandError) as caught:
        command.handle(provider="qwen", live=True)

    rendered = "".join(
        traceback.TracebackException.from_exception(
            caught.value, capture_locals=True
        ).format()
    )
    assert _SECRET not in rendered
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_provider_argument_choices_are_exactly_qwen_and_deepseek():
    parser = Command().create_parser("manage.py", "ai_smoke_test")
    provider_action = next(
        action for action in parser._actions if action.dest == "provider"
    )

    assert tuple(provider_action.choices) == ("qwen", "deepseek")
    assert provider_action.required is True
