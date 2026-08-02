"""Position service: stage 1 - detect question positions."""
import logging
from apps.common.ai.components.vision_parser import VisionParserComponent
from apps.parser.schemas.page_parse_schema import validate_position_result
from apps.common.ai.failure_safety import (
    POSITION_DETECTION_FAILURE,
    log_safe_failure,
)

logger = logging.getLogger(__name__)


def vision_parser_component_factory() -> VisionParserComponent:
    return VisionParserComponent()


def detect_positions(page_images: list) -> list:
    """Detect question positions for all pages.

    Args:
        page_images: List of dicts with keys: page_no, path (absolute path to page image)

    Returns:
        List of position results, each containing:
        - page_no: int
        - questions: list of {question_no, section_title, page_start, page_end, bbox, is_cross_page}
        - raw_response: str
        - response_json: str
        - latency_ms: int
    """
    component = None
    component_failed = False
    try:
        component = vision_parser_component_factory()
    except Exception:
        component_failed = True
        log_safe_failure(logger, POSITION_DETECTION_FAILURE)
    try:
        return _detect_positions_with_component(
            component, component_failed, page_images
        )
    finally:
        close = getattr(component, "close", None)
        if callable(close):
            close()
        component = None
        page_images = []


def _detect_positions_with_component(
    component, component_failed: bool, page_images: list
) -> list:
    results = []

    for page_info in page_images:
        page_no = page_info['page_no']
        image_path = page_info['path']

        logger.info(f'Stage 1: Detecting question positions for page {page_no}')

        if component_failed:
            results.append({
                'page_no': page_no,
                'questions': [],
                'raw_response': '',
                'response_json': '',
                'error': POSITION_DETECTION_FAILURE.detail,
                'latency_ms': 0,
            })
            continue

        try:
            ai_result = component.detect_positions(image_path)

            # Use lightweight position schema instead of PageParseResult
            raw_data = ai_result['parsed']
            try:
                validated = validate_position_result(raw_data)
                questions = validated.model_dump().get('questions', [])
            except Exception:
                logger.warning(
                    "Position schema validation failed",
                    extra={"failure_code": "POSITION_SCHEMA_INVALID"},
                )
                questions = raw_data.get('questions', [])

            results.append({
                'page_no': page_no,
                'questions': questions,
                'raw_response': ai_result['raw_response'],
                'response_json': ai_result['response_json'],
                'latency_ms': ai_result['latency_ms'],
            })

            logger.info(f'Page {page_no}: detected {len(questions)} questions')

        except Exception:
            log_safe_failure(logger, POSITION_DETECTION_FAILURE)
            results.append({
                'page_no': page_no,
                'questions': [],
                'raw_response': '',
                'response_json': '',
                'error': POSITION_DETECTION_FAILURE.detail,
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
