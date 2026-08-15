from __future__ import annotations

from io import StringIO
import json
from types import SimpleNamespace
import traceback
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError
from apps.common.management.commands.ai_smoke_test import Command


_SECRET = "sk-smoke-secret-must-not-leak"
_RAW_MARKER = "provider-raw-response-must-not-leak"
_PROMPT_MARKER = "unique-smoke-prompt-must-not-leak"
_REFERENCE_MARKER = "unique-reference-answer-must-not-leak"


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


def _independent_payload() -> str:
    return json.dumps(
        {
            "independent_answer": "2",
            "independent_reasoning_summary": "一加一等于二。",
            "key_facts": ["加法恒等关系成立"],
            "reference_answer_valid": True,
            "reference_analysis_valid": True,
            "reference_issues": [],
            "confidence": 0.99,
            "mode_content": {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "识别加法"},
                    {"step": 2, "content": "相加"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "计算完成",
                "missing_conditions": [],
            },
        },
        ensure_ascii=False,
    )


def _final_review_payload() -> str:
    return json.dumps(
        {
            "trusted_answer": "2",
            "qwen_content_valid": True,
            "candidate_issues": [],
            "confidence": 0.99,
            "mode_content": {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "识别加法"},
                    {"step": 2, "content": "相加"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "summary": "计算完成",
                "missing_conditions": [],
            },
        },
        ensure_ascii=False,
    )


def _deepseek_payload_with_mode_content(
    task_key: str, mode_content: dict[str, object]
) -> str:
    payload = json.loads(
        _independent_payload()
        if task_key == "deepseek_independent_verify"
        else _final_review_payload()
    )
    payload["mode_content"] = mode_content
    if task_key == "deepseek_independent_verify":
        payload["independent_reasoning_summary"] = _RAW_MARKER
    else:
        payload["candidate_issues"] = [_RAW_MARKER]
    return json.dumps(payload, ensure_ascii=False)


class FakeConfig:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.models = {
            "question_probe": "qwen3.7-flash",
            "variant_verify_deepseek": "deepseek-v4-pro",
            "deepseek_independent_verify": "deepseek-v4-pro",
            "deepseek_final_review": "deepseek-v4-pro",
        }

    def get_task_config(self, task_key: str):
        self.calls.append(task_key)
        return SimpleNamespace(model=self.models[task_key])


class RecordingRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def render(self, task_key: str, **variables: object):
        self.calls.append((task_key, variables))
        return (
            f"system:{task_key}:{_PROMPT_MARKER}",
            f"user:{task_key}:{_PROMPT_MARKER}",
        )


class RecordingClient:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        provider_override: str | None = None,
        model_override: str | None = None,
        close_error: Exception | None = None,
        content_overrides: dict[str, str] | None = None,
    ) -> None:
        self.error = error
        self.provider_override = provider_override
        self.model_override = model_override
        self.close_error = close_error
        self.content_overrides = content_overrides or {}
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    def complete(self, task_key: str, **kwargs: object) -> AIResult:
        self.calls.append((task_key, kwargs))
        if self.error is not None:
            raise self.error
        if task_key in self.content_overrides:
            content = self.content_overrides[task_key]
            provider = "deepseek"
            model = "deepseek-v4-pro"
        elif task_key == "question_probe":
            content = _probe_payload()
            provider = "qwen"
            model = "qwen3.7-flash"
        elif task_key == "deepseek_independent_verify":
            content = _independent_payload()
            provider = "deepseek"
            model = "deepseek-v4-pro"
        elif task_key == "deepseek_final_review":
            content = _final_review_payload()
            provider = "deepseek"
            model = "deepseek-v4-pro"
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
        "provider=qwen task=question_probe status=error category=live_required"
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
        "task": "question_probe",
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
        "task": "variant_verify_deepseek",
        "status": "ok",
        "latency_ms": "17",
        "schema": "valid",
    }


def test_deepseek_independent_task_uses_exact_config_route_and_safe_fixture():
    """Catch accidental routing to a fallback task or incomplete prompt data."""
    command, output, client, config, registry, _, _ = _command()

    command.handle(
        provider="deepseek",
        task="deepseek_independent_verify",
        live=True,
    )

    assert config.calls == ["deepseek_independent_verify"]
    assert [call[0] for call in client.calls] == [
        "deepseek_independent_verify"
    ]
    assert registry.calls[0][0] == "deepseek_independent_verify"
    variables = registry.calls[0][1]
    assert set(variables) == {
        "question_context_json",
        "target_mode",
        "mode_schema_json",
    }
    assert variables["target_mode"] == "A"
    context = json.loads(variables["question_context_json"])
    assert context == {
        "stem": "计算 1+1 的结果。",
        "options": [
            {"label": "A", "content": "1"},
            {"label": "B", "content": "2"},
            {"label": "C", "content": "3"},
            {"label": "D", "content": "4"},
        ],
        "reference_answer": _REFERENCE_MARKER,
        "reference_analysis": "利用加法定义。",
        "reference_solution": "把两个单位相加。",
        "question_type": "calculation",
        "subject": "math",
        "difficulty": "L1",
        "material": "",
        "tables": [],
        "subquestions": [],
        "image_urls": [],
        "normalized_text": "计算 1+1 的结果。",
        "vision_result": {"figure_present": False},
        "knowledge_refs": ["整数加法"],
    }
    mode_schema = json.loads(variables["mode_schema_json"])
    assert mode_schema["required"] == [
        "mode",
        "steps",
        "final_answer",
        "summary",
    ]
    assert client.closed is True
    assert _fields(output) == {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "task": "deepseek_independent_verify",
        "status": "ok",
        "latency_ms": "17",
        "schema": "valid",
    }


def test_deepseek_final_review_task_is_supported_with_anonymous_candidates():
    """Catch a missing final-review route or candidate-source disclosure."""
    command, output, client, config, registry, _, _ = _command()

    command.handle(
        provider="deepseek",
        task="deepseek_final_review",
        live=True,
    )

    assert config.calls == ["deepseek_final_review"]
    assert [call[0] for call in client.calls] == ["deepseek_final_review"]
    variables = registry.calls[0][1]
    qwen_candidate = json.loads(variables["qwen_result_json"])
    independent_candidate = json.loads(
        variables["independent_result_json"]
    )
    assert qwen_candidate["candidate"] == "candidate A"
    assert qwen_candidate["content"]["mode_content"]["steps"] == [
        {"step": 1, "content": "识别加法"},
        {"step": 2, "content": "完成计算"},
        {"step": 3, "content": "核对结果"},
    ]
    assert independent_candidate["candidate"] == "candidate B"
    assert independent_candidate["content"]["key_facts"] == [
        "一加一等于二"
    ]
    assert independent_candidate["content"]["mode_content"]["summary"] == (
        "计算完成"
    )
    assert "provider" not in variables["qwen_result_json"].lower()
    assert "qwen" not in variables["qwen_result_json"].lower()
    assert _fields(output)["task"] == "deepseek_final_review"


@pytest.mark.parametrize(
    ("task_key", "mode_content"),
    [
        pytest.param(
            "deepseek_independent_verify",
            {},
            id="independent-empty-mode-content",
        ),
        pytest.param(
            "deepseek_independent_verify",
            {
                "mode": "B",
                "questions": [],
                "final_answer": "2",
                "summary": "错误模式",
            },
            id="independent-wrong-mode-shape",
        ),
        pytest.param(
            "deepseek_final_review",
            {},
            id="final-review-empty-mode-content",
        ),
        pytest.param(
            "deepseek_final_review",
            {
                "mode": "C",
                "questions": [],
                "final_answer": "2",
                "summary": "错误模式",
            },
            id="final-review-wrong-mode-shape",
        ),
        pytest.param(
            "deepseek_final_review",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "识别加法"},
                    {"step": 2, "content": "相加"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "3",
                "summary": "冲突答案",
                "missing_conditions": [],
            },
            id="final-review-answer-conflict",
        ),
        pytest.param(
            "deepseek_final_review",
            {
                "mode": "A",
                "steps": [
                    {"step": 1, "content": "识别加法"},
                    {"step": 2, "content": "相加"},
                    {"step": 3, "content": "验算"},
                ],
                "final_answer": "2",
                "missing_conditions": [],
            },
            id="final-review-missing-public-field",
        ),
    ],
)
def test_deepseek_tasks_require_valid_nested_public_mode_content(
    task_key, mode_content
):
    """Catch top-level-only validation being reported as schema valid."""
    client = RecordingClient(
        content_overrides={
            task_key: _deepseek_payload_with_mode_content(
                task_key, mode_content
            )
        }
    )
    command, output, client, _, _, _, _ = _command(client=client)

    with pytest.raises(CommandError) as caught:
        command.handle(provider="deepseek", task=task_key, live=True)

    assert caught.value.returncode == 5
    assert str(caught.value) == (
        f"provider=deepseek task={task_key} "
        "status=error category=schema_response"
    )
    assert output.getvalue() == ""
    assert client.closed is True
    assert _RAW_MARKER not in str(caught.value)


def test_arbitrary_task_is_rejected_before_config_or_client_access():
    """Catch a direct-handle bypass around argparse's fixed allowlist."""
    command, output, client, _, _, created_clients, loaded_configs = _command()

    with pytest.raises(CommandError) as caught:
        command.handle(provider="qwen", task="mode_a_answer", live=True)

    assert caught.value.returncode == 1
    assert str(caught.value) == (
        "provider=qwen task=invalid status=error category=task_not_allowed"
    )
    assert output.getvalue() == ""
    assert loaded_configs == []
    assert created_clients == []
    assert client.calls == []


def test_real_command_parser_redacts_arbitrary_task_before_setup():
    """Catch argparse echoing an attacker-controlled task before handle()."""
    marker = "unique-illegal-task-secret-must-not-leak"
    stdout = StringIO()
    stderr = StringIO()
    setup_calls: list[str] = []

    def forbidden_config_loader():
        setup_calls.append("config")
        raise AssertionError("config must not be loaded")

    def forbidden_client_factory():
        setup_calls.append("client")
        raise AssertionError("client must not be constructed")

    with (
        patch.object(
            Command,
            "config_loader",
            staticmethod(forbidden_config_loader),
        ),
        patch.object(
            Command,
            "ai_client_factory",
            staticmethod(forbidden_client_factory),
        ),
        pytest.raises(CommandError) as caught,
    ):
        call_command(
            "ai_smoke_test",
            "--provider",
            "qwen",
            "--task",
            marker,
            "--live",
            stdout=stdout,
            stderr=stderr,
        )

    assert caught.value.returncode == 1
    assert str(caught.value) == (
        "provider=qwen task=invalid status=error category=task_not_allowed"
    )
    rendered = stdout.getvalue() + stderr.getvalue() + str(caught.value)
    assert marker not in rendered
    assert setup_calls == []


def test_provider_task_mismatch_is_rejected_before_any_http_setup():
    """Catch provider spoofing before config load or client construction."""
    command, output, client, _, _, created_clients, loaded_configs = _command()

    with pytest.raises(CommandError) as caught:
        command.handle(
            provider="qwen",
            task="deepseek_independent_verify",
            live=True,
        )

    assert caught.value.returncode == 1
    assert str(caught.value) == (
        "provider=qwen task=deepseek_independent_verify "
        "status=error category=provider_task_mismatch"
    )
    assert output.getvalue() == ""
    assert loaded_configs == []
    assert created_clients == []
    assert client.calls == []


def test_success_summary_has_only_allowlisted_fields_and_no_payload_data():
    command, output, _, _, _, _, _ = _command()

    command.handle(provider="qwen", live=True)

    rendered = output.getvalue()
    assert set(_fields(output)) == {
        "provider",
        "model",
        "task",
        "status",
        "latency_ms",
        "schema",
    }
    for forbidden in (
        _SECRET,
        _RAW_MARKER,
        _REFERENCE_MARKER,
        _PROMPT_MARKER,
        "计算 1+1",
        "https://",
    ):
        assert forbidden not in rendered


def test_deepseek_failure_summary_excludes_prompt_reference_and_raw_markers():
    """Catch exception text leaking any live verification fixture/provider data."""
    client = RecordingClient(
        error=AIResponseError(
            f"{_PROMPT_MARKER} {_REFERENCE_MARKER} {_RAW_MARKER} {_SECRET}"
        )
    )
    command, output, client, _, _, _, _ = _command(client=client)

    with pytest.raises(CommandError) as caught:
        command.handle(
            provider="deepseek",
            task="deepseek_independent_verify",
            live=True,
        )

    assert caught.value.returncode == 5
    assert str(caught.value) == (
        "provider=deepseek task=deepseek_independent_verify "
        "status=error category=schema_response"
    )
    assert output.getvalue() == ""
    assert client.closed is True
    for forbidden in (
        _PROMPT_MARKER,
        _REFERENCE_MARKER,
        _RAW_MARKER,
        _SECRET,
    ):
        assert forbidden not in str(caught.value)


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
        "task": "question_probe",
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
        "provider=deepseek task=variant_verify_deepseek "
        "status=error category=configuration"
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
        "provider=qwen task=question_probe "
        "status=error category=schema_response"
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


def test_task_argument_defers_safe_allowlist_to_handle_and_remains_optional():
    """Catch parser-level choices that echo an untrusted task value."""
    parser = Command().create_parser("manage.py", "ai_smoke_test")
    task_action = next(
        action for action in parser._actions if action.dest == "task"
    )

    assert task_action.choices is None
    assert task_action.required is False
