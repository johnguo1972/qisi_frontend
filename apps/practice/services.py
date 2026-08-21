"""Transactional services for the personal practice pool and sets."""
from __future__ import annotations

from copy import deepcopy
import uuid

from django.db import transaction
from django.utils import timezone

from apps.accounts.auth import get_request_role
from apps.parser.models import ExamQuestion
from apps.wrongbook.models import WrongBookItem

from .models import PracticeAttempt, PracticePoolItem, PracticeSet, PracticeSetItem
from .recommendation import (
    ALGORITHM_VERSION,
    QuestionBankWrongbookCandidateProvider,
    question_display,
)


MAX_SET_QUESTIONS = 50


class PracticeValidationError(Exception):
    def __init__(self, code, message, *, item_index=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.item_index = item_index


def _uuid(value, *, code='INVALID_UUID'):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise PracticeValidationError(code, 'ID 格式不正确')


def _wrong_item_for_student(student, value):
    wrong_item_id = _uuid(value, code='INVALID_WRONG_ITEM_ID')
    return WrongBookItem.objects.filter(pk=wrong_item_id, student_user_id=student).first()


def _question_for_pool(question_id):
    return (
        ExamQuestion.objects.select_related('paper').prefetch_related('images', 'options')
        .filter(pk=question_id, paper__is_deleted=False)
        .exclude(stem__isnull=True).exclude(stem='')
        .first()
    )


def _candidate_map(*, student, wrong_item):
    result = QuestionBankWrongbookCandidateProvider().recommend_for_wrong_item(
        student=student, wrong_item=wrong_item, limit=3,
    )
    return {item['id']: item for item in result['items']}, result['meta']


def _resolve_pool_item(*, student, payload, item_index):
    if not isinstance(payload, dict):
        raise PracticeValidationError(
            'INVALID_ITEM', 'items 中的每一项必须是对象', item_index=item_index
        )
    source_type = str(payload.get('source_type') or 'recommended_variant')
    if source_type not in {'original_wrong', 'recommended_variant', 'manual'}:
        raise PracticeValidationError(
            'INVALID_SOURCE_TYPE', '不支持的精练题来源类型', item_index=item_index
        )
    if source_type == 'manual':
        raise PracticeValidationError(
            'MANUAL_NOT_ALLOWED', '当前接口不允许直接添加手工题', item_index=item_index
        )

    question_id = _uuid(payload.get('question_id'), code='INVALID_QUESTION_ID')
    wrong_item = _wrong_item_for_student(student, payload.get('source_wrong_item_id'))
    if wrong_item is None:
        raise PracticeValidationError(
            'WRONG_ITEM_NOT_FOUND', '来源错题不存在或不属于当前学生', item_index=item_index
        )

    # An active duplicate is idempotent. The provider excludes active pool items.
    existing = PracticePoolItem.objects.filter(
        student_user=student, question_id=question_id,
    ).first()
    if existing and existing.status == 'active':
        return {
            'question_id': question_id,
            'wrong_item': wrong_item,
            'source_type': source_type,
            'existing': existing,
            'display_snapshot': existing.display_snapshot,
            'recommendation_snapshot': existing.recommendation_snapshot,
            'result_status': 'already_exists',
        }

    if source_type == 'original_wrong':
        if question_id != wrong_item.question_id:
            raise PracticeValidationError(
                'ORIGINAL_QUESTION_MISMATCH', '原错题来源只能添加该错题本身', item_index=item_index
            )
        question = _question_for_pool(question_id)
        if question is None:
            raise PracticeValidationError(
                'QUESTION_NOT_FOUND', '原题不存在、已删除或没有题干', item_index=item_index
            )
        display_snapshot = question_display(question)
        recommendation_snapshot = {
            'algorithm_version': ALGORITHM_VERSION,
            'source_type': source_type,
            'source_wrong_item_id': str(wrong_item.id),
        }
    else:
        candidates, meta = _candidate_map(student=student, wrong_item=wrong_item)
        candidate = candidates.get(str(question_id))
        if candidate is None:
            raise PracticeValidationError(
                'RECOMMENDATION_INVALID',
                '题目不属于当前错题的有效候选，或推荐结果已失效',
                item_index=item_index,
            )
        display_snapshot = candidate
        recommendation_snapshot = {
            'algorithm_version': meta['algorithm_version'],
            'source_type': source_type,
            'source_wrong_item_id': str(wrong_item.id),
            'match': deepcopy(candidate.get('match') or {}),
        }

    return {
        'question_id': question_id,
        'wrong_item': wrong_item,
        'source_type': source_type,
        'existing': existing,
        'display_snapshot': display_snapshot,
        'recommendation_snapshot': recommendation_snapshot,
        'result_status': 'restored' if existing else 'added',
    }


@transaction.atomic
def add_pool_items(*, student, items):
    if not isinstance(items, list) or not items:
        raise PracticeValidationError('INVALID_ITEMS', 'items 必须是非空数组')

    resolved = []
    seen = set()
    for index, payload in enumerate(items):
        item = _resolve_pool_item(student=student, payload=payload, item_index=index)
        if item['question_id'] in seen:
            raise PracticeValidationError(
                'DUPLICATE_REQUEST_ITEM', '请求中不能重复添加同一道题', item_index=index
            )
        seen.add(item['question_id'])
        resolved.append(item)

    results = []
    for item in resolved:
        existing = item['existing']
        if existing:
            if item['result_status'] == 'already_exists':
                results.append({'status': 'already_exists', 'item': existing})
                continue
            existing.status = 'active'
            existing.source_wrong_item = item['wrong_item']
            existing.source_type = item['source_type']
            existing.recommendation_snapshot = item['recommendation_snapshot']
            existing.display_snapshot = item['display_snapshot']
            existing.save()
            results.append({'status': 'restored', 'item': existing})
            continue
        created = PracticePoolItem.objects.create(
            student_user=student,
            question_id=item['question_id'],
            source_wrong_item=item['wrong_item'],
            source_type=item['source_type'],
            recommendation_snapshot=item['recommendation_snapshot'],
            display_snapshot=item['display_snapshot'],
            status='active',
        )
        results.append({'status': 'added', 'item': created})
    return results


@transaction.atomic
def remove_pool_item(*, student, item_id):
    item = PracticePoolItem.objects.filter(pk=_uuid(item_id), student_user=student).first()
    if item is None:
        raise PracticeValidationError('POOL_ITEM_NOT_FOUND', '精练题目不存在')
    if item.status == 'removed':
        return item, 'already_removed'
    item.status = 'removed'
    item.save(update_fields=['status', 'updated_at'])
    return item, 'removed'


@transaction.atomic
def batch_remove_pool_items(*, student, item_ids):
    if not isinstance(item_ids, list) or not item_ids:
        raise PracticeValidationError('INVALID_ITEM_IDS', 'item_ids 必须是非空数组')
    ids = []
    for value in item_ids:
        parsed = _uuid(value)
        if parsed not in ids:
            ids.append(parsed)
    found = list(PracticePoolItem.objects.filter(student_user=student, pk__in=ids))
    found_by_id = {item.id: item for item in found}
    if len(found_by_id) != len(ids):
        raise PracticeValidationError('POOL_ITEM_NOT_FOUND', '存在不属于当前学生的精练题目')
    changed = []
    for item in found:
        if item.status != 'removed':
            item.status = 'removed'
            item.save(update_fields=['status', 'updated_at'])
            changed.append(item)
    return found, changed


def refresh_set_progress(practice_set):
    answered_ids = PracticeAttempt.objects.filter(
        practice_set=practice_set,
        status__in=('submitted', 'pending_review', 'graded'),
    ).values_list('set_item_id', flat=True).distinct()
    answered_count = answered_ids.count()
    question_count = practice_set.question_count
    progress = (answered_count * 100 / question_count) if question_count else 0
    changed = (
        practice_set.answered_count != answered_count
        or practice_set.progress_percent != progress
    )
    practice_set.answered_count = answered_count
    practice_set.progress_percent = progress
    if changed:
        practice_set.save(update_fields=['answered_count', 'progress_percent', 'updated_at'])
    return practice_set


@transaction.atomic
def create_practice_set(*, request, student, title, pool_item_ids, status='draft'):
    if not isinstance(pool_item_ids, list) or not pool_item_ids:
        raise PracticeValidationError('INVALID_POOL_ITEMS', 'pool_item_ids 必须是非空数组')
    if len(pool_item_ids) > MAX_SET_QUESTIONS:
        raise PracticeValidationError('TOO_MANY_QUESTIONS', f'精练作业最多包含{MAX_SET_QUESTIONS}道题')
    if status not in {'draft', 'active'}:
        raise PracticeValidationError('INVALID_SET_STATUS', '作业初始状态只能是 draft 或 active')

    parsed_ids = []
    for value in pool_item_ids:
        parsed = _uuid(value, code='INVALID_POOL_ITEM_ID')
        if parsed in parsed_ids:
            raise PracticeValidationError('DUPLICATE_POOL_ITEM', '作业中不能重复添加同一道精练题')
        parsed_ids.append(parsed)
    pool_items = list(PracticePoolItem.objects.filter(
        student_user=student, status='active', pk__in=parsed_ids,
    ))
    by_id = {item.id: item for item in pool_items}
    if len(by_id) != len(parsed_ids):
        raise PracticeValidationError('POOL_ITEM_NOT_FOUND', '存在无效、已移除或不属于当前学生的精练题目')

    active_role = get_request_role(request)
    practice_set = PracticeSet.objects.create(
        student_user=student,
        created_by_user=request.user,
        created_via_role='parent' if active_role == 'parent' else 'student',
        title=(str(title or '').strip() or f'错题精练-{timezone.localdate()}')[:200],
        status=status,
        question_count=len(parsed_ids),
        answered_count=0,
        progress_percent=0,
        pdf_version=1,
    )
    PracticeSetItem.objects.bulk_create([
        PracticeSetItem(
            practice_set=practice_set,
            pool_item=by_id[item_id],
            question_id=by_id[item_id].question_id,
            sort_no=index,
            source_type=by_id[item_id].source_type,
            display_snapshot=deepcopy(by_id[item_id].display_snapshot),
        )
        for index, item_id in enumerate(parsed_ids, start=1)
    ])
    return practice_set


@transaction.atomic
def activate_practice_set(*, practice_set):
    if practice_set.status in {'completed', 'archived'}:
        raise PracticeValidationError('INVALID_SET_TRANSITION', '已完成或已归档的作业不能重新激活')
    if practice_set.status != 'active':
        practice_set.status = 'active'
        practice_set.save(update_fields=['status', 'updated_at'])
    return practice_set


@transaction.atomic
def submit_practice_set(*, practice_set):
    refresh_set_progress(practice_set)
    if practice_set.status == 'completed':
        return practice_set
    if practice_set.status == 'archived':
        raise PracticeValidationError('INVALID_SET_TRANSITION', '已归档的作业不能提交')
    if practice_set.answered_count < practice_set.question_count:
        raise PracticeValidationError('PRACTICE_SET_INCOMPLETE', '作业尚未完成全部题目')
    practice_set.status = 'completed'
    practice_set.completed_at = timezone.now()
    practice_set.save(update_fields=['status', 'completed_at', 'updated_at'])
    return practice_set
