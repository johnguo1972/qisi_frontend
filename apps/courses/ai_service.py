"""AI service for variant question generation and verification."""
import json
import logging
import time
import os
import httpx

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# DeepSeek API endpoint
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def get_api_key() -> str:
    """获取通义千问 API Key。"""
    api_key = os.environ.get('QWEN_API_KEY', '')
    if not api_key:
        raise ValueError("QWEN_API_KEY is not set")
    return api_key


def get_deepseek_api_key() -> str:
    """获取 DeepSeek API Key。"""
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set")
    return api_key


def call_ai(system_prompt: str, user_prompt: str,
            model: str, api_url: str = QWEN_API_URL,
            api_key: str = None,
            max_tokens: int = 8000, temperature: float = 0.1) -> str:
    """调用 AI API，带重试逻辑（最多 3 次）。

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        model: 模型名称
        api_url: API 端点 URL
        api_key: API Key（默认从环境变量获取）
        max_tokens: 最大输出 token 数
        temperature: 温度参数

    Returns:
        AI 响应文本

    Raises:
        ValueError: 调用失败时抛出异常
    """
    if api_key is None:
        api_key = get_api_key()

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
                raise ValueError("No choices in AI response")
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
            raise ValueError(f"Unexpected AI API error: {e}")

    raise ValueError(f"AI API call failed after 3 attempts: {last_error}")


def parse_json_response(text: str) -> dict:
    """解析 AI 返回的 JSON 响应，处理 markdown 代码块。

    Args:
        text: AI 返回的原始文本

    Returns:
        解析后的 dict

    Raises:
        ValueError: JSON 解析失败时抛出异常
    """
    import re
    from apps.common.utils import repair_json_string

    cleaned = repair_json_string(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AI JSON response: {e}\nRaw: {text[:500]}")
