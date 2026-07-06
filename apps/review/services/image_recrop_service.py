"""Image recropping for human review."""
import logging
import os
from django.conf import settings
from apps.common.exceptions import ImageCropError
from apps.parser.services.save_service import crop_question_image

logger = logging.getLogger(__name__)


def recrop_question_image(question, new_bbox: list, image_id=None, page_no=None, description='人工重裁'):
    """Re-crop a question's image with a new bbox.

    Args:
        question: ExamQuestion instance
        new_bbox: [x1, y1, x2, y2] pixel coordinates
        image_id: if provided, update existing QuestionImage; otherwise create new
        page_no: page number to crop from (defaults to question.page_start)
        description: description for the new image
    """
    from apps.parser.models import ExamPage, QuestionImage

    paper = question.paper
    target_page_no = page_no or question.page_start
    if not target_page_no:
        raise ImageCropError("No page associated with this question")

    try:
        page = ExamPage.objects.get(paper=paper, page_no=target_page_no)
    except ExamPage.DoesNotExist:
        raise ImageCropError(f"Page {target_page_no} not found for paper {paper.id}")

    # Crop the image
    src_page_image = str(settings.MEDIA_ROOT / page.image_path)
    crop_dir = settings.MEDIA_ROOT / 'exams' / str(paper.id) / 'crops'

    if image_id:
        # Update existing image
        try:
            img = QuestionImage.objects.get(id=image_id, question=question)
        except QuestionImage.DoesNotExist:
            raise ImageCropError(f"Image {image_id} not found")

        # Generate new filename (reuse existing path pattern)
        crop_filename = f'q{question.id}_{img.sort_order}.png'
        crop_abs_path = str(crop_dir / crop_filename)

        cropped = crop_question_image(src_page_image, new_bbox, crop_abs_path)
        if not cropped:
            raise ImageCropError("Failed to crop image")

        rel_path = os.path.relpath(cropped, str(settings.MEDIA_ROOT))
        img.bbox = new_bbox
        img.file_path = rel_path
        img.source_page_image_path = page.image_path
        img.description = description
        img.save()
        return img
    else:
        # Create new image
        next_sort = QuestionImage.objects.filter(question=question).count()
        crop_filename = f'q{question.id}_{next_sort}.png'
        crop_abs_path = str(crop_dir / crop_filename)

        cropped = crop_question_image(src_page_image, new_bbox, crop_abs_path)
        if not cropped:
            raise ImageCropError("Failed to crop image")

        rel_path = os.path.relpath(cropped, str(settings.MEDIA_ROOT))
        img = QuestionImage.objects.create(
            paper=paper,
            question=question,
            page=page,
            image_type='diagram',
            file_path=rel_path,
            source_page_image_path=page.image_path,
            bbox=new_bbox,
            description=description,
            sort_order=next_sort,
        )
        return img


def add_question_image(question, bbox: list, page_no=None, description='人工添加'):
    """Add a new image to a question.

    Args:
        question: ExamQuestion instance
        bbox: [x1, y1, x2, y2] pixel coordinates
        page_no: page number to crop from
        description: description for the new image
    """
    return recrop_question_image(question, bbox, page_no=page_no, description=description)


def delete_question_image(image):
    """Delete a QuestionImage record and its file.

    Args:
        image: QuestionImage instance
    """
    # Delete file from disk
    if image.file_path:
        abs_path = str(settings.MEDIA_ROOT / image.file_path)
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
                logger.info(f'Deleted crop file: {abs_path}')
        except OSError as e:
            logger.warning(f'Failed to delete crop file {abs_path}: {e}')

    image.delete()
