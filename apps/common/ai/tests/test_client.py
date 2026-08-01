from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Callable

import httpx
import pytest

import apps.common.ai.client as client_module
from apps.common.ai.client import AIClient
from apps.common.ai.config import AIConfig, AIProviderConfig, AITaskConfig
from apps.common.ai.exceptions import AIResponseError
from apps.common.exceptions import AIRequestError


TEST_SECRET = "test-secret"
TEST_DATA_IMAGE = "data:image/png;base64," + "QUJDREVGR0hJSktMTU5PUA==" * 4


def _config(
    *,
    task_key: str = "question_probe",
    provider: str = "qwen",
    model: str = "qwen3.7-flash",
    response_format: str | None = None,
    retry_count: int = 0,
    retry_backoff_seconds: tuple[float, ...] = (),
) -> AIConfig:
    task = AITaskConfig(
        key=task_key,
        provider=provider,
        model=model,
        prompt="unused-by-client",
        prompt_key=task_key,
        temperature=0.25,
        max_tokens=321,
        timeout_seconds=300.0,
        retry_count=retry_count,
        retry_backoff_seconds=retry_backoff_seconds,
        response_format=response_format,
    )
    provider_config = AIProviderConfig(
        name=provider,
        api_url=f"https://example.test/{provider}/chat/completions",
        api_key=TEST_SECRET,
    )
    return AIConfig(
        providers={provider: provider_config},
        tasks={task_key: task},
        prompts={},
    )


def _client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    config: AIConfig | None = None,
    sleeper: Callable[[float], None] = lambda _seconds: None,
) -> AIClient:
    monkeypatch.setattr(
        client_module,
        "load_ai_config",
        lambda: config or _config(),
    )
    return AIClient(transport=httpx.MockTransport(handler), sleeper=sleeper)


def _success_response(request: httpx.Request, content: str = "ok") -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        json={
            "id": "chatcmpl-test",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def test_complete_sends_text_payload_from_cached_config(monkeypatch):
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["payload"] = json.loads(request.content)
        seen["timeout"] = request.extensions["timeout"]
        return _success_response(request, "text answer")

    result = _client(monkeypatch, handler).complete(
        "question_probe", system="system prompt", user="user prompt"
    )

    assert seen == {
        "url": "https://example.test/qwen/chat/completions",
        "authorization": "Bearer test-secret",
        "payload": {
            "model": "qwen3.7-flash",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
            "temperature": 0.25,
            "max_tokens": 321,
        },
        "timeout": {
            "connect": 300.0,
            "read": 300.0,
            "write": 300.0,
            "pool": 300.0,
        },
    }
    assert result.content == "text answer"
    assert result.provider == "qwen"
    assert result.model == "qwen3.7-flash"
    assert result.latency_ms >= 0
    assert result.raw_response["id"] == "chatcmpl-test"


def test_complete_sends_openai_multimodal_image_url_payload(monkeypatch):
    seen_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content))
        return _success_response(request)

    _client(monkeypatch, handler).complete(
        "question_probe",
        system="vision system",
        user="inspect images",
        images=("https://example.test/one.png", TEST_DATA_IMAGE),
    )

    assert seen_payload["messages"] == [
        {"role": "system", "content": "vision system"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "inspect images"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.test/one.png"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": TEST_DATA_IMAGE},
                },
            ],
        },
    ]


@pytest.mark.parametrize("configured_format", ["json", "json_object"])
def test_complete_sends_json_object_response_format(
    monkeypatch, configured_format
):
    seen_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payload.update(json.loads(request.content))
        return _success_response(request, "{}")

    _client(
        monkeypatch,
        handler,
        config=_config(response_format=configured_format),
    ).complete("question_probe", system="system", user="user")

    assert seen_payload["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_complete_retries_retryable_http_statuses_with_configured_backoff(
    monkeypatch, status_code
):
    attempts: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            return httpx.Response(status_code, request=request, text="private-body")
        return _success_response(request)

    result = _client(
        monkeypatch,
        handler,
        config=_config(
            retry_count=2,
            retry_backoff_seconds=(0.125, 0.25),
        ),
        sleeper=sleeps.append,
    ).complete("question_probe", system="system", user="user")

    assert result.content == "ok"
    assert attempts == [1, 2, 3]
    assert sleeps == [0.125, 0.25]


@pytest.mark.parametrize("error_type", [httpx.ConnectTimeout, httpx.ReadTimeout])
def test_complete_retries_connection_and_read_timeouts(monkeypatch, error_type):
    attempts: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise error_type("transport details", request=request)
        return _success_response(request)

    result = _client(
        monkeypatch,
        handler,
        config=_config(retry_count=1, retry_backoff_seconds=(0.5,)),
        sleeper=sleeps.append,
    ).complete("question_probe", system="system", user="user")

    assert result.content == "ok"
    assert attempts == [1, 2]
    assert sleeps == [0.5]


@pytest.mark.parametrize("status_code", [401, 403])
def test_complete_does_not_retry_authentication_failures(monkeypatch, status_code):
    attempts: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(len(attempts) + 1)
        return httpx.Response(status_code, request=request, text="private-body")

    client = _client(
        monkeypatch,
        handler,
        config=_config(retry_count=3, retry_backoff_seconds=(1.0, 2.0, 4.0)),
        sleeper=sleeps.append,
    )

    with pytest.raises(AIRequestError, match=str(status_code)):
        client.complete("question_probe", system="system", user="user")

    assert attempts == [1]
    assert sleeps == []


def test_complete_raises_response_error_for_empty_choices(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={"choices": []})

    client = _client(monkeypatch, handler)

    with pytest.raises(AIResponseError, match="content"):
        client.complete("question_probe", system="system", user="user")


def test_complete_supports_injected_httpx_client(monkeypatch):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    transport = httpx.MockTransport(_success_response)

    with httpx.Client(transport=transport) as http_client:
        client = AIClient(client=http_client, sleeper=lambda _seconds: None)
        result = client.complete(
            "question_probe", system="system", user="user"
        )
        follow_up = http_client.get("https://example.test/health")

    assert result.content == "ok"
    assert follow_up.status_code == 200


def test_logs_and_exceptions_redact_secret_image_and_transport_details(
    monkeypatch, caplog
):
    transport_secret = "transport-private-detail"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            f"{transport_secret} {TEST_SECRET} {TEST_DATA_IMAGE}",
            request=request,
        )

    client = _client(monkeypatch, handler)
    caplog.set_level(logging.INFO, logger="apps.common.ai.client")

    with pytest.raises(AIRequestError) as caught:
        client.complete(
            "question_probe",
            system="system",
            user="user",
            images=(TEST_DATA_IMAGE,),
            trace_id=f"trace {TEST_SECRET} {TEST_DATA_IMAGE}",
        )

    error_text = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    combined = caplog.text + error_text
    for sensitive in (TEST_SECRET, TEST_DATA_IMAGE, transport_secret):
        assert sensitive not in combined
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_deepseek_request_uses_its_configured_model_url_key_and_300s_timeout(
    monkeypatch,
):
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["payload"] = json.loads(request.content)
        seen["timeout"] = request.extensions["timeout"]
        return _success_response(request)

    config = _config(
        task_key="variant_verify_deepseek",
        provider="deepseek",
        model="deepseek-v4-pro",
    )
    result = _client(monkeypatch, handler, config=config).complete(
        "variant_verify_deepseek", system="verify", user="candidate"
    )

    assert seen["url"] == "https://example.test/deepseek/chat/completions"
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"]["model"] == "deepseek-v4-pro"
    assert seen["timeout"] == {
        "connect": 300.0,
        "read": 300.0,
        "write": 300.0,
        "pool": 300.0,
    }
    assert result.provider == "deepseek"


def test_rejects_ambiguous_client_and_transport_injection(monkeypatch):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    transport = httpx.MockTransport(_success_response)

    with httpx.Client(transport=transport) as http_client:
        with pytest.raises(ValueError, match="client.*transport"):
            AIClient(client=http_client, transport=transport)
