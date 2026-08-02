"""Config-backed compatibility access for the retired course AI API."""

from __future__ import annotations

import hmac
from collections.abc import Callable

from apps.common.exceptions import AIRequestError

from .client import AIClient
from .config import AIConfig, load_ai_config
from .exceptions import AIConfigError


LEGACY_VARIANT_TASK_KEYS = (
    "variant_generate",
    "variant_verify_deepseek",
)
LEGACY_MAX_TOKENS = frozenset({2000, 8000})
LEGACY_TEMPERATURE = 0.1


def complete_legacy_variant_request(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_url: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.1,
    *,
    config_loader: Callable[[], AIConfig] = load_ai_config,
    client_factory=AIClient,
) -> str:
    """Map a legacy request to one configured shared-client task."""
    failure_kind = ""
    config = None
    task_key = None
    client = None
    opened_client = None
    completion = None
    try:
        config = config_loader()
        task_key = match_legacy_variant_task(
            config,
            model=model,
            api_url=api_url,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if task_key is None:
            failure_kind = "mismatch"
        else:
            client = client_factory()
            with client as opened_client:
                completion = opened_client.complete(
                    task_key,
                    system=system_prompt,
                    user=user_prompt,
                )
                return completion.content
    except AIConfigError:
        failure_kind = "config"
    except AIRequestError:
        failure_kind = "request"
    except Exception:
        failure_kind = "request"
    finally:
        system_prompt = ""
        user_prompt = ""
        model = ""
        api_url = None
        api_key = None
        max_tokens = 0
        temperature = 0.0
        config_loader = None
        client_factory = None
        config = None
        task_key = None
        client = None
        opened_client = None
        completion = None

    if failure_kind == "mismatch":
        raise AIRequestError(
            "Legacy AI request does not match configured task"
        )
    if failure_kind == "config":
        raise AIConfigError("AI configuration is unavailable")
    raise AIRequestError("AI provider request failed")


def match_legacy_variant_task(
    config: AIConfig,
    *,
    model: str,
    api_url: str | None,
    api_key: str | None,
    max_tokens: int,
    temperature: float,
) -> str | None:
    task = None
    provider = None
    task_key = None
    try:
        if (
            type(model) is not str
            or (api_url is not None and type(api_url) is not str)
            or (api_key is not None and type(api_key) is not str)
            or type(max_tokens) is not int
            or type(temperature) not in (int, float)
        ):
            return None

        for task_key in LEGACY_VARIANT_TASK_KEYS:
            task = config.get_task_config(task_key)
            provider = config.get_provider_config(task.provider)
            if model != task.model:
                continue
            if api_url is not None and api_url != provider.api_url:
                continue
            if api_key is not None and not _api_keys_match(
                api_key, provider.api_key
            ):
                continue
            if max_tokens not in {*LEGACY_MAX_TOKENS, task.max_tokens}:
                continue
            if temperature not in {LEGACY_TEMPERATURE, task.temperature}:
                continue
            return task_key
        return None
    finally:
        config = None
        model = ""
        api_url = None
        api_key = None
        max_tokens = 0
        temperature = 0.0
        task = None
        provider = None
        task_key = None


def get_configured_provider_key(
    provider: str,
    *,
    config_loader: Callable[[], AIConfig] = load_ai_config,
) -> str:
    config = None
    provider_config = None
    try:
        config = config_loader()
        provider_config = config.get_provider_config(provider)
        return provider_config.api_key
    finally:
        provider = ""
        config_loader = None
        config = None
        provider_config = None


def configured_provider_available(
    provider: str,
    *,
    config_loader: Callable[[], AIConfig] = load_ai_config,
) -> bool:
    available = False
    try:
        available = bool(
            get_configured_provider_key(
                provider, config_loader=config_loader
            )
        )
    except AIConfigError:
        available = False
    finally:
        provider = ""
        config_loader = None
    return available


def get_configured_task_model(
    task_key: str,
    *,
    config_loader: Callable[[], AIConfig] = load_ai_config,
) -> str:
    config = None
    task = None
    try:
        config = config_loader()
        task = config.get_task_config(task_key)
        return task.model
    finally:
        task_key = ""
        config_loader = None
        config = None
        task = None


def _api_keys_match(provided: str, configured: str) -> bool:
    provided_bytes = b""
    configured_bytes = b""
    try:
        provided_bytes = provided.encode("utf-8")
        configured_bytes = configured.encode("utf-8")
    except UnicodeEncodeError:
        return False
    try:
        return hmac.compare_digest(provided_bytes, configured_bytes)
    finally:
        provided = ""
        configured = ""
        provided_bytes = b""
        configured_bytes = b""
