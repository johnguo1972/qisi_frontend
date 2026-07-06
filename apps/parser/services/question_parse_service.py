"""Question parse service: stage 2 - parse individual questions using qwen3-VL-plus."""
import json
import logging
import base64
import os
import time
import httpx
from django.conf import settings
from apps.common.exceptions import AIRequestError
from apps.parser.prompts.question_parse_prompt import (
    QUESTION_PARSE_SYSTEM_PROMPT,
    QUESTION_PARSE_USER_PROMPT_TEMPLATE,
    QUESTION_TYPE_LABELS,
)
from apps.parser.services.schema_service import validate_and_repair_json

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_VL_MODEL = "qwen3-vl-plus"


class QuestionParseService:
    """Service for parsing individual questions using qwen3-VL-plus."""

    def __init__(self):
        self.api_key = os.environ.get('QWEN_API_KEY', '')
        if not self.api_key:
            raise AIRequestError("QWEN_API_KEY environment variable is not set")

    def parse_question(self, question_info: dict, page_images: list, page_nos: list) -> dict:
        """Parse a single question.

        Args:
            question_info: dict with question_no, question_type, section_title, page_start, page_end
            page_images: list of absolute paths to page images
            page_nos: list of page numbers corresponding to page_images

        Returns:
            dict with keys: raw_response, response_json, latency_ms, parsed
        """
        # Build multi-image content
        content_parts = []
        for img_path, page_no in zip(page_images, page_nos):
            image_b64 = self._encode_image(img_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"}
            })

        # Build user prompt
        question_no = question_info.get('question_no', '?')
        question_type = question_info.get('question_type', 'unknown')
        section_title = question_info.get('section_title', '')
        page_start = question_info.get('page_start', 1)
        page_end = question_info.get('page_end', page_start)

        multi_page_notice = ""
        if len(page_images) > 1:
            multi_page_notice = (
                f"**注意**：该题目跨页，涉及第 {', '.join(str(p) for p in page_nos)} 页。"
                f"请综合分析所有页面的内容，确保解析完整。"
            )

        user_prompt = QUESTION_PARSE_USER_PROMPT_TEMPLATE.format(
            question_no=question_no,
            question_type=question_type,
            question_type_label=QUESTION_TYPE_LABELS.get(question_type, '未知'),
            section_title=section_title,
            page_start=page_start,
            page_end=page_end,
            multi_page_notice=multi_page_notice,
        )

        content_parts.append({"type": "text", "text": user_prompt})

        messages = [
            {"role": "system", "content": QUESTION_PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": content_parts}
        ]

        payload = {
            "model": QWEN_VL_MODEL,
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
            with httpx.Client(timeout=180.0, trust_env=False) as client:
                response = client.post(QWEN_API_URL, json=payload, headers=headers)
                response.raise_for_status()

            latency_ms = int((time.time() - start_time) * 1000)
            result = response.json()

            choices = result.get("choices", [])
            if not choices:
                raise AIRequestError("No choices in qwen3-VL-plus response")

            content = choices[0]["message"]["content"]
            response_json = json.dumps(result, ensure_ascii=False)

            # Parse and repair JSON
            parsed = validate_and_repair_json(content)

            # Add page info
            parsed['page_no'] = page_start
            parsed['page_end'] = page_end

            return {
                "raw_response": content,
                "response_json": response_json,
                "latency_ms": latency_ms,
                "parsed": parsed,
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


def parse_questions_stage2(position_results: list, page_map: dict, progress_callback=None) -> list:
    """Stage 2: Parse each question using the position info from stage 1.

    Args:
        position_results: Output from position_service.detect_positions()
        page_map: Dict mapping page_no -> ExamPage instance (for image paths)
        progress_callback: Optional callable(question_no, current, total) for progress updates.

    Returns:
        List of parsed question dicts ready for postprocessing.
    """
    from apps.parser.models import ExamPage

    service = QuestionParseService()
    all_questions = []

    # Count total questions first
    total_questions = sum(len(result.get('questions', [])) for result in position_results)

    # Collect all questions from all pages
    parsed_count = 0
    for result in position_results:
        page_no = result['page_no']
        for q_info in result.get('questions', []):
            q_info['page_start'] = page_no
            q_info['page_end'] = q_info.get('page_end', page_no)

            # Get page images for this question
            page_nos = list(range(q_info['page_start'], q_info['page_end'] + 1))
            page_images = []
            for pn in page_nos:
                if pn in page_map:
                    page = page_map[pn]
                    img_path = str(settings.MEDIA_ROOT / page.image_path)
                    if os.path.exists(img_path):
                        page_images.append(img_path)

            if not page_images:
                logger.warning(f'No page images found for Q{q_info.get("question_no")} on pages {page_nos}')
                parsed_count += 1
                if progress_callback:
                    progress_callback(q_info.get('question_no', '?'), parsed_count, total_questions)
                continue

            try:
                parse_result = service.parse_question(q_info, page_images, page_nos)
                parsed = parse_result['parsed']

                # Add confidence and other metadata
                parsed['page_no'] = q_info['page_start']
                parsed['page_end'] = q_info['page_end']
                parsed['section_title'] = q_info.get('section_title', '')
                parsed['bbox'] = q_info.get('bbox')

                all_questions.append(parsed)
                logger.info(
                    f'Parsed Q{q_info.get("question_no")} '
                    f'(pages {q_info["page_start"]}-{q_info["page_end"]}, {parse_result["latency_ms"]}ms)'
                )

            except AIRequestError as e:
                logger.exception(f'Failed to parse Q{q_info.get("question_no")}: {e}')

            parsed_count += 1
            if progress_callback:
                progress_callback(q_info.get('question_no', '?'), parsed_count, total_questions)

    return all_questions
