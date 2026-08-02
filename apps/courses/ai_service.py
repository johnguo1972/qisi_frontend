"""Structured adapters for shared course variant components."""

from __future__ import annotations

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
    return ResultVerifierComponent()


class VariantAIService:
    """Backward-compatible facade with no provider implementation of its own."""

    def generate(self, question: QuestionInput, variant_mode: str) -> dict:
        return generate_variant(question, variant_mode)

    def verify(self, original: dict, candidate: dict) -> dict:
        return verify_variant(original, candidate)

    @staticmethod
    def parse_json_response(text: str) -> dict:
        return parse_json_response(text)

def generate_variant(question: QuestionInput, variant_mode: str) -> dict:
    component = variant_generator_component_factory()
    try:
        return component.generate(question, variant_mode)
    finally:
        component.close()


def verify_variant(original: dict, candidate: dict) -> dict:
    component = result_verifier_component_factory()
    try:
        return component.verify(
            "variant_verify_deepseek", original, candidate
        )
    finally:
        component.close()


def parse_json_response(text: str) -> dict:
    try:
        parsed = ResponseParser.parse_json(text)
    except AIResponseError:
        raise AIRequestError("Failed to parse AI JSON response") from None
    if not isinstance(parsed, dict):
        raise AIRequestError("AI JSON response must be an object")
    return parsed


def deepseek_verification_available() -> bool:
    config = None
    try:
        config = load_ai_config()
        return bool(config.get_provider_config("deepseek").api_key)
    except AIConfigError:
        return False
    finally:
        config = None


def get_deepseek_model() -> str:
    config = None
    try:
        config = load_ai_config()
        return config.get_task_config("variant_verify_deepseek").model
    except AIConfigError:
        raise AIRequestError("DeepSeek verifier is not configured") from None
    finally:
        config = None
