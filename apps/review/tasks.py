"""Celery tasks for single question AI processing."""
import json
import logging
import uuid
from collections import Counter
from copy import deepcopy
from decimal import Decimal

from celery import chord, group
from celery import shared_task
from django.conf import settings
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from apps.common.ai_service import AIReviewService, create_ai_review_service
from apps.common.ai.question_context import (
    QuestionContextBuilder,
    question_context_hash,
)
from apps.parser.models import ExamQuestion
from .ai_mode_dispatch import release_single_mode_ai_task_lock
from .ai_queue import dispatch_queued_ai_items, recover_stale_ai_items

logger = logging.getLogger(__name__)

PROGRESS_KEY_PREFIX = 'single_ai_progress:'
COURSE_RECONCILE_KEY_PREFIX = 'course_ai_reconcile:'
COURSE_RECONCILE_STATUS_TTL = 7 * 24 * 60 * 60
_ARBITRATION_FAILURE_STAGES = frozenset({
    'baseline_invalid',
    'qwen_generate',
    'qwen_structure_repair',
    'deepseek_independent',
    'deepseek_final_review',
})


def _unanswered_baseline_from_verifier(value):
    """Return a usable persisted no-answer baseline without exposing raw AI data."""
    if not isinstance(value, dict):
        return None
    baseline = value.get('unanswered_baseline')
    if not isinstance(baseline, dict):
        return None
    if not all(
        isinstance(baseline.get(key), str) and baseline[key].strip()
        for key in ('canonical_answer', 'canonical_analysis')
    ):
        return None
    return dict(baseline)


def _question_has_no_source_answer(question) -> bool:
    if not hasattr(question, 'answer'):
        # Lightweight compatibility callers may intentionally omit this field;
        # only a persisted blank answer opts into the DeepSeek baseline flow.
        return False
    answer = getattr(question, 'answer', None)
    return answer is None or (isinstance(answer, str) and not answer.strip())


def classify_ai_failure(error: BaseException) -> str:
    """Return a stable, non-sensitive category for durable AI task telemetry."""
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        stage = getattr(current, 'stage', None)
        if stage in _ARBITRATION_FAILURE_STAGES:
            return stage
        message = str(current).lower()
        if message in _ARBITRATION_FAILURE_STAGES:
            return message
        if '429' in message or 'rate limit' in message or 'rate_limited' in message:
            return 'rate_limited'
        if 'connecttimeout' in message or 'connect timeout' in message:
            return 'connect_timeout'
        if 'timeout' in message or 'timed out' in message:
            return 'read_timeout'
        if any(marker in message for marker in ('schema', 'json', 'validation')):
            return 'schema_invalid'
        if 'baseline_invalid' in message:
            return 'baseline_invalid'
        if any(marker in message for marker in ('not configured', 'configuration', 'api key')):
            return 'configuration_error'
        if any(marker in message for marker in ('500', '502', '503', '504', 'unavailable')):
            return 'provider_unavailable'
        current = current.__cause__
    return 'unknown_error'


def _valid_ai_payload(value) -> bool:
    return isinstance(value, dict) and bool(value) and not value.get('error')


def is_ai_probe_complete(question) -> bool:
    """Accept controlled probes while keeping historic persisted probes usable."""
    probe = getattr(question, 'ai_probe_result', None)
    if not _valid_ai_payload(probe):
        return False
    taxonomy = probe.get('taxonomy')
    scope = taxonomy.get('scope') if isinstance(taxonomy, dict) else None
    if _valid_ai_payload(scope):
        required_fields = (
            'subject', 'question_type', 'normalized_text', 'difficulty_level',
        )
    elif isinstance(taxonomy, dict):
        # A controlled taxonomy was started but has not completed its scope.
        return False
    else:
        # Existing production rows predate the controlled catalog.  They must
        # remain visible to the reconcile workflow until they are reprobed.
        required_fields = ('subject', 'question_type', 'normalized_text')
    return all(
        isinstance(probe.get(key), str) and probe[key].strip()
        for key in required_fields
    )


def is_ai_knowledge_complete(question) -> bool:
    """Accept controlled module results and historic knowledge results."""
    knowledge = getattr(question, 'ai_knowledge_enrichment', None)
    if not _valid_ai_payload(knowledge):
        return False
    modules = knowledge.get('knowledge_modules')
    if isinstance(modules, list):
        if not modules:
            return False
        level = knowledge.get('difficulty_level')
        if level not in {'L1', 'L2', 'L3', 'L4', 'L5'}:
            return False
        stored = getattr(question, 'difficulty', None)
        try:
            score = Decimal(str(stored))
            return Decimal(level[1]) <= score <= Decimal(level[1]) + Decimal('0.9')
        except (TypeError, ValueError, ArithmeticError):
            return False

    # Compatibility for rows generated before module-level constrained
    # selection was introduced.
    points = knowledge.get('knowledge_points')
    if not isinstance(points, list) or not points:
        return False
    difficulty = knowledge.get('difficulty')
    if isinstance(difficulty, str) and difficulty in {'L1', 'L2', 'L3', 'L4', 'L5'}:
        return True
    try:
        return Decimal(str(getattr(question, 'difficulty', None))) in {
            Decimal(i) for i in range(1, 6)
        }
    except (TypeError, ValueError, ArithmeticError):
        return False


def is_ai_mode_complete(question, mode: str) -> bool:
    normalized_mode = str(mode).strip().upper()
    if normalized_mode not in {'A', 'B', 'C'}:
        return False
    return _valid_ai_payload(
        getattr(question, f'ai_answer_{normalized_mode.lower()}', None)
    )


def _load_reconcile_question(question_id):
    return ExamQuestion.objects.get(id=question_id)


def _run_reconcile_probe(question_id):
    service = create_ai_review_service()
    try:
        result = service.process_question_probe(question_id)
        if 'controlled_taxonomy' not in result:
            # The catalog is not imported yet, so retain the legacy probe
            # persistence contract for existing deployments.
            service.save_results_to_question(
                question_id,
                {
                    'probe': result.get('probe', {}),
                    'knowledge': result.get('knowledge', {}),
                    'errors': result.get('errors', {}),
                },
            )
        return {'status': 'complete'}
    except Exception as error:
        return {'status': 'failed', 'error': classify_ai_failure(error)}
    finally:
        service.close()


def _run_reconcile_knowledge(question_id):
    # The third controlled probe stage owns module selection and is invoked
    # together with scope/subtopic so its candidates cannot drift.
    return _run_reconcile_probe(question_id)


def _run_reconcile_mode(question_id, mode):
    return single_mode_ai_process_question.run(str(question_id), mode)


def _attempt_reconcile_step(question_id, runner, validator):
    last_error = 'result_incomplete'
    for attempt in (1, 2):
        try:
            result = runner(question_id) or {}
            last_error = result.get('error') or 'result_incomplete'
        except Exception as error:
            last_error = classify_ai_failure(error)
        question = _load_reconcile_question(question_id)
        if validator(question):
            return (
                {'status': 'complete', 'attempts': attempt, 'error': None},
                question,
            )
    return (
        {'status': 'failed', 'attempts': 2, 'error': last_error},
        question,
    )


@shared_task(bind=True, max_retries=0, soft_time_limit=1200, time_limit=1260)
def reconcile_course_probe_only_task(self, question_id):
    """Repair one missing probe with one retry, without starting A/B/C."""
    question = _load_reconcile_question(question_id)
    if is_ai_probe_complete(question):
        detail = {'status': 'skipped', 'attempts': 0, 'error': None}
    else:
        detail, _question = _attempt_reconcile_step(
            question_id, _run_reconcile_probe, is_ai_probe_complete
        )
    return {'question_id': str(question_id), 'step': detail}


def reconcile_course_question_ai(question_id, round_no=1):
    """Fill only missing probe/knowledge/A/B/C fields for one question."""
    question = _load_reconcile_question(question_id)
    steps = {}

    if is_ai_probe_complete(question):
        steps['probe'] = {'status': 'skipped', 'attempts': 0, 'error': None}
    else:
        steps['probe'], question = _attempt_reconcile_step(
            question_id, _run_reconcile_probe, is_ai_probe_complete
        )

    if is_ai_knowledge_complete(question):
        steps['knowledge'] = {'status': 'skipped', 'attempts': 0, 'error': None}
    elif is_ai_probe_complete(question):
        steps['knowledge'], question = _attempt_reconcile_step(
            question_id, _run_reconcile_knowledge, is_ai_knowledge_complete
        )
    else:
        steps['knowledge'] = {
            'status': 'failed', 'attempts': 0, 'error': 'probe_incomplete',
        }

    prerequisites_complete = (
        is_ai_probe_complete(question) and is_ai_knowledge_complete(question)
    )
    for mode in 'ABC':
        if is_ai_mode_complete(question, mode):
            steps[mode] = {'status': 'skipped', 'attempts': 0, 'error': None}
            continue
        if not prerequisites_complete:
            missing = (
                'probe_incomplete'
                if not is_ai_probe_complete(question)
                else 'knowledge_incomplete'
            )
            steps[mode] = {'status': 'failed', 'attempts': 0, 'error': missing}
            continue
        steps[mode], question = _attempt_reconcile_step(
            question_id,
            lambda qid, current_mode=mode: _run_reconcile_mode(
                qid, current_mode
            ),
            lambda current, current_mode=mode: is_ai_mode_complete(
                current, current_mode
            ),
        )

    return {
        'question_id': str(question_id),
        'round': int(round_no),
        'steps': steps,
    }


def _course_reconcile_cache_key(batch_id):
    return f'{COURSE_RECONCILE_KEY_PREFIX}{batch_id}'


def _set_course_reconcile_status(batch_id, payload):
    cache.set(
        _course_reconcile_cache_key(batch_id),
        deepcopy(payload),
        timeout=COURSE_RECONCILE_STATUS_TTL,
    )


def get_course_reconcile_status(batch_id):
    return cache.get(_course_reconcile_cache_key(batch_id))


def _course_question_ids(course_id):
    from apps.courses.models import CourseQuestionLink

    return [
        str(value)
        for value in CourseQuestionLink.objects.filter(
            course_id=course_id,
            is_deleted=False,
        ).order_by('created_at', 'id').values_list('question_id', flat=True)
    ]


def _aggregate_reconcile_results(results):
    counts = Counter()
    failures = []
    for result in results:
        question_id = result.get('question_id')
        for step, detail in result.get('steps', {}).items():
            status = detail.get('status', 'failed')
            counts[f'{step}:{status}'] += 1
            if status == 'failed':
                failures.append({
                    'question_id': question_id,
                    'step': step,
                    'error': detail.get('error') or 'unknown_error',
                })
    return {'counts': dict(counts), 'failures': failures}


def _course_reconcile_completion(course_id):
    questions = ExamQuestion.objects.filter(
        course_links__course_id=course_id,
        course_links__is_deleted=False,
    ).distinct()
    values = list(questions)
    return {
        'total': len(values),
        'probe_complete': sum(is_ai_probe_complete(q) for q in values),
        'knowledge_complete': sum(is_ai_knowledge_complete(q) for q in values),
        'a_complete': sum(is_ai_mode_complete(q, 'A') for q in values),
        'b_complete': sum(is_ai_mode_complete(q, 'B') for q in values),
        'c_complete': sum(is_ai_mode_complete(q, 'C') for q in values),
    }


def _enqueue_course_reconcile_round(course_id, batch_id, round_no):
    question_ids = _course_question_ids(course_id)
    header = group(
        reconcile_course_question_ai_task.s(question_id, round_no).set(
            queue='ai.batch'
        )
        for question_id in question_ids
    )
    callback = course_ai_reconcile_round_finished.s(
        str(course_id), str(batch_id), int(round_no)
    ).set(queue='ai.batch')
    return str(chord(header)(callback).id)


@shared_task(bind=True, max_retries=0, soft_time_limit=30000, time_limit=31200)
def reconcile_course_question_ai_task(self, question_id, round_no=1):
    return reconcile_course_question_ai(question_id, round_no=round_no)


@shared_task(bind=True, max_retries=0)
def start_course_ai_reconcile(self, course_id, batch_id=None):
    batch_id = str(batch_id or uuid.uuid4())
    question_ids = _course_question_ids(course_id)
    payload = {
        'batch_id': batch_id,
        'course_id': str(course_id),
        'status': 'round_1_queued',
        'total_questions': len(question_ids),
        'rounds': {},
        'created_at': timezone.now().isoformat(),
    }
    _set_course_reconcile_status(batch_id, payload)
    round_task_id = _enqueue_course_reconcile_round(course_id, batch_id, 1)
    payload['round_task_id'] = round_task_id
    _set_course_reconcile_status(batch_id, payload)
    return payload


@shared_task(bind=True, max_retries=0)
def course_ai_reconcile_round_finished(
    self, results, course_id, batch_id, round_no,
):
    payload = get_course_reconcile_status(batch_id) or {
        'batch_id': str(batch_id),
        'course_id': str(course_id),
        'rounds': {},
    }
    payload.setdefault('rounds', {})[str(round_no)] = (
        _aggregate_reconcile_results(results)
    )
    if int(round_no) == 1:
        payload['status'] = 'round_2_queued'
        _set_course_reconcile_status(batch_id, payload)
        payload['round_2_task_id'] = _enqueue_course_reconcile_round(
            course_id, batch_id, 2
        )
        _set_course_reconcile_status(batch_id, payload)
        return {'status': 'round_2_queued', 'batch_id': str(batch_id)}

    payload['status'] = 'completed'
    payload['completed_at'] = timezone.now().isoformat()
    payload['final'] = _course_reconcile_completion(course_id)
    _set_course_reconcile_status(batch_id, payload)
    return {
        'status': 'completed',
        'batch_id': str(batch_id),
        'final': payload['final'],
    }

# Step labels for progress reporting
STEP_LABELS = {
    'starting': '准备中...',
    'probe': '正在探查...',
    'vision': '正在读图...',
    'answer_a': '正在生成A模式答案...',
    'answer_b': '正在生成B模式答案...',
    'answer_c': '正在生成C模式答案...',
    'verifier': '正在校验...',
}


@shared_task
def dispatch_queued_ai_items_task():
    return dispatch_queued_ai_items()


@shared_task
def recover_and_dispatch_ai_items():
    """Recover only expired lost-worker items, then fill available slots."""
    recovered = recover_stale_ai_items()
    dispatch_queued_ai_items()
    return recovered


@shared_task(bind=True, max_retries=0)
def execute_ai_job_item(self, item_id: str):
    """Execute one durable queue item using the unchanged full AI pipeline."""
    from .ai_queue import RedisLeasePool
    from .models import AIProcessingJob, AIProcessingJobItem

    item = AIProcessingJobItem.objects.select_related('question').get(id=item_id)
    if item.status != AIProcessingJobItem.Status.DISPATCHED:
        return {'status': 'skipped', 'question_id': str(item.question_id)}
    item.status = AIProcessingJobItem.Status.RUNNING
    item.attempt_count += 1
    item.started_at = timezone.now()
    item.save(update_fields=['status', 'attempt_count', 'started_at'])
    service = AIReviewService()
    try:
        def persist_completed_step(step_key, value):
            service.save_results_to_question(
                item.question_id,
                {step_key: value, 'errors': {}},
            )

        results = service.process_question_full_v2(
            item.question_id,
            model=item.model,
            on_step_complete=persist_completed_step,
            retry_mode_b=True,
        )
        service.save_results_to_question(item.question_id, results)
        item.status = (AIProcessingJobItem.Status.PARTIAL if results.get('errors')
                       else AIProcessingJobItem.Status.SUCCEEDED)
        b_mode_error = results.get('errors', {}).get('answer_b')
        item.error_code = (
            f'answer_b_failed_{classify_ai_failure(Exception(b_mode_error))}'
            if b_mode_error
            else ''
        )
        item.finished_at = timezone.now()
        item.save(update_fields=['status', 'error_code', 'finished_at'])
        AIProcessingJob.sync_status_from_items(item.job_id)
        return {'status': 'partial' if results.get('errors') else 'complete', 'question_id': str(item.question_id)}
    except Exception as error:
        item.status = AIProcessingJobItem.Status.FAILED
        error_category = classify_ai_failure(error)
        item.error_code = f'processing_failed_{error_category}'
        item.finished_at = timezone.now()
        item.save(update_fields=['status', 'error_code', 'finished_at'])
        AIProcessingJob.sync_status_from_items(item.job_id)
        logger.exception(
            'AI queue item processing failed',
            extra={
                'question_id': str(item.question_id),
                'item_id': str(item.id),
                'error_category': error_category,
            },
        )
        return {'status': 'failed', 'question_id': str(item.question_id)}
    finally:
        service.close()
        RedisLeasePool(
            'question',
            limit=int(getattr(settings, 'AI_GLOBAL_CONCURRENCY', 6)),
            ttl_seconds=4200,
        ).release(str(item.id))


def _skip_missing_question(set_progress, question_id):
    """Persist terminal progress and return the stable missing-question result."""
    result = {
        'status': 'skipped',
        'question_id': str(question_id),
        'reason': 'question_not_found',
    }
    set_progress(
        'skipped',
        'starting',
        STEP_LABELS['starting'],
        error=result['reason'],
    )
    logger.warning(
        'AI processing skipped because question was not found',
        extra={
            'question_id': result['question_id'],
            'status': result['status'],
            'reason': result['reason'],
        },
    )
    return result


@shared_task(bind=True, max_retries=0)
def single_ai_process_question(self, question_id, model=None):
    """AI processing for a single question (6-step pipeline)."""
    task_id = self.request.id

    def set_progress(status, step, label, result=None, error=None):
        cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
            'status': status,
            'question_id': question_id,
            'step': step,
            'step_label': label,
            'result': result,
            'error': error,
        }), timeout=3600)

    set_progress('running', 'starting', STEP_LABELS['starting'])

    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        return _skip_missing_question(set_progress, question_id)
    except Exception:
        raise

    service = create_ai_review_service()

    try:
        def persist_completed_step(step_key, value):
            service.save_results_to_question(
                question_id,
                {step_key: value, 'errors': {}},
            )

        # Call the new 6-step pipeline
        results = service.process_question_full_v2(
            question_id,
            model=model,
            on_step_complete=persist_completed_step,
        )
        service.save_results_to_question(question_id, results)

        logger.info(
            '[AI RESULT] task complete',
            extra={
                'question_id': str(question_id),
                'status': question.ai_processing_status,
            },
        )
        for key in ('answer_a', 'answer_b', 'answer_c', 'probe', 'vision', 'verifier', 'knowledge'):
            if key in results:
                val = results[key]
                if isinstance(val, dict) and 'error' in val:
                    logger.warning(
                        '[AI RESULT] field failed',
                        extra={'field': key, 'status': 'failed'},
                    )
                else:
                    logger.info(
                        '[AI RESULT] field complete',
                        extra={
                            'field': key,
                            'status': 'complete',
                            'value_length': len(str(val)),
                        },
                    )
                    if key.startswith('answer_'):
                        for k2 in ('steps', 'answer', 'content', 'options', 'dialogue'):
                            if k2 in val:
                                v = val[k2]
                                logger.info(
                                    '[AI RESULT] answer field present',
                                    extra={
                                        'field': f'{key}.{k2}',
                                        'value_length': len(str(v)),
                                    },
                                )

        task_status = 'complete' if not results.get('errors') else 'partial'
        set_progress(task_status, 'complete', '处理完成', result={
            'errors': results.get('errors', {}),
            'image_count': results.get('image_count', 0),
        })

        response = {
            'status': task_status,
            'question_id': question_id,
        }
        service.close()
        return response

    except Exception as e:
        service.close()
        logger.error(
            'AI processing failed',
            extra={'question_id': str(question_id), 'status': 'failed'},
        )
        set_progress('failed', 'failed', '处理失败', error=str(e))
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def single_probe_ai_process_question(self, question_id, model=None):
    """Run the manual probe-only AI path for one existing question."""
    task_id = self.request.id

    def set_progress(status, step, label, result=None, error=None):
        cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
            'status': status,
            'question_id': question_id,
            'step': step,
            'step_label': label,
            'result': result,
            'error': error,
        }), timeout=3600)

    set_progress('running', 'starting', STEP_LABELS['starting'])

    try:
        ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        return _skip_missing_question(set_progress, question_id)
    except Exception:
        raise

    service = create_ai_review_service()
    try:
        results = service.process_question_probe(question_id, model=model)
        service.save_results_to_question(question_id, results)
        task_status = 'complete' if not results.get('errors') else 'partial'
        set_progress(
            task_status,
            'complete',
            '处理完成',
            result={'errors': results.get('errors', {})},
        )
        logger.info(
            'AI probe processing complete',
            extra={
                'question_id': str(question_id),
                'status': task_status,
                'mode': 'probe',
            },
        )
        return {
            'status': task_status,
            'question_id': str(question_id),
            'mode': 'probe',
        }
    except Exception:
        logger.error(
            'AI probe processing failed',
            extra={
                'question_id': str(question_id),
                'status': 'failed',
                'mode': 'probe',
            },
        )
        set_progress('failed', 'failed', '处理失败', error='processing_failed')
        return {
            'status': 'failed',
            'question_id': str(question_id),
            'mode': 'probe',
        }
    finally:
        service.close()


@shared_task(
    bind=True,
    max_retries=0,
    soft_time_limit=3800,
    time_limit=3900,
)
def single_mode_ai_process_question(self, question_id, mode, model=None):
    """Arbitrate and atomically persist one manually requested A/B/C mode."""
    task_id = self.request.id
    normalized_mode = mode.strip().upper() if isinstance(mode, str) else ''
    service = None

    def set_progress(status, step, label, result=None, error=None):
        cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
            'status': status,
            'question_id': question_id,
            'step': step,
            'step_label': label,
            'result': result,
            'error': error,
        }), timeout=3600)

    try:
        set_progress('running', 'starting', STEP_LABELS['starting'])
        if normalized_mode not in ('A', 'B', 'C'):
            set_progress(
                'failed', 'failed', '处理失败', error='invalid_mode'
            )
            return {'status': 'failed', 'error': 'invalid_mode'}

        try:
            question = ExamQuestion.objects.get(id=question_id)
        except ExamQuestion.DoesNotExist:
            return _skip_missing_question(set_progress, question_id)
        except Exception:
            raise

        service = create_ai_review_service()

        # Load existing probe/vision results from DB to avoid redundant API calls
        probe_result = question.ai_probe_result or {}
        vision_result = question.ai_vision_extract or {}

        if normalized_mode == 'B' and not probe_result:
            set_progress(
                'failed', 'failed', '请先完成 AI 探查', error='probe_result_required'
            )
            return {
                'status': 'failed',
                'question_id': question_id,
                'mode': normalized_mode,
                'error': 'probe_result_required',
            }

        # Build normalized_text and knowledge_refs from existing data
        normalized_text = probe_result.get('normalized_text', question.stem or '')
        knowledge_refs = ""
        if probe_result.get('topic_tags_top3'):
            knowledge_refs = ", ".join(probe_result['topic_tags_top3'])
        elif isinstance(getattr(question, 'ai_knowledge_enrichment', None), dict):
            modules = question.ai_knowledge_enrichment.get('knowledge_modules')
            if isinstance(modules, list):
                knowledge_refs = ", ".join(
                    str(module) for module in modules if str(module).strip()
                )

        # Get image URLs
        image_urls = service._get_question_image_urls(question)

        # A manual A/B/C request for a source-unanswered question must retain
        # the same canonical DeepSeek baseline as the full pipeline.  The
        # baseline is committed before any mode-specific generation so later
        # failures never discard the newly established answer and analysis.
        baseline = _unanswered_baseline_from_verifier(
            question.ai_verifier_result
        )
        rebuild_invalid_baseline = baseline is not None and not service.unanswered_baseline_is_valid(
            question,
            baseline,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
        )
        if rebuild_invalid_baseline:
            # A previous no-answer baseline may have filled answer/analysis
            # with an explanatory sentence that is invalid for the question
            # type.  Treat it as missing and recreate it before mode handling.
            baseline = None

        if baseline is None and (
            _question_has_no_source_answer(question) or rebuild_invalid_baseline
        ):
            generated_baseline = service.solve_unanswered_question_baseline(
                question,
                image_urls=image_urls,
                normalized_text=normalized_text,
                vision_result=vision_result,
                knowledge_refs=knowledge_refs,
                exclude_reference_answer=rebuild_invalid_baseline,
            )
            with transaction.atomic():
                locked_question = (
                    ExamQuestion.objects.select_for_update().get(id=question_id)
                )
                baseline = _unanswered_baseline_from_verifier(
                    locked_question.ai_verifier_result
                )
                locked_baseline_valid = baseline is not None and service.unanswered_baseline_is_valid(
                    locked_question,
                    baseline,
                    image_urls=image_urls,
                    normalized_text=normalized_text,
                    vision_result=vision_result,
                    knowledge_refs=knowledge_refs,
                )
                if not locked_baseline_valid:
                    baseline = None
                if baseline is None and (
                    _question_has_no_source_answer(locked_question)
                    or rebuild_invalid_baseline
                ):
                    baseline = {
                        key: generated_baseline[key]
                        for key in (
                            'canonical_answer',
                            'canonical_analysis',
                            'key_facts',
                            'confidence',
                            'context_hash',
                        )
                        if key in generated_baseline
                    }
                    verifier = (
                        dict(locked_question.ai_verifier_result)
                        if isinstance(locked_question.ai_verifier_result, dict)
                        else {}
                    )
                    verifier['unanswered_baseline'] = baseline
                    locked_question.answer = baseline['canonical_answer']
                    locked_question.analysis = baseline['canonical_analysis']
                    locked_question.ai_verifier_result = verifier
                    locked_question.save(
                        update_fields=['answer', 'analysis', 'ai_verifier_result']
                    )
                question = locked_question

        if baseline is not None:
            outcome = service.solve_unanswered_mode_with_arbitration(
                question,
                mode=normalized_mode,
                baseline=baseline,
                image_urls=image_urls,
                normalized_text=normalized_text,
                vision_result=vision_result,
                knowledge_refs=knowledge_refs,
                model=model,
            )
        else:
            outcome = service.solve_mode_with_arbitration(
                question,
                mode=normalized_mode,
                image_urls=image_urls,
                normalized_text=normalized_text,
                vision_result=vision_result,
                knowledge_refs=knowledge_refs,
                cached_verification=question.ai_verifier_result,
                model=model,
            )

        mode_key = f'ai_answer_{normalized_mode.lower()}'
        answer = dict(outcome.answer)
        answer['mode'] = normalized_mode
        route_provider, route_model = service._task_route(
            f'mode_{normalized_mode.lower()}_answer'
        )
        answer['provider'] = route_provider
        answer['model'] = route_model
        processed_at = timezone.now()
        answer['generated_at'] = processed_at.strftime('%Y-%m-%dT%H:%M:%S')
        answer['confirmed'] = False
        answer['confirmed_at'] = None
        answer['edited_content'] = None
        answer['error'] = None

        update_fields = [mode_key, 'ai_processed_at', 'ai_processing_status']
        with transaction.atomic():
            locked_question = (
                ExamQuestion.objects.select_for_update().get(id=question_id)
            )
            locked_probe = locked_question.ai_probe_result or {}
            locked_vision = locked_question.ai_vision_extract or {}
            locked_normalized_text = locked_probe.get(
                'normalized_text', locked_question.stem or ''
            )
            locked_knowledge_refs = ''
            if locked_probe.get('topic_tags_top3'):
                locked_knowledge_refs = ', '.join(
                    locked_probe['topic_tags_top3']
                )
            locked_context = QuestionContextBuilder.build(
                locked_question,
                image_urls=service._get_question_image_urls(locked_question),
                normalized_text=locked_normalized_text,
                vision_result=locked_vision,
                knowledge_refs=locked_knowledge_refs,
                target_mode=normalized_mode,
            )
            if question_context_hash(locked_context) != outcome.verification.get(
                'context_hash'
            ):
                raise RuntimeError('question_context_changed')
            setattr(locked_question, mode_key, answer)
            if outcome.shared_verifier_result is not None:
                locked_question.ai_verifier_result = dict(
                    outcome.shared_verifier_result
                )
                update_fields.append('ai_verifier_result')
            locked_question.ai_processed_at = processed_at
            locked_question.ai_processing_status = 'success'
            locked_question.save(update_fields=update_fields)

        logger.info(
            '[AI RESULT] single mode complete',
            extra={
                'mode': normalized_mode,
                'question_id': str(question_id),
                'status': 'complete',
            },
        )
        for k2 in ('steps', 'questions', 'final_answer', 'summary'):
            if k2 in answer:
                v = answer[k2]
                logger.info(
                    '[AI RESULT] single mode field present',
                    extra={
                        'field': f'{mode_key}.{k2}',
                        'value_length': len(str(v)),
                    },
                )

        set_progress('complete', '处理完成', f'{normalized_mode}模式处理完成', result={
            'mode': normalized_mode,
            'image_count': len(image_urls),
        })

        response = {
            'status': 'complete',
            'question_id': question_id,
            'mode': normalized_mode,
        }
        return response

    except SoftTimeLimitExceeded:
        logger.error(
            'AI single mode processing timed out',
            extra={
                'question_id': str(question_id),
                'mode': normalized_mode,
                'status': 'failed',
            },
        )
        set_progress('failed', 'failed', '处理超时', error='processing_timeout')
        return {'status': 'failed', 'error': 'processing_timeout'}
    except Exception as error:
        if service is None:
            raise
        error_category = classify_ai_failure(error)
        logger.exception(
            'AI single mode processing failed',
            extra={
                'question_id': str(question_id),
                'mode': normalized_mode,
                'status': 'failed',
                'error_category': error_category,
            },
        )
        set_progress('failed', 'failed', '处理失败', error=error_category)
        return {'status': 'failed', 'error': error_category}
    finally:
        try:
            if service is not None:
                service.close()
        finally:
            if normalized_mode in ('A', 'B', 'C'):
                release_single_mode_ai_task_lock(
                    str(question_id), normalized_mode, task_id
                )
