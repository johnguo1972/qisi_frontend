"""Thin compatibility adapters for the shared course variant components."""

from __future__ import annotations

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.components.variant_generator import VariantGeneratorComponent
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.legacy_variant_adapter import (
    complete_legacy_variant_request,
    configured_provider_available,
    get_configured_provider_key,
    get_configured_task_model,
)
from apps.common.ai.response_parser import ResponseParser
from apps.common.exceptions import AIRequestError


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
    try:
        return complete_legacy_variant_request(
            system_prompt,
            user_prompt,
            model,
            api_url,
            api_key,
            max_tokens,
            temperature,
            config_loader=load_ai_config,
            client_factory=AIClient,
        )
    finally:
        system_prompt = ""
        user_prompt = ""
        model = ""
        api_url = None
        api_key = None
        max_tokens = 0
        temperature = 0.0


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
        return get_configured_provider_key(
            "deepseek", config_loader=load_ai_config
        )
    except AIConfigError:
        raise AIRequestError("DeepSeek verifier is not configured") from None


def deepseek_verification_available() -> bool:
    return configured_provider_available(
        "deepseek", config_loader=load_ai_config
    )


def get_deepseek_model() -> str:
    try:
        return get_configured_task_model(
            "variant_verify_deepseek", config_loader=load_ai_config
        )
    except AIConfigError:
        raise AIRequestError("DeepSeek verifier is not configured") from None
