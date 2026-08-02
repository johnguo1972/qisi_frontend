"""Thin compatibility adapters for the shared course variant components."""

from __future__ import annotations

from apps.common.ai.client import AIClient
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.components.variant_generator import VariantGeneratorComponent
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import AIConfigError, AIResponseError
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
    """Forward legacy Qwen calls to the configured shared client.

    Provider overrides are rejected so a legacy DeepSeek request can never be
    silently routed through Qwen.
    """
    del model, max_tokens, temperature
    if api_url is not None or api_key is not None:
        raise AIRequestError("Legacy AI provider overrides are unsupported")
    return AIClient().complete(
        "variant_generate",
        system=system_prompt,
        user=user_prompt,
    ).content


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
