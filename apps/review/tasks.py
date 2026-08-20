"""Celery tasks for single question AI processing."""
import json
import logging
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
        message = str(current).lower()
        if '429' in message or 'rate limit' in message or 'rate_limited' in message:
            return 'rate_limited'
        if 'connecttimeout' in message or 'connect timeout' in message:
            return 'connect_timeout'
        if 'timeout' in message or 'timed out' in message:
            return 'read_timeout'
        if any(marker in message for marker in ('schema', 'json', 'validation')):
            return 'schema_invalid'
        if any(marker in message for marker in ('not configured', 'configuration', 'api key')):
            return 'configuration_error'
        if any(marker in message for marker in ('500', '502', '503', '504', 'unavailable')):
            return 'provider_unavailable'
        current = current.__cause__
    return 'unknown_error'

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
    from .models import AIProcessingJobItem

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
        return {'status': 'partial' if results.get('errors') else 'complete', 'question_id': str(item.question_id)}
    except Exception as error:
        item.status = AIProcessingJobItem.Status.FAILED
        error_category = classify_ai_failure(error)
        item.error_code = f'processing_failed_{error_category}'
        item.finished_at = timezone.now()
        item.save(update_fields=['status', 'error_code', 'finished_at'])
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

        # Get image URLs
        image_urls = service._get_question_image_urls(question)

        # A manual A/B/C request for a source-unanswered question must retain
        # the same canonical DeepSeek baseline as the full pipeline.  The
        # baseline is committed before any mode-specific generation so later
        # failures never discard the newly established answer and analysis.
        baseline = _unanswered_baseline_from_verifier(
            question.ai_verifier_result
        )
        if baseline is None and _question_has_no_source_answer(question):
            generated_baseline = service.solve_unanswered_question_baseline(
                question,
                image_urls=image_urls,
                normalized_text=normalized_text,
                vision_result=vision_result,
                knowledge_refs=knowledge_refs,
            )
            with transaction.atomic():
                locked_question = (
                    ExamQuestion.objects.select_for_update().get(id=question_id)
                )
                baseline = _unanswered_baseline_from_verifier(
                    locked_question.ai_verifier_result
                )
                if baseline is None and _question_has_no_source_answer(
                    locked_question
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
