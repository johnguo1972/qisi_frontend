"""Thin compatibility adapters for the shared course variant components."""

from __future__ import annotations

import hmac

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.components.variant_generator import VariantGeneratorComponent
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.response_parser import ResponseParser
from apps.common.exceptions import AIRequestError


_LEGACY_VARIANT_TASK_KEYS = (
    "variant_generate",
    "variant_verify_deepseek",
)
_LEGACY_MAX_TOKENS = frozenset({2000, 8000})
_LEGACY_TEMPERATURE = 0.1


def variant_generator_component_factory() -> VariantGeneratorComponent:
    return VariantGeneratorComponent()


def result_verifier_component_factory() -> ResultVerifierComponent:
    return ResultVerifierComponent(AIClient())


class VariantAIService:
    """Backward-compatible facade with no provider implementation of its own."""

    def generate(self, question: QuestionInput, variant_mode: str) -> dict:
        return variant_generator_component_factory().generate(
            question, variant_mode
        )

    def verify(self, original: dict, candidate: dict) -> dict:
        return result_verifier_component_factory().verify(
            "variant_verify_deepseek", original, candidate
        )

    def call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        api_url: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 8000,
        temperature: float = 0.1,
    ) -> str:
        return call_ai(
            system_prompt,
            user_prompt,
            model,
            api_url,
            api_key,
            max_tokens,
            temperature,
        )

    @staticmethod
    def parse_json_response(text: str) -> dict:
        return parse_json_response(text)

    @staticmethod
    def get_deepseek_api_key() -> str:
        return get_deepseek_api_key()


def generate_variant(question: QuestionInput, variant_mode: str) -> dict:
    return variant_generator_component_factory().generate(
        question, variant_mode
    )


def verify_variant(original: dict, candidate: dict) -> dict:
    return result_verifier_component_factory().verify(
        "variant_verify_deepseek", original, candidate
    )


def call_ai(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_url: str | None = None,
    api_key: str | None = None,
    max_tokens: int = 8000,
    temperature: float = 0.1,
) -> str:
    """Forward compatible legacy calls to a matching configured variant task.

    Positional and keyword arguments remain accepted. Provider/model/request
    parameters must match shared cfg (or an old ignored token/temperature
    default); arbitrary overrides are rejected instead of being silently routed.
    """
    task_key = _match_legacy_variant_task(
        model=model,
        api_url=api_url,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    model = ""
    api_url = None
    api_key = None
    max_tokens = 0
    temperature = 0.0
    if task_key is None:
        raise AIRequestError(
            "Legacy AI request does not match configured task"
        )
    with AIClient() as client:
        return client.complete(
            task_key,
            system=system_prompt,
            user=user_prompt,
        ).content


def _match_legacy_variant_task(
    *,
    model: str,
    api_url: str | None,
    api_key: str | None,
    max_tokens: int,
    temperature: float,
) -> str | None:
    if (
        type(model) is not str
        or (api_url is not None and type(api_url) is not str)
        or (api_key is not None and type(api_key) is not str)
        or type(max_tokens) is not int
        or type(temperature) not in (int, float)
    ):
        return None

    config = load_ai_config()
    for task_key in _LEGACY_VARIANT_TASK_KEYS:
        task = config.get_task_config(task_key)
        provider = config.get_provider_config(task.provider)
        if model != task.model:
            continue
        if api_url is not None and api_url != provider.api_url:
            continue
        if api_key is not None and not hmac.compare_digest(
            api_key.encode("utf-8"), provider.api_key.encode("utf-8")
        ):
            continue
        if max_tokens not in {*_LEGACY_MAX_TOKENS, task.max_tokens}:
            continue
        if temperature not in {_LEGACY_TEMPERATURE, task.temperature}:
            continue
        return task_key
    return None


def parse_json_response(text: str) -> dict:
    try:
        parsed = ResponseParser.parse_json(text)
    except AIResponseError:
        raise AIRequestError("Failed to parse AI JSON response") from None
    if not isinstance(parsed, dict):
        raise AIRequestError("AI JSON response must be an object")
    return parsed


def get_deepseek_api_key() -> str:
    """Retain the legacy accessor while delegating config ownership."""
    try:
        return load_ai_config().get_provider_config("deepseek").api_key
    except AIConfigError:
        raise AIRequestError("DEEPSEEK_API_KEY is not set") from None


def deepseek_verification_available() -> bool:
    try:
        return bool(get_deepseek_api_key())
    except AIRequestError:
        return False


def get_deepseek_model() -> str:
    try:
        return load_ai_config().get_task_config(
            "variant_verify_deepseek"
        ).model
    except AIConfigError:
        raise AIRequestError("DeepSeek verifier is not configured") from None
