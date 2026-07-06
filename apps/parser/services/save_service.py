"""Save service: crop question images and save all questions to DB."""
import logging
import os
from pathlib import Path
from PIL import Image
from django.conf import settings
from apps.parser.models import ExamPage, ExamQuestion, QuestionOption, QuestionImage
from apps.common import status as const
from apps.common.codegen import generate_question_system_id, extract_major_section_no, batch_compute_paper_question_nos

logger = logging.getLogger(__name__)


def crop_question_image(page_image_path: str, bbox: dict | list, output_path: str) -> str | None:
    """Crop a region from a page image and save it.

    Args:
        page_image_path: Absolute path to the full page image.
        bbox: Either a dict with keys x1, y1, x2, y2, or a list [x1, y1, x2, y2].
        output_path: Absolute path to save the cropped image.

    Returns:
        Relative path of the cropped image, or None if cropping failed.
    """
    try:
        if isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            x1 = bbox.get('x1', 0)
            y1 = bbox.get('y1', 0)
            x2 = bbox.get('x2', 0)
            y2 = bbox.get('y2', 0)
        with Image.open(page_image_path) as img:
            cropped = img.crop((x1, y1, x2, y2))
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cropped.save(output_path)
            return output_path
    except Exception as e:
        logger.warning(f'Failed to crop image: {e}')
        return None


def save_questions(paper, questions: list, page_map: dict):
    """Save parsed questions, options, and cropped images to the database.

    Args:
        paper: ExamPaper instance.
        questions: List of processed question dicts from postprocess_questions().
        page_map: Dict mapping page_no -> ExamPage instance.
    """
    created_count = 0

    # Pre-compute paper_question_no for all questions
    paper_question_nos = batch_compute_paper_question_nos(paper, questions)

    for idx, q in enumerate(questions):
        # Determine parent question for sub-questions
        parent = None
        if q.get('is_sub_question') and q.get('parent_question_no'):
            parent = ExamQuestion.objects.filter(
                paper=paper, question_no=q['parent_question_no']
            ).first()

        # Generate system ID and paper question number
        system_id = generate_question_system_id(paper.subject)
        paper_question_no = paper_question_nos[idx]

        # Create ExamQuestion
        question = ExamQuestion.objects.create(
            paper=paper,
            question_no=q.get('question_no', str(idx + 1)),
            system_id=system_id,
            paper_question_no=paper_question_no,
            parent_question=parent,
            section_title=q.get('section_title'),
            question_type=q.get('question_type', const.QT_UNKNOWN),
            subject=paper.subject,
            stem=q.get('stem', ''),
            answer=q.get('answer', ''),
            analysis=q.get('analysis', ''),
            solution=q.get('solution', ''),
            raw_explanation=q.get('explanation', ''),
            knowledge_points=q.get('knowledge_points'),
            difficulty=q.get('difficulty'),
            confidence=q.get('confidence'),
            page_start=q.get('page_no'),
            page_end=q.get('page_end', q.get('page_no')),
            bbox=q.get('bbox'),
            sort_order=idx,
            need_review=q.get('need_review', True),
            formula_need_review=q.get('formula_need_review', False),
            review_status='need_review' if q.get('need_review', True) else 'unreviewed',
            parse_status=const.QUESTION_AUTO_PARSED,
        )

        # Save options (for multiple choice / single choice questions)
        options = q.get('options', [])
        if options:
            for opt_idx, opt in enumerate(options):
                QuestionOption.objects.create(
                    question=question,
                    option_label=opt.get('label', ''),
                    content=opt.get('content', ''),
                    bbox=opt.get('bbox'),
                    sort_order=opt_idx,
                )

        # Crop and save images
        images = q.get('images', [])
        page_no = q.get('page_no')
        if images:
            for img_idx, img_info in enumerate(images):
                # Word-extracted images: already saved as files, no bbox
                if img_info.get('source') == 'word_extracted':
                    file_path = img_info.get('file_path', '')
                    if file_path:
                        QuestionImage.objects.create(
                            paper=paper,
                            question=question,
                            page=None,
                            image_type=img_info.get('image_type', 'diagram'),
                            file_path=file_path,
                            source_page_image_path=None,
                            bbox=None,
                            description=img_info.get('description', ''),
                            sort_order=img_idx,
                        )
                    continue

                # Qwen-detected images: crop from page image
                bbox = img_info.get('bbox')
                if not bbox or page_no not in page_map:
                    continue

                # Parse bbox (list or dict)
                if isinstance(bbox, list) and len(bbox) == 4:
                    bx1, by1, bx2, by2 = bbox
                else:
                    bx1 = bbox.get('x1', 0)
                    by1 = bbox.get('y1', 0)
                    bx2 = bbox.get('x2', 0)
                    by2 = bbox.get('y2', 0)

                # Skip crops that are too small to be a meaningful image
                # (e.g., the LLM mistakenly returned text region as image bbox)
                MIN_IMG_AREA = 50 * 50  # 2500 pixels
                if (bx2 - bx1) * (by2 - by1) < MIN_IMG_AREA:
                    q['need_review_reason'] = (
                        q.get('need_review_reason', '') +
                        'AI标注图片bbox过小(%dx%d)，可能标注有误 ' % (bx2 - bx1, by2 - by1)
                    )
                    question.need_review = True
                    question.save(update_fields=['need_review'])
                    continue

                page = page_map[page_no]

                # Crop image from page
                src_page_image = str(settings.MEDIA_ROOT / page.image_path)
                crop_dir = settings.MEDIA_ROOT / 'exams' / str(paper.id) / 'crops'
                crop_filename = f'q{question.id}_{img_idx}.png'
                crop_abs_path = str(crop_dir / crop_filename)

                cropped = crop_question_image(src_page_image, bbox, crop_abs_path)
                if cropped:
                    rel_path = os.path.relpath(cropped, str(settings.MEDIA_ROOT))
                    QuestionImage.objects.create(
                        paper=paper,
                        question=question,
                        page=page,
                        image_type=img_info.get('image_type', 'diagram'),
                        file_path=rel_path,
                        source_page_image_path=page.image_path,
                        bbox=bbox,
                        description=img_info.get('description', ''),
                        sort_order=img_idx,
                    )

        created_count += 1

    # Update paper total question count
    paper.total_questions = created_count
    paper.save(update_fields=['total_questions'])

    logger.info(f'Saved {created_count} questions for paper {paper.id}')
