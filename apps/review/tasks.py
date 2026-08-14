"""Celery tasks for single question AI processing."""
import json
import logging
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from apps.common.ai_service import AIReviewService, create_ai_review_service
from apps.parser.models import ExamQuestion
from .ai_mode_dispatch import release_single_mode_ai_task_lock

logger = logging.getLogger(__name__)

PROGRESS_KEY_PREFIX = 'single_ai_progress:'

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
        # Call the new 6-step pipeline
        results = service.process_question_full_v2(question_id, model=model)
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

        # Build normalized_text and knowledge_refs from existing data
        normalized_text = probe_result.get('normalized_text', question.stem or '')
        knowledge_refs = ""
        if probe_result.get('topic_tags_top3'):
            knowledge_refs = ", ".join(probe_result['topic_tags_top3'])

        # Get image URLs
        image_urls = service._get_question_image_urls(question)

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
        answer['model'] = (
            service._get_model(model)
            if model is not None
            else service._task_route(
                f'mode_{normalized_mode.lower()}_answer'
            )[1]
        )
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
    except Exception:
        if service is None:
            raise
        logger.error(
            'AI single mode processing failed',
            extra={
                'question_id': str(question_id),
                'mode': normalized_mode,
                'status': 'failed',
            },
        )
        set_progress('failed', 'failed', '处理失败', error='processing_failed')
        return {'status': 'failed', 'error': 'processing_failed'}
    finally:
        if service is not None:
            service.close()
        if normalized_mode in ('A', 'B', 'C'):
            release_single_mode_ai_task_lock(
                str(question_id), normalized_mode, task_id
            )
