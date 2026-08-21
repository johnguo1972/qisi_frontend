"""Photo-answer workflow for personal practice sets.

This module deliberately only touches PracticeAttempt and PracticeAttemptImage.
It must not enter the existing mission/answer-attempt grading pipeline.
"""
from __future__ import annotations

from pathlib import Path
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.media import media_url
from apps.qrcode.services import analyze_image_blur
from apps.parser.models import ExamQuestion

from .models import PracticeAttempt, PracticeAttemptImage, PracticeSet, PracticeSetItem
from .services import PracticeValidationError, refresh_set_progress, _uuid


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _get_set_item(*, student, set_id, set_item_id):
    practice_set = PracticeSet.objects.filter(pk=_uuid(set_id), student_user=student).first()
    if practice_set is None:
        raise PracticeValidationError('PRACTICE_SET_NOT_FOUND', '精练作业不存在')
    set_item = PracticeSetItem.objects.filter(
        pk=_uuid(set_item_id), practice_set=practice_set,
    ).first()
    if set_item is None:
        raise PracticeValidationError('SET_ITEM_NOT_FOUND', '题目不属于该精练作业')
    return practice_set, set_item


def _question_matches_item(set_item, question_id):
    if question_id in (None, ''):
        return
    if _uuid(question_id, code='INVALID_QUESTION_ID') != set_item.question_id:
        raise PracticeValidationError('QUESTION_MISMATCH', '题目与精练作业题目不一致')


@transaction.atomic
def create_photo_attempt(*, student, set_id, set_item_id, question_id=None):
    practice_set, set_item = _get_set_item(
        student=student, set_id=set_id, set_item_id=set_item_id,
    )
    _question_matches_item(set_item, question_id)
    if practice_set.status in {'completed', 'archived'}:
        raise PracticeValidationError('INVALID_SET_STATUS', '已完成或已归档的作业不能继续答题')

    last_no = PracticeAttempt.objects.filter(
        practice_set=practice_set, set_item=set_item,
    ).order_by('-attempt_no').values_list('attempt_no', flat=True).first() or 0
    attempt = PracticeAttempt.objects.create(
        practice_set=practice_set,
        set_item=set_item,
        student_user=student,
        answer_content={},
        submit_source='photo',
        attempt_no=last_no + 1,
        status='draft',
    )
    return practice_set, set_item, attempt


def _validate_image(image):
    if image is None:
        raise PracticeValidationError('IMAGE_REQUIRED', '缺少图片')
    content_type = str(getattr(image, 'content_type', '') or '').lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise PracticeValidationError('INVALID_IMAGE_TYPE', '仅支持 JPEG、PNG 或 WebP 图片')
    if int(getattr(image, 'size', 0) or 0) > MAX_IMAGE_BYTES:
        raise PracticeValidationError('IMAGE_TOO_LARGE', '图片大小不能超过 5MB')
    suffix = Path(str(getattr(image, 'name', '') or '')).suffix.lower()
    if suffix and suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise PracticeValidationError('INVALID_IMAGE_EXTENSION', '图片扩展名不受支持')


@transaction.atomic
def upload_photo(*, student, attempt_id, image, page_no):
    _validate_image(image)
    attempt = PracticeAttempt.objects.select_related('practice_set', 'set_item').filter(
        pk=_uuid(attempt_id), student_user=student,
    ).first()
    if attempt is None:
        raise PracticeValidationError('ATTEMPT_NOT_FOUND', '答题记录不存在')
    if attempt.status != 'draft':
        raise PracticeValidationError('ATTEMPT_NOT_DRAFT', '只有草稿答题记录可以上传图片')
    try:
        page_no = int(page_no)
    except (TypeError, ValueError):
        raise PracticeValidationError('INVALID_PAGE_NO', '页码必须是正整数')
    if page_no <= 0 or page_no > 30:
        raise PracticeValidationError('INVALID_PAGE_NO', '页码必须在 1 到 30 之间')
    if PracticeAttemptImage.objects.filter(attempt=attempt, page_no=page_no).exists():
        raise PracticeValidationError('DUPLICATE_PAGE', '该页图片已经上传，请更换页码')

    suffix = Path(str(getattr(image, 'name', '') or '')).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        suffix = '.jpg' if str(getattr(image, 'content_type', '')).lower() == 'image/jpeg' else f'.{str(getattr(image, "content_type", "image/png")).split("/")[-1]}'
    directory = Path(settings.MEDIA_ROOT) / 'practice_attempts' / str(attempt.id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f'{page_no}_{uuid.uuid4().hex}{suffix}'
    destination = directory / filename
    with destination.open('wb') as target:
        for chunk in image.chunks():
            target.write(chunk)

    blur_score, is_blurry = analyze_image_blur(image)
    record = PracticeAttemptImage.objects.create(
        attempt=attempt,
        student_user=student,
        image_path=f'practice_attempts/{attempt.id}/{filename}',
        page_no=page_no,
        blur_score=blur_score,
        is_blurry=is_blurry,
        upload_status='uploaded',
    )
    return attempt, record


@transaction.atomic
def submit_photo_attempt(*, student, attempt_id, answer_content=None):
    attempt = PracticeAttempt.objects.select_related('practice_set', 'set_item').filter(
        pk=_uuid(attempt_id), student_user=student,
    ).first()
    if attempt is None:
        raise PracticeValidationError('ATTEMPT_NOT_FOUND', '答题记录不存在')
    if attempt.status != 'draft':
        raise PracticeValidationError('ATTEMPT_NOT_DRAFT', '该答题记录已经提交')
    if not attempt.images.filter(upload_status='uploaded').exists():
        raise PracticeValidationError('IMAGE_REQUIRED', '请至少上传一张答题图片')
    if answer_content is not None and not isinstance(answer_content, dict):
        raise PracticeValidationError('INVALID_ANSWER_CONTENT', 'answer_content 必须是对象')

    attempt.answer_content = answer_content if isinstance(answer_content, dict) else {}
    attempt.submit_source = 'photo'
    attempt.is_correct = None
    attempt.is_subjective_pending = True
    attempt.score = None
    attempt.status = 'pending_review'
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=[
        'answer_content', 'submit_source', 'is_correct',
        'is_subjective_pending', 'score', 'status', 'submitted_at',
    ])
    refresh_set_progress(attempt.practice_set)
    return attempt.practice_set, attempt.set_item, attempt


def serialize_photo_image(record):
    return {
        'id': str(record.id),
        'page_no': record.page_no,
        'url': media_url(record.image_path),
        'blur_score': float(record.blur_score) if record.blur_score is not None else None,
        'is_blurry': record.is_blurry,
        'upload_status': record.upload_status,
        'created_at': record.created_at,
    }
