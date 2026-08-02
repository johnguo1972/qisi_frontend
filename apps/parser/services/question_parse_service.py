"""Question parse service: stage 2 - parse individual questions."""
import logging
import os
from django.conf import settings
from apps.common.ai.components.vision_parser import VisionParserComponent
from apps.common.exceptions import AIRequestError
from apps.parser.prompts.question_parse_prompt import (
    QUESTION_TYPE_LABELS,
)
from apps.parser.services.schema_service import validate_and_repair_json

logger = logging.getLogger(__name__)

class QuestionParseService:
    """Compatibility adapter for shared question vision parsing."""

    def __init__(self, component=None):
        self._component = component or VisionParserComponent()

    def parse_question(self, question_info: dict, page_images: list, page_nos: list) -> dict:
        """Parse a single question.

        Args:
            question_info: dict with question_no, question_type, section_title, page_start, page_end
            page_images: list of absolute paths to page images
            page_nos: list of page numbers corresponding to page_images

        Returns:
            dict with keys: raw_response, response_json, latency_ms, parsed
        """
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

        try:
            ai_result = self._component.parse_question(
                page_images,
                {
                    'question_no': question_no,
                    'question_type': question_type,
                    'question_type_label': QUESTION_TYPE_LABELS.get(
                        question_type, '未知'
                    ),
                    'section_title': section_title,
                    'page_start': page_start,
                    'page_end': page_end,
                    'multi_page_notice': multi_page_notice,
                },
            )

            # Parse and repair JSON
            parsed = validate_and_repair_json(ai_result['raw_response'])

            # Add page info
            parsed['page_no'] = page_start
            parsed['page_end'] = page_end

            return {
                "raw_response": ai_result['raw_response'],
                "response_json": ai_result['response_json'],
                "latency_ms": ai_result['latency_ms'],
                "parsed": parsed,
            }
        except AIRequestError:
            raise
        except Exception:
            raise AIRequestError("Question vision parsing failed") from None


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
