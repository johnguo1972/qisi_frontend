"""Teacher-selected fallback for wrong-book practice generation.

The legacy wrong-book generation and AI supplement endpoints stay in
``wrongbook_matrix.py``.  This module only owns the optional teacher-select
workflow used when automatic recommendations are missing or insufficient.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.parser.models import ExamQuestion
from apps.practice.recommendation import (
    knowledge_point_keys,
    normalize_stage,
    question_display,
)
from apps.study.models import QuestionRelation

from .models import (
    LearningMission,
    RelatedQuestionRecommendation,
    TeacherWrongBookCell,
    WrongBookGenerationBatch,
    WrongBookGenerationItem,
)
from .wrongbook_matrix import (
    MatrixError,
    _audit,
    _create_published_mission,
    _sid,
    publish_generated_mission,
)


def _selected_count(limit, candidate_count):
    return min(int(limit), int(candidate_count))


def _validate_generation_request(matrix, version, idempotency_key, cell_ids=None):
    if not idempotency_key:
        raise MatrixError('idempotency_key 必填', 'invalid')
    if int(version) != matrix.version:
        raise MatrixError(
            '矩阵版本已变化，请刷新后重试', 'version_conflict', 409,
            {'current_version': matrix.version},
        )
    if matrix.status in ('closed', 'scope_changed'):
        raise MatrixError('矩阵范围已变化或已关闭，请先查看历史或刷新范围', 'conflict', 409)
    if cell_ids:
        requested = [str(value) for value in cell_ids]
        selected = list(matrix.cells.filter(id__in=requested).select_related('student', 'wrong_book_item'))
        by_id = {str(cell.id): cell for cell in selected}
        invalid = [value for value in requested if value not in by_id or by_id[value].status != 'marked']
        if invalid:
            raise MatrixError('只能生成当前状态为 marked 的矩阵单元格', 'cell_conflict', 409, {'cell_ids': invalid})
        cells = [by_id[value] for value in dict.fromkeys(requested)]
    else:
        cells = list(matrix.cells.filter(status='marked').select_related('student', 'wrong_book_item'))
    if not cells:
        raise MatrixError('没有可生成的已标记错题', 'no_marked_cells')
    return cells, sorted(str(cell.id) for cell in cells)


@transaction.atomic
def request_teacher_generation(matrix, teacher, version, idempotency_key, cell_ids=None, trace_id=''):
    cells, requested_ids = _validate_generation_request(matrix, version, idempotency_key, cell_ids)
    batch = WrongBookGenerationBatch.objects.filter(matrix=matrix, idempotency_key=idempotency_key).first()
    if batch:
        if batch.request_version != int(version) or sorted(batch.request_cell_ids or []) != requested_ids:
            raise MatrixError('相同幂等键不能用于不同版本或不同单元格集合', 'idempotency_conflict', 409)
        return batch
    batch = WrongBookGenerationBatch.objects.create(
        matrix=matrix,
        requested_by=teacher,
        request_version=matrix.version,
        request_cell_ids=requested_ids,
        related_limit=3,
        generation_mode='teacher_select',
        candidate_limit=10,
        selection_limit=3,
        requested_count=len(cells),
        idempotency_key=idempotency_key,
    )
    WrongBookGenerationItem.objects.bulk_create([
        WrongBookGenerationItem(
            batch=batch,
            cell=cell,
            student_id=cell.student_id,
            source_question_id=cell.source_question_id,
            source_wrong_book_item_id=cell.wrong_book_item_id,
        )
        for cell in cells
    ])
    matrix.status = 'generating'
    matrix.last_generation_batch_id = batch.id
    matrix.save(update_fields=['status', 'last_generation_batch_id', 'updated_at'])
    _audit(matrix, teacher, 'generation_requested', trace_id, batch=batch, payload={
        'cell_count': len(cells), 'generation_mode': 'teacher_select',
    })
    from .tasks import generate_teacher_wrongbook_batch_task
    transaction.on_commit(lambda: generate_teacher_wrongbook_batch_task.delay(str(batch.id)))
    return batch


MANUAL_CANDIDATE_PROVIDERS = ('relation', 'criteria')
CRITERIA_CANDIDATE_LIMIT = 5


def _difficulty_coefficient(value):
    try:
        coefficient = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return coefficient if coefficient.is_finite() else None


def _relation_candidates(item):
    """Return explicit question relations for the original wrong question."""
    original_id = _sid(item.source_question_id)
    relations = QuestionRelation.for_question(item.source_question_id).order_by('created_at', 'id')
    related_ids = []
    for relation in relations:
        related_id = relation.question_right_id if _sid(relation.question_left_id) == original_id else relation.question_left_id
        related_id = _sid(related_id)
        if related_id not in related_ids:
            related_ids.append(related_id)
    if not related_ids:
        return []
    by_id = {
        _sid(question.id): question
        for question in ExamQuestion.objects.filter(pk__in=related_ids)
        .select_related('paper').prefetch_related('images', 'options')
    }
    return [question_display(by_id[question_id]) for question_id in related_ids if question_id in by_id]


def _criteria_candidates(item, excluded_ids=None, limit=CRITERIA_CANDIDATE_LIMIT):
    """Select question-bank candidates using the teacher-approved criteria."""
    excluded = {_sid(value) for value in (excluded_ids or [])}
    original = ExamQuestion.objects.select_related('paper').filter(pk=item.source_question_id).first()
    if original is None:
        return []
    original_stage = normalize_stage(getattr(original.paper, 'stage', None))
    original_difficulty = _difficulty_coefficient(original.difficulty)
    original_points = knowledge_point_keys(original.knowledge_points)
    if not original.subject or not original_stage or original_difficulty is None or not original_points:
        return []
    query = ExamQuestion.objects.filter(
        paper__is_deleted=False,
        review_status__in=('reviewed', 'confirmed'),
        need_review=False,
        subject=original.subject,
    ).exclude(pk=original.id).exclude(stem__isnull=True).exclude(stem='')
    ranked = []
    for question in query.select_related('paper').prefetch_related('images', 'options'):
        question_id = _sid(question.id)
        if question_id in excluded:
            continue
        if normalize_stage(getattr(question.paper, 'stage', None)) != original_stage:
            continue
        difficulty = _difficulty_coefficient(question.difficulty)
        if difficulty is None or abs(difficulty - original_difficulty) > Decimal('0.5'):
            continue
        if not (original_points & knowledge_point_keys(question.knowledge_points)):
            continue
        ranked.append((abs(difficulty - original_difficulty), question.sort_order, question_id, question))
    ranked.sort(key=lambda row: row[:3])
    return [question_display(question) for _, _, _, question in ranked[:limit]]


def _upsert_candidate(batch, item, candidate, provider, rank, reason=''):
    candidate_id = candidate['id']
    defaults = {
        'provider': provider,
        'model_name': 'teacher-question-relation' if provider == 'relation' else 'teacher-question-criteria',
        'prompt_version': 'teacher-select-v2',
        'score': max(0, 1 - rank / 10),
        'confidence': max(0, 1 - rank / 10),
        'requested_by': batch.requested_by,
        'result_json': {'candidate': candidate, 'fallback_reason': reason, 'rank': rank + 1},
    }
    rec, created = RelatedQuestionRecommendation.objects.get_or_create(
        matrix=batch.matrix,
        source_batch=batch,
        source_student_id=item.student_id,
        source_question_id=item.source_question_id,
        source_wrong_book_item_id=item.source_wrong_book_item_id,
        candidate_question_id=candidate_id,
        defaults=defaults,
    )
    if not created and rec.status == 'suggested':
        for field, value in defaults.items():
            setattr(rec, field, value)
        rec.save(update_fields=[*defaults.keys(), 'updated_at'])
    return rec


def _candidate_payload(rec):
    return {
        'recommendation_id': str(rec.id),
        'candidate_question_id': str(rec.candidate_question_id),
        'provider': rec.provider,
        'status': rec.status,
        'candidate': (rec.result_json or {}).get('candidate') or {},
        'fallback_reason': (rec.result_json or {}).get('fallback_reason') or '',
        'rank': (rec.result_json or {}).get('rank'),
    }


def _legacy_teacher_candidate_groups(batch):
    groups = []
    items = batch.items.select_related('student', 'source_wrong_book_item').filter(selection_required=True).order_by('student_id', 'source_question_id')
    for item in items:
        recs = list(batch.recommendations.filter(
            source_student_id=item.student_id,
            source_question_id=item.source_question_id,
            source_wrong_book_item_id=item.source_wrong_book_item_id,
        ).order_by('score', 'id'))
        recs.sort(key=lambda rec: ((rec.result_json or {}).get('rank') or 999, str(rec.id)))
        groups.append({
            'item_id': str(item.id),
            'student_id': str(item.student_id),
            'student_name': item.student.display_name,
            'source_wrong_book_item_id': str(item.source_wrong_book_item_id),
            'source_question_id': str(item.source_question_id),
            'source_question_no': (item.result_json or {}).get('source_question_no', ''),
            'source_question': (item.result_json or {}).get('source_question') or {},
            'reason': (item.result_json or {}).get('selection_reason', 'no_related_question'),
            'reason_label': (item.result_json or {}).get('selection_reason_label', '暂无有效关联题，请手动选择'),
            'candidate_source': 'question_bank',
            'selection_limit': batch.selection_limit,
            'candidates': [_candidate_payload(rec) for rec in recs[:batch.candidate_limit]],
        })
    return groups


def _manual_candidates(batch, item, excluded_ids=None):
    """Prefer established relations; use deterministic criteria only if none exist."""
    related = _relation_candidates(item)
    if related:
        provider, candidates, reason = 'relation', related, 'existing_relations'
    else:
        provider, candidates, reason = 'criteria', _criteria_candidates(item, excluded_ids), 'criteria_match'
    recs = [_upsert_candidate(batch, item, candidate, provider, rank, reason) for rank, candidate in enumerate(candidates)]
    return provider, recs


def _candidate_group_payload(batch, item, recs, provider, excluded_ids=None):
    displayed_ids = {_sid(rec.candidate_question_id) for rec in recs}
    has_more = False
    if provider == 'criteria':
        next_candidates = _criteria_candidates(item, set(excluded_ids or []) | displayed_ids, limit=1)
        has_more = bool(next_candidates)
    meta = item.result_json or {}
    return {
        'item_id': str(item.id),
        'student_id': str(item.student_id),
        'student_name': item.student.display_name,
        'source_wrong_book_item_id': str(item.source_wrong_book_item_id),
        'source_question_id': str(item.source_question_id),
        'source_question_no': meta.get('source_question_no', ''),
        'source_question': meta.get('source_question') or {},
        'reason': 'existing_relations' if provider == 'relation' else 'criteria_match',
        'reason_label': '已加载本题已建立的关联题，请选择同类题。' if provider == 'relation' else '未建立关联题，已按相同知识点、同学段同学科和难度系数正负 0.5 筛选。',
        'candidate_source': provider,
        'selection_limit': batch.selection_limit,
        'has_more': has_more,
        'candidates': [_candidate_payload(rec) for rec in recs],
    }


def teacher_candidate_groups(batch):
    groups = []
    items = batch.items.select_related('student', 'source_wrong_book_item').filter(selection_required=True).order_by('student_id', 'source_question_id')
    for item in items:
        provider, recs = _manual_candidates(batch, item)
        groups.append(_candidate_group_payload(batch, item, recs, provider))
    return groups


def next_teacher_candidate_group(batch, item_id, excluded_ids=None):
    if batch.generation_mode != 'teacher_select' or batch.status != 'awaiting_selection':
        raise MatrixError('当前批次不支持更换候选题。', 'conflict', 409)
    item = batch.items.select_related('student', 'source_wrong_book_item').filter(pk=item_id, selection_required=True).first()
    if item is None:
        raise MatrixError('待选择错题不存在或已完成。', 'not_found', 404)
    excluded = {_sid(value) for value in (excluded_ids or [])}
    provider, recs = _manual_candidates(batch, item, excluded)
    if provider != 'criteria':
        raise MatrixError('本题已有关联题，无需更换候选题。', 'conflict', 409)
    if not recs:
        raise MatrixError('没有更多符合条件的同类题。', 'no_more_candidates', 409)
    return _candidate_group_payload(batch, item, recs, provider, excluded)


def _source_snapshot(batch, item):
    row = batch.matrix.questions.filter(source_question_id=item.source_question_id, status='active').first()
    if row is None:
        raise MatrixError('原题快照不存在', 'snapshot_failed')
    return row.question_snapshot, row.question_no_snapshot


def _selection_row(batch, item, selected_ids, provider_by_id):
    original_snapshot, _ = _source_snapshot(batch, item)
    related = []
    for candidate_id in selected_ids:
        question = ExamQuestion.objects.filter(pk=candidate_id).prefetch_related('images', 'options').first()
        if question is None:
            raise MatrixError('所选同类题已不存在', 'not_found', 404)
        related.append({'id': str(question.id), **question_display(question)})
    return {
        'student_id': item.student_id,
        'source_question_id': item.source_question_id,
        'wrong_book_item_id': item.source_wrong_book_item_id,
        'original_snapshot': original_snapshot,
        'related': related,
        'provider': provider_by_id or 'rule',
    }


def _finish_batch(batch, mission, items, failed=0):
    WrongBookGenerationItem.objects.filter(batch=batch, status='generated').update(
        target_mission=mission, status='published', selection_required=False,
    )
    TeacherWrongBookCell.objects.filter(
        matrix=batch.matrix, id__in=[item.cell_id for item in items if item.status == 'generated'],
    ).update(status='generated', generated_batch_id=batch.id)
    batch.generated_count = len(items) - failed
    batch.failed_count = failed
    batch.published_task_count = 1 if mission and mission.status == 'published' else 0
    batch.final_mission_id = mission.id if mission else None
    batch.status = 'partially_failed' if failed else ('published' if mission else 'failed')
    batch.completed_at = timezone.now()
    batch.save(update_fields=[
        'generated_count', 'failed_count', 'published_task_count', 'final_mission_id',
        'status', 'completed_at',
    ])
    batch.matrix.last_generation_batch_id = batch.id
    batch.matrix.generated_count = batch.matrix.cells.filter(status='generated').count()
    batch.matrix.failed_count = failed
    batch.matrix.status = 'partially_failed' if failed else ('generated' if mission else 'saved')
    batch.matrix.save(update_fields=['last_generation_batch_id', 'generated_count', 'failed_count', 'status', 'updated_at'])


def _legacy_generate_teacher_batch(batch_id, trace_id=''):
    batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
    if batch.generation_mode != 'teacher_select':
        raise MatrixError('该批次不是教师选择模式', 'conflict', 409)
    if batch.status in ('published', 'partially_failed') and batch.final_mission_id:
        return batch
    batch.status = 'generating'
    batch.started_at = timezone.now()
    batch.save(update_fields=['status', 'started_at'])
    items = list(batch.items.select_related('student', 'source_wrong_book_item'))
    ai_by_key = {}
    ai_error = ''
    try:
        ai_recs = batch_recommendations(
            batch, batch.requested_by, batch.selection_limit, trace_id,
            allow_unpublished=True,
        )
        for rec in ai_recs:
            ai_by_key.setdefault((str(rec.source_student_id), str(rec.source_wrong_book_item_id)), []).append(rec)
    except Exception as exc:
        ai_error = str(exc)[:255]

    selections = []
    needs_selection = False
    failed = 0
    for item in items:
        try:
            item.status = 'generating'
            item.save(update_fields=['status', 'updated_at'])
            source_snapshot, source_question_no = _source_snapshot(batch, item)
            key = (str(item.student_id), str(item.source_wrong_book_item_id))
            ai_recs_for_item = ai_by_key.get(key, [])
            ai_recs_for_item = [rec for rec in ai_recs_for_item if rec.status == 'suggested']
            ai_ids = [str(rec.candidate_question_id) for rec in ai_recs_for_item]
            if len(ai_recs_for_item) >= batch.selection_limit:
                selected_ids = ai_ids[:batch.selection_limit]
                item.related_question_ids = selected_ids
                item.selected_question_ids = selected_ids
                item.selected_count = len(selected_ids)
                item.selection_required = False
                item.result_json = {
                    'source_question_no': source_question_no,
                    'source_question': source_snapshot,
                    'selection_reason': '',
                    'automatic_source': 'ai',
                }
                item.status = 'generated'
                item.save(update_fields=[
                    'related_question_ids', 'selected_question_ids', 'selected_count',
                    'selection_required', 'result_json', 'status', 'updated_at',
                ])
                selections.append(_selection_row(batch, item, selected_ids, 'ai'))
                continue

            candidates, meta = _fallback_candidates(item, batch.candidate_limit, ai_ids)
            all_ids = list(ai_ids)
            for rank, candidate in enumerate(candidates, start=len(all_ids)):
                candidate_id = str(candidate['id'])
                if candidate_id in all_ids:
                    continue
                _upsert_candidate(batch, item, candidate, 'rule', rank, 'ai_insufficient' if ai_recs_for_item else 'no_related_question')
                all_ids.append(candidate_id)
            reason = 'ai_failed' if ai_error else ('ai_insufficient' if ai_recs_for_item else 'no_related_question')
            reason_label = {
                'ai_failed': 'AI推荐失败，请手动选择同类题',
                'ai_insufficient': f'AI推荐不足{batch.selection_limit}道，请手动选择同类题',
                'no_related_question': '暂无有效关联题，请手动选择同类题',
            }[reason]
            item.related_question_ids = all_ids[:batch.candidate_limit]
            item.selected_question_ids = []
            item.selected_count = 0
            item.selection_required = True
            item.shortage_reason = meta.get('insufficient_reason') or ''
            item.result_json = {
                'source_question_no': source_question_no,
                'source_question': source_snapshot,
                'selection_reason': reason,
                'selection_reason_label': reason_label,
                'candidate_count': len(all_ids),
                'ai_count': len(ai_recs_for_item),
                'ai_error': ai_error,
            }
            item.status = 'generated'
            item.save(update_fields=[
                'related_question_ids', 'selected_question_ids', 'selected_count',
                'selection_required', 'shortage_reason', 'result_json', 'status', 'updated_at',
            ])
            needs_selection = True
        except Exception as exc:
            failed += 1
            item.status = 'failed'
            item.error_code = getattr(exc, 'code', 'generation_error')
            item.error_stage = 'candidate'
            item.error_message = str(exc)[:500]
            item.save(update_fields=['status', 'error_code', 'error_stage', 'error_message', 'updated_at'])

    if needs_selection:
        batch.status = 'awaiting_selection'
        batch.generated_count = len(items) - failed
        batch.failed_count = failed
        batch.completed_at = timezone.now()
        batch.error_json = {'code': 'teacher_selection_required', 'message': '部分错题需要教师选择同类题'}
        batch.save(update_fields=['status', 'generated_count', 'failed_count', 'completed_at', 'error_json'])
        batch.matrix.status = 'saved'
        batch.matrix.failed_count = failed
        batch.matrix.save(update_fields=['status', 'failed_count', 'updated_at'])
        return batch

    try:
        batch.status = 'snapshotting'
        batch.save(update_fields=['status'])
        mission = _create_published_mission(batch.matrix.source_mission, batch.matrix, batch, selections)
        if mission is None:
            raise MatrixError('无法生成错题练习作业', 'publish_error')
        publish_generated_mission(mission)
        _finish_batch(batch, mission, items, failed)
    except Exception as exc:
        batch.error_json = {'code': 'publish_error', 'message': str(exc)[:500]}
        batch.status = 'partially_failed' if failed else 'failed'
        batch.failed_count = failed + 1
        batch.completed_at = timezone.now()
        batch.save(update_fields=['error_json', 'status', 'failed_count', 'completed_at'])
    return batch


def generate_teacher_batch(batch_id, trace_id=''):
    """Create a teacher-selection batch without AI recommendations or rule fallback."""
    batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
    if batch.generation_mode != 'teacher_select':
        raise MatrixError('该批次不是教师选择模式。', 'conflict', 409)
    if batch.status in ('published', 'partially_failed') and batch.final_mission_id:
        return batch
    batch.status = 'generating'
    batch.started_at = timezone.now()
    batch.save(update_fields=['status', 'started_at'])
    items = list(batch.items.select_related('student', 'source_wrong_book_item'))
    failed = 0
    for item in items:
        try:
            item.status = 'generating'
            item.save(update_fields=['status', 'updated_at'])
            source_snapshot, source_question_no = _source_snapshot(batch, item)
            provider, recs = _manual_candidates(batch, item)
            candidate_ids = [_sid(rec.candidate_question_id) for rec in recs]
            item.related_question_ids = candidate_ids
            item.selected_question_ids = []
            item.selected_count = 0
            item.selection_required = True
            item.shortage_reason = '' if candidate_ids else 'no_manual_candidates'
            item.result_json = {
                'source_question_no': source_question_no,
                'source_question': source_snapshot,
                'selection_reason': 'existing_relations' if provider == 'relation' else 'criteria_match',
                'selection_reason_label': '已加载本题已建立的关联题，请选择同类题。' if provider == 'relation' else '未建立关联题，已按相同知识点、同学段同学科和难度系数正负 0.5 筛选。',
                'candidate_count': len(candidate_ids),
                'candidate_source': provider,
            }
            item.status = 'generated'
            item.save(update_fields=[
                'related_question_ids', 'selected_question_ids', 'selected_count',
                'selection_required', 'shortage_reason', 'result_json', 'status', 'updated_at',
            ])
        except Exception as exc:
            failed += 1
            item.status = 'failed'
            item.error_code = getattr(exc, 'code', 'generation_error')
            item.error_stage = 'candidate'
            item.error_message = str(exc)[:500]
            item.save(update_fields=['status', 'error_code', 'error_stage', 'error_message', 'updated_at'])
    batch.status = 'awaiting_selection'
    batch.generated_count = len(items) - failed
    batch.failed_count = failed
    batch.completed_at = timezone.now()
    batch.error_json = {'code': 'teacher_selection_required', 'message': '请为每道错题选择同类题。'}
    batch.save(update_fields=['status', 'generated_count', 'failed_count', 'completed_at', 'error_json'])
    batch.matrix.status = 'saved'
    batch.matrix.failed_count = failed
    batch.matrix.save(update_fields=['status', 'failed_count', 'updated_at'])
    return batch


@transaction.atomic
def confirm_teacher_selection(batch, teacher, groups, idempotency_key='', trace_id=''):
    if batch.generation_mode != 'teacher_select':
        raise MatrixError('该批次不是教师选择模式', 'conflict', 409)
    if idempotency_key and batch.teacher_selection_confirmation_key == idempotency_key and batch.final_mission_id:
        return LearningMission.objects.get(pk=batch.final_mission_id)
    if batch.status != 'awaiting_selection':
        raise MatrixError('当前批次不需要教师选择', 'conflict', 409)
    if not isinstance(groups, list):
        raise MatrixError('groups 必须是数组', 'invalid')
    item_map = {
        (str(item.student_id), str(item.source_wrong_book_item_id)): item
        for item in batch.items.filter(selection_required=True)
    }
    submitted = {}
    for group in groups:
        if not isinstance(group, dict):
            raise MatrixError('选择分组格式错误', 'invalid')
        key = (str(group.get('student_id')), str(group.get('source_wrong_book_item_id')))
        if key in submitted:
            raise MatrixError('同一学生的同一道错题不能重复提交', 'invalid')
        item = item_map.get(key)
        if item is None:
            raise MatrixError('选择分组不属于当前批次', 'scope_conflict', 409)
        ids = [str(value) for value in (group.get('candidate_question_ids') or [])]
        if len(ids) != len(set(ids)):
            raise MatrixError('同一分组不能重复选择题目', 'invalid')
        available = set(batch.recommendations.filter(
            source_student_id=item.student_id,
            source_question_id=item.source_question_id,
            source_wrong_book_item_id=item.source_wrong_book_item_id,
            status='suggested',
            provider__in=MANUAL_CANDIDATE_PROVIDERS,
        ).values_list('candidate_question_id', flat=True))
        available = {_sid(value) for value in available}
        required = _selected_count(batch.selection_limit, len(available))
        if not ids or len(ids) != required or not set(ids).issubset(available):
            raise MatrixError(
                f'学生{item.student.display_name}的第{item.result_json.get("source_question_no", "")}题请选择{required}道有效同类题',
                'selection_invalid', 409,
            )
        submitted[key] = ids
    if set(submitted) != set(item_map):
        raise MatrixError('请完成所有需要人工选择的错题', 'selection_incomplete', 409)

    selections = []
    items = list(batch.items.select_related('student', 'source_wrong_book_item').order_by('created_at'))
    for item in items:
        key = (str(item.student_id), str(item.source_wrong_book_item_id))
        selected_ids = submitted[key] if item.selection_required else [str(value) for value in item.selected_question_ids]
        if item.selection_required:
            provider = batch.recommendations.filter(
                source_student_id=item.student_id,
                source_question_id=item.source_question_id,
                source_wrong_book_item_id=item.source_wrong_book_item_id,
                candidate_question_id__in=selected_ids,
                provider__in=MANUAL_CANDIDATE_PROVIDERS,
            ).values_list('provider', flat=True).first() or 'criteria'
        else:
            provider = 'criteria'
        selections.append(_selection_row(batch, item, selected_ids, provider))
        item.selected_question_ids = selected_ids
        item.related_question_ids = selected_ids
        item.selected_count = len(selected_ids)
        item.selection_required = False
        item.save(update_fields=['selected_question_ids', 'related_question_ids', 'selected_count', 'selection_required', 'updated_at'])
    mission = _create_published_mission(batch.matrix.source_mission, batch.matrix, batch, selections)
    if mission is None:
        raise MatrixError('无法生成错题练习作业', 'publish_error')
    publish_generated_mission(mission)
    selected_ids = [candidate_id for values in submitted.values() for candidate_id in values]
    batch.recommendations.filter(candidate_question_id__in=selected_ids, status='suggested').update(
        status='teacher_selected', confirmed_by=teacher,
    )
    batch.teacher_selection_confirmation_key = idempotency_key or ''
    batch.final_mission_id = mission.id
    batch.status = 'published'
    batch.generated_count = len(items)
    batch.published_task_count = 1
    batch.completed_at = timezone.now()
    batch.save(update_fields=[
        'teacher_selection_confirmation_key', 'final_mission_id', 'status',
        'generated_count', 'published_task_count', 'completed_at',
    ])
    WrongBookGenerationItem.objects.filter(batch=batch).update(target_mission=mission, status='published')
    TeacherWrongBookCell.objects.filter(
        matrix=batch.matrix, id__in=list(batch.items.values_list('cell_id', flat=True)),
    ).update(status='generated', generated_batch_id=batch.id)
    batch.matrix.last_generation_batch_id = batch.id
    batch.matrix.generated_count = batch.matrix.cells.filter(status='generated').count()
    batch.matrix.failed_count = 0
    batch.matrix.status = 'generated'
    batch.matrix.save(update_fields=['last_generation_batch_id', 'generated_count', 'failed_count', 'status', 'updated_at'])
    _audit(batch.matrix, teacher, 'recommendation_confirmed', trace_id, batch=batch, payload={
        'mode': 'teacher_select', 'group_count': len(groups), 'mission_id': str(mission.id),
    })
    return mission
