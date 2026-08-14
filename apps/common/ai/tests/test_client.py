from __future__ import annotations

import json
import logging
import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

import apps.common.ai.client as client_module
from apps.common.ai.client import AIClient
from apps.common.ai.config import (
    AIConfig,
    AIProviderConfig,
    AITaskConfig,
    reset_ai_config_for_tests,
)
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError


TEST_SECRET = "test-secret"
TEST_DATA_IMAGE = "data:image/png;base64," + "QUJDREVGR0hJSktMTU5PUA==" * 4
TRACE_SYSTEM = "system-private-marker"
TRACE_USER = "user-private-marker"
TRACE_RAW_RESPONSE = "raw-response-private-marker"
TRACE_NETWORK_DETAIL = "network-private-marker"


class TrackingTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.closed:
            raise RuntimeError("borrowed transport was closed")
        return _success_response(request)

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class ConcurrentTrackingTransport(TrackingTransport):
    def __init__(self) -> None:
        super().__init__()
        self.first_started = threading.Event()
        self.second_started = threading.Event()
        self.release_second = threading.Event()
        self.close_while_active = False
        self._active = 0
        self._lock = threading.Lock()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.closed:
            raise RuntimeError("borrowed transport was closed")
        user = json.loads(request.content)["messages"][1]["content"]
        with self._lock:
            self._active += 1
        try:
            if user == "first":
                self.first_started.set()
                assert self.second_started.wait(2)
            else:
                self.second_started.set()
                assert self.release_second.wait(2)
            return _success_response(request, user)
        finally:
            with self._lock:
                self._active -= 1

    def close(self) -> None:
        with self._lock:
            if self._active:
                self.close_while_active = True
        super().close()


def _config(
    *,
    task_key: str = "question_probe",
    provider: str = "qwen",
    model: str = "qwen3.7-flash",
    response_format: str | None = None,
    enable_thinking: bool | None = None,
    reasoning_effort: str | None = None,
    retry_count: int = 0,
    retry_backoff_seconds: tuple[float, ...] = (),
    api_key: str = TEST_SECRET,
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
        enable_thinking=enable_thinking,
        reasoning_effort=reasoning_effort,
    )
    provider_config = AIProviderConfig(
        name=provider,
        api_url=f"https://example.test/{provider}/chat/completions",
        api_key=api_key,
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


def _traceback_with_locals(error: BaseException) -> str:
    return "".join(
        traceback.TracebackException(
            type(error),
            error,
            error.__traceback__,
            capture_locals=True,
        ).format()
    )


def _assert_no_private_traceback_values(error: BaseException) -> None:
    formatted = _traceback_with_locals(error)
    for sensitive in (
        TEST_SECRET,
        TRACE_SYSTEM,
        TRACE_USER,
        TEST_DATA_IMAGE,
        TRACE_RAW_RESPONSE,
        TRACE_NETWORK_DETAIL,
    ):
        assert sensitive not in formatted


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
    assert "enable_thinking" not in seen["payload"]
    assert "reasoning_effort" not in seen["payload"]


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
        with AIClient(
            client=http_client, sleeper=lambda _seconds: None
        ) as client:
            result = client.complete(
                "question_probe", system="system", user="user"
            )
        follow_up = http_client.get("https://example.test/health")

    assert result.content == "ok"
    assert follow_up.status_code == 200


def test_borrowed_transport_supports_repeated_calls_and_is_not_closed(
    monkeypatch,
):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    transport = TrackingTransport()
    client = AIClient(transport=transport, sleeper=lambda _seconds: None)

    first = client.complete("question_probe", system="system", user="first")
    second = client.complete("question_probe", system="system", user="second")
    client.close()

    assert (first.content, second.content) == ("ok", "ok")
    assert transport.close_calls == 0
    assert not transport.closed


def test_borrowed_transport_is_not_closed_during_concurrent_calls(monkeypatch):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    transport = ConcurrentTrackingTransport()
    client = AIClient(transport=transport, sleeper=lambda _seconds: None)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            client.complete,
            "question_probe",
            system="system",
            user="first",
        )
        assert transport.first_started.wait(2)
        second_future = executor.submit(
            client.complete,
            "question_probe",
            system="system",
            user="second",
        )
        assert transport.second_started.wait(2)
        first = first_future.result(timeout=2)
        transport.release_second.set()
        second = second_future.result(timeout=2)

    third = client.complete("question_probe", system="system", user="third")
    client.close()

    assert (first.content, second.content, third.content) == (
        "first",
        "second",
        "third",
    )
    assert transport.close_calls == 0
    assert not transport.close_while_active


def test_injected_client_defaults_cannot_modify_configured_request(monkeypatch):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["timeout"] = request.extensions["timeout"]
        return _success_response(request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(
        transport=transport,
        auth=httpx.BasicAuth("default-user", "default-auth-secret"),
        params={"default-param": "default-param-secret"},
        cookies={"session": "default-cookie-secret"},
        headers={"X-Default": "default-header-secret"},
        timeout=1.0,
    ) as http_client:
        AIClient(client=http_client).complete(
            "question_probe", system="system", user="user"
        )

    assert seen["url"] == "https://example.test/qwen/chat/completions"
    headers = seen["headers"]
    assert headers["authorization"] == "Bearer test-secret"
    assert "cookie" not in headers
    assert "x-default" not in headers
    assert seen["timeout"] == {
        "connect": 300.0,
        "read": 300.0,
        "write": 300.0,
        "pool": 300.0,
    }


def test_401_traceback_locals_do_not_expose_request_or_response_data(
    monkeypatch,
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, text=TRACE_RAW_RESPONSE)

    client = _client(monkeypatch, handler)

    with pytest.raises(AIRequestError) as caught:
        client.complete(
            "question_probe",
            system=TRACE_SYSTEM,
            user=TRACE_USER,
            images=(TEST_DATA_IMAGE,),
        )

    _assert_no_private_traceback_values(caught.value)


def test_read_timeout_traceback_locals_do_not_expose_network_data(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            TRACE_NETWORK_DETAIL,
            request=request,
        )

    client = _client(monkeypatch, handler)

    with pytest.raises(AIRequestError) as caught:
        client.complete(
            "question_probe",
            system=TRACE_SYSTEM,
            user=TRACE_USER,
            images=(TEST_DATA_IMAGE,),
        )

    _assert_no_private_traceback_values(caught.value)


def test_non_json_traceback_locals_do_not_expose_raw_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, text=TRACE_RAW_RESPONSE)

    client = _client(monkeypatch, handler)

    with pytest.raises(AIResponseError) as caught:
        client.complete(
            "question_probe",
            system=TRACE_SYSTEM,
            user=TRACE_USER,
            images=(TEST_DATA_IMAGE,),
        )

    _assert_no_private_traceback_values(caught.value)


def test_empty_choices_traceback_locals_do_not_expose_raw_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"choices": [], "debug": TRACE_RAW_RESPONSE},
        )

    client = _client(monkeypatch, handler)

    with pytest.raises(AIResponseError) as caught:
        client.complete(
            "question_probe",
            system=TRACE_SYSTEM,
            user=TRACE_USER,
            images=(TEST_DATA_IMAGE,),
        )

    _assert_no_private_traceback_values(caught.value)


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
        enable_thinking=True,
        reasoning_effort="high",
    )
    result = _client(monkeypatch, handler, config=config).complete(
        "variant_verify_deepseek", system="verify", user="candidate"
    )

    assert seen["url"] == "https://example.test/deepseek/chat/completions"
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"]["model"] == "deepseek-v4-pro"
    assert seen["payload"]["enable_thinking"] is True
    assert seen["payload"]["reasoning_effort"] == "high"
    assert seen["timeout"] == {
        "connect": 300.0,
        "read": 300.0,
        "write": 300.0,
        "pool": 300.0,
    }
    assert result.provider == "deepseek"


def test_empty_optional_provider_key_fails_before_network(monkeypatch):
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return _success_response(request)

    client = _client(
        monkeypatch,
        handler,
        config=_config(
            task_key="variant_verify_deepseek",
            provider="deepseek",
            model="deepseek-v4-pro",
            api_key="",
        ),
    )

    with pytest.raises(
        AIConfigError, match="AI provider credentials are not configured"
    ) as caught:
        client.complete(
            "variant_verify_deepseek", system="verify", user="candidate"
        )

    assert attempts == []
    assert "deepseek" not in str(caught.value).lower()
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_real_deepseek_task_without_optional_key_makes_zero_network_attempts(
    monkeypatch,
):
    attempts = []
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return _success_response(request)

    reset_ai_config_for_tests()
    try:
        client = AIClient(transport=httpx.MockTransport(handler))
        with pytest.raises(
            AIConfigError,
            match="AI provider credentials are not configured",
        ):
            client.complete(
                "variant_verify_deepseek",
                system="verify",
                user="candidate",
            )
    finally:
        if "client" in locals():
            client.close()
        reset_ai_config_for_tests()

    assert attempts == []


def test_rejects_ambiguous_client_and_transport_injection(monkeypatch):
    monkeypatch.setattr(client_module, "load_ai_config", _config)
    transport = httpx.MockTransport(_success_response)

    with httpx.Client(transport=transport) as http_client:
        with pytest.raises(ValueError, match="client.*transport"):
            AIClient(client=http_client, transport=transport)
