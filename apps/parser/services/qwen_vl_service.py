"""qwen3-VL-plus API service for page parsing."""
import json
import logging
import base64
import os
import time
import httpx
from django.conf import settings
from apps.common.exceptions import AIRequestError
from apps.parser.prompts.page_parse_prompt import PAGE_PARSE_SYSTEM_PROMPT, PAGE_PARSE_USER_PROMPT

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen3-vl-plus"


class QwenVLService:
    """Service for calling qwen3-VL-plus to parse exam pages."""

    def __init__(self):
        self.api_key = os.environ.get('QWEN_API_KEY', '')
        if not self.api_key:
            raise AIRequestError("QWEN_API_KEY environment variable is not set")

    def parse_page(self, image_path: str) -> dict:
        """Parse a single exam page image.

        Args:
            image_path: Absolute path to the page image file.

        Returns:
            dict with keys: raw_response, response_json, latency_ms
        """
        image_b64 = self._encode_image(image_path)

        messages = [
            {"role": "system", "content": PAGE_PARSE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    },
                    {"type": "text", "text": PAGE_PARSE_USER_PROMPT}
                ]
            }
        ]

        payload = {
            "model": QWEN_MODEL,
            "messages": messages,
            "max_tokens": 8000,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.time()
        try:
            with httpx.Client(timeout=120.0, trust_env=False) as client:
                response = client.post(QWEN_API_URL, json=payload, headers=headers)
                response.raise_for_status()

            latency_ms = int((time.time() - start_time) * 1000)
            result = response.json()

            # Extract assistant message content
            choices = result.get("choices", [])
            if not choices:
                raise AIRequestError("No choices in qwen3-VL-plus response")

            content = choices[0]["message"]["content"]
            response_json = json.dumps(result, ensure_ascii=False)

            return {
                "raw_response": content,
                "response_json": response_json,
                "latency_ms": latency_ms,
            }

        except httpx.HTTPError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            raise AIRequestError(f"qwen3-VL-plus API request failed: {e}")
        except Exception as e:
            raise AIRequestError(f"Unexpected error calling qwen3-VL-plus: {e}")

    def _encode_image(self, image_path: str) -> str:
        """Read image file and return base64-encoded string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
