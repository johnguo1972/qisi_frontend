"""Position service: stage 1 - detect question positions using qwen3.6-plus."""
import json
import logging
import re
from apps.parser.prompts.position_prompt import POSITION_SYSTEM_PROMPT, POSITION_USER_PROMPT
from apps.parser.services.qwen_text_service import QwenTextService
from apps.parser.schemas.page_parse_schema import validate_position_result
from apps.common.exceptions import AIRequestError

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    """Extract JSON from AI response that may be wrapped in markdown code fences."""
    stripped = text.strip()
    # Try to find ```json ... ``` or ``` ... ``` block
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', stripped)
    if match:
        return match.group(1).strip()
    # If no code fences, return as-is
    return stripped


def detect_positions(page_images: list) -> list:
    """Detect question positions for all pages.

    Args:
        page_images: List of dicts with keys: page_no, path (absolute path to page image)

    Returns:
        List of position results, each containing:
        - page_no: int
        - questions: list of {question_no, section_title, page_start, page_end, bbox, is_cross_page}
        - raw_response: str
        - latency_ms: int
    """
    text_service = QwenTextService()
    results = []

    for page_info in page_images:
        page_no = page_info['page_no']
        image_path = page_info['path']

        logger.info(f'Stage 1: Detecting question positions for page {page_no}')

        try:
            ai_result = text_service.detect_question_positions(
                image_path, POSITION_SYSTEM_PROMPT, POSITION_USER_PROMPT
            )

            # Use lightweight position schema instead of PageParseResult
            cleaned = _extract_json(ai_result['raw_response'])
            raw_data = json.loads(cleaned)
            try:
                validated = validate_position_result(raw_data)
                questions = validated.model_dump().get('questions', [])
            except Exception as e:
                logger.warning(f"Position schema validation failed for page {page_no}: {e}")
                questions = raw_data.get('questions', [])

            results.append({
                'page_no': page_no,
                'questions': questions,
                'raw_response': ai_result['raw_response'],
                'latency_ms': ai_result['latency_ms'],
            })

            logger.info(f'Page {page_no}: detected {len(questions)} questions')

        except AIRequestError as e:
            logger.exception(f'Position detection failed for page {page_no}: {e}')
            results.append({
                'page_no': page_no,
                'questions': [],
                'raw_response': '',
                'error': str(e),
                'latency_ms': 0,
            })

    return results


def build_page_range_map(position_results: list) -> dict:
    """Build a mapping of page_no -> list of question position info.

    Args:
        position_results: Output from detect_positions()

    Returns:
        Dict mapping page_no -> list of question position dicts
    """
    page_map = {}
    for result in position_results:
        page_no = result['page_no']
        page_map[page_no] = result.get('questions', [])
    return page_map


def merge_cross_page_positions(position_results: list) -> list:
    """Merge cross-page question positions.

    When stage 1 detects a question that spans multiple pages, this function
    consolidates the position info.

    Args:
        position_results: Output from detect_positions()

    Returns:
        List of consolidated question position dicts, each with:
        - question_no, section_title, page_start, page_end, bbox, is_cross_page
        - pages: list of page_nos that contain this question
    """
    all_questions = []

    for result in position_results:
        page_no = result['page_no']
        for q in result.get('questions', []):
            q['page_start'] = page_no
            q['page_end'] = q.get('page_end', page_no)
            q['pages'] = list(range(q['page_start'], q['page_end'] + 1))
            all_questions.append(q)

    return all_questions
