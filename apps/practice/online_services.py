"""Online practice services with no side effects outside the practice domain."""
from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from apps.parser.models import ExamQuestion

from .grading import AnswerFormatError, grade_question
from .models import PracticeAttempt, PracticeSet, PracticeSetItem
from .services import PracticeValidationError, refresh_set_progress


def _parse_uuid(value, code):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise PracticeValidationError(code, 'ID 格式不正确')


@transaction.atomic
def submit_online_attempt(*, student, set_id, set_item_id, question_id, answer_content):
    practice_set = PracticeSet.objects.select_for_update().filter(
        pk=_parse_uuid(set_id, 'INVALID_SET_ID'), student_user=student,
    ).first()
    if practice_set is None:
        raise PracticeValidationError('PRACTICE_SET_NOT_FOUND', '精练作业不存在')
    if practice_set.status != 'active':
        raise PracticeValidationError('PRACTICE_SET_NOT_ACTIVE', '只有进行中的精练作业可以答题')

    set_item = PracticeSetItem.objects.filter(
        pk=_parse_uuid(set_item_id, 'INVALID_SET_ITEM_ID'), practice_set=practice_set,
    ).first()
    if set_item is None:
        raise PracticeValidationError('SET_ITEM_NOT_FOUND', '精练作业题目不存在')
    submitted_question_id = _parse_uuid(question_id, 'INVALID_QUESTION_ID')
    if submitted_question_id != set_item.question_id:
        raise PracticeValidationError('QUESTION_MISMATCH', '提交题目与作业题目不一致')
    question = ExamQuestion.objects.filter(pk=set_item.question_id).first()
    if question is None:
        raise PracticeValidationError('QUESTION_NOT_FOUND', '题目不存在，无法判分')
    try:
        is_correct, is_pending = grade_question(question, answer_content)
    except AnswerFormatError as error:
        raise PracticeValidationError('INVALID_ANSWER_FORMAT', str(error))

    attempt_no = PracticeAttempt.objects.filter(
        practice_set=practice_set, set_item=set_item,
    ).count() + 1
    attempt = PracticeAttempt.objects.create(
        practice_set=practice_set,
        set_item=set_item,
        student_user=student,
        answer_content=answer_content,
        submit_source='online',
        attempt_no=attempt_no,
        is_correct=is_correct,
        is_subjective_pending=is_pending,
        score=None if is_pending else (100 if is_correct else 0),
        status='pending_review' if is_pending else 'submitted',
        submitted_at=timezone.now(),
    )
    refresh_set_progress(practice_set)
    return practice_set, set_item, attempt
