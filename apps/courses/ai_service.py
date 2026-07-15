"""AI service for variant question generation and verification."""
import json
import logging
import time
import os
import httpx

from django.conf import settings
from apps.common.exceptions import AIRequestError
from apps.common.utils import repair_json_string

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# DeepSeek API endpoint
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


class VariantAIService:
    """变式题生成 AI 服务，与 AIReviewService 模式一致。"""

    def __init__(self):
        self.qwen_api_key = os.environ.get('QWEN_API_KEY', '')
        if not self.qwen_api_key:
            raise AIRequestError("QWEN_API_KEY is not set")
        self.deepseek_api_key = os.environ.get('DEEPSEEK_API_KEY', '')

    def call_ai(self, system_prompt: str, user_prompt: str,
                model: str, api_url: str = QWEN_API_URL,
                api_key: str = None,
                max_tokens: int = 8000, temperature: float = 0.1) -> str:
        """调用 AI API，带重试逻辑（最多 3 次）。

        Returns:
            AI 响应文本
        Raises:
            AIRequestError: 调用失败时抛出异常
        """
        if api_key is None:
            api_key = self.qwen_api_key

        retry_delays = [5, 8, 10]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(1, 4):
            try:
                with httpx.Client(timeout=300.0, trust_env=False) as client:
                    response = client.post(api_url, json=payload, headers=headers)
                    response.raise_for_status()
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    raise AIRequestError("No choices in AI response")
                return choices[0]["message"]["content"]
            except httpx.ReadTimeout as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI API timeout (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except httpx.HTTPError as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI API HTTP error (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except Exception as e:
                raise AIRequestError(f"Unexpected AI API error: {e}")

        raise AIRequestError(f"AI API call failed after 3 attempts: {last_error}")

    def get_deepseek_api_key(self) -> str:
        """获取 DeepSeek API Key。"""
        if not self.deepseek_api_key:
            raise AIRequestError("DEEPSEEK_API_KEY is not set")
        return self.deepseek_api_key

    @staticmethod
    def parse_json_response(text: str) -> dict:
        """解析 AI 返回的 JSON 响应，处理 markdown 代码块。

        Returns:
            解析后的 dict
        Raises:
            AIRequestError: JSON 解析失败时抛出异常
        """
        cleaned = repair_json_string(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise AIRequestError(f"Failed to parse AI JSON response: {e}\nRaw: {text[:500]}")


# ------------------------------------------------------------------ #
#  向后兼容：模块级函数包装器（供 tasks.py 直接调用）                    #
# ------------------------------------------------------------------ #

_default_service: VariantAIService = None


def _get_service() -> VariantAIService:
    """Lazy-initialize the singleton service."""
    global _default_service
    if _default_service is None:
        _default_service = VariantAIService()
    return _default_service


def call_ai(system_prompt: str, user_prompt: str,
            model: str, api_url: str = QWEN_API_URL,
            api_key: str = None,
            max_tokens: int = 8000, temperature: float = 0.1) -> str:
    """Module-level wrapper around VariantAIService.call_ai for backward compat."""
    return _get_service().call_ai(
        system_prompt, user_prompt, model, api_url, api_key,
        max_tokens, temperature
    )


def parse_json_response(text: str) -> dict:
    """Module-level wrapper around VariantAIService.parse_json_response for backward compat."""
    return VariantAIService.parse_json_response(text)


def get_deepseek_api_key() -> str:
    """Module-level wrapper for backward compat."""
    return _get_service().get_deepseek_api_key()
