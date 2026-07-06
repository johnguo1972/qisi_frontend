"""qwen3.6-plus API service for text-based question positioning."""
import json
import logging
import base64
import os
import time
import io
import httpx
from PIL import Image
from django.conf import settings
from apps.common.exceptions import AIRequestError

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_TEXT_MODEL = "qwen3.6-plus"


class QwenTextService:
    """Service for calling qwen3.6-plus for question position detection."""

    def __init__(self):
        self.api_key = os.environ.get('QWEN_API_KEY', '')
        if not self.api_key:
            raise AIRequestError("QWEN_API_KEY environment variable is not set")

    def detect_question_positions(self, image_path: str, system_prompt: str, user_prompt: str) -> dict:
        """Detect question positions from a page image.

        Args:
            image_path: Absolute path to the page image file.
            system_prompt: System prompt for positioning.
            user_prompt: User prompt for positioning.

        Returns:
            dict with keys: raw_response, response_json, latency_ms
        """
        image_b64 = self._encode_image(image_path)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    },
                    {"type": "text", "text": user_prompt}
                ]
            }
        ]

        payload = {
            "model": QWEN_TEXT_MODEL,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.time()
        last_error = None
        for attempt in range(1, 4):  # up to 3 attempts with exponential backoff
            try:
                with httpx.Client(timeout=300.0, trust_env=False) as client:
                    response = client.post(QWEN_API_URL, json=payload, headers=headers)
                    response.raise_for_status()

                latency_ms = int((time.time() - start_time) * 1000)
                result = response.json()

                # Extract assistant message content
                choices = result.get("choices", [])
                if not choices:
                    raise AIRequestError("No choices in qwen3.6-plus response")

                content = choices[0]["message"]["content"]
                response_json = json.dumps(result, ensure_ascii=False)

                return {
                    "raw_response": content,
                    "response_json": response_json,
                    "latency_ms": latency_ms,
                }

            except httpx.ReadTimeout as e:
                last_error = e
                wait = min(10 * (2 ** (attempt - 1)), 60)  # 10s, 20s, 40s (cap at 60s)
                logger.warning(f"qwen3.6-plus read timeout (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except httpx.HTTPError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                raise AIRequestError(f"qwen3.6-plus API request failed: {e}")
            except Exception as e:
                raise AIRequestError(f"Unexpected error calling qwen3.6-plus: {e}")

        raise AIRequestError(f"qwen3.6-plus API request failed after 3 attempts: {last_error}")

    def _encode_image(self, image_path: str, max_width: int = 1200) -> str:
        """Read image file, optionally resize, and return base64-encoded JPEG."""
        img = Image.open(image_path)
        # Resize if wider than max_width (maintains aspect ratio)
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        # Save as JPEG with quality=85 for smaller payload
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
