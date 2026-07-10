"""Celery tasks for batch AI processing of questions."""
import logging
import json
from celery import shared_task
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from apps.common.ai_service import AIReviewService
from apps.parser.models import ExamQuestion

logger = logging.getLogger(__name__)

CANCEL_KEY_PREFIX = 'batch_cancel:'
PROGRESS_KEY_PREFIX = 'batch_progress:'
MAX_CONCURRENCY = 3


@shared_task(bind=True, max_retries=0)
def batch_ai_process_questions(self, question_ids, model=None):
    """Batch AI processing for multiple questions with concurrency control.

    Args:
        question_ids: list of question IDs to process
        model: optional AI model override
    """
    task_id = self.request.id
    total = len(question_ids)
    cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
        'current': 0, 'total': total, 'status': 'running',
        'current_question': None, 'success_count': 0, 'error_count': 0,
        'errors': {},
    }), timeout=3600)

    service = AIReviewService()
    success_count = 0
    error_count = 0
    errors = {}

    def process_one(q_id):
        """Process a single question, return (q_id, success, error_msg)."""
        try:
            results = service.process_question_full(q_id, model=model)
            service.save_results_to_question(q_id, results)
            has_errors = bool(results.get('errors'))
            return (q_id, not has_errors,
                    str(results.get('errors')) if has_errors else None)
        except Exception as e:
            return (q_id, False, str(e))

    try:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
            futures = {executor.submit(process_one, q_id): q_id for q_id in question_ids}
            current = 0

            for future in as_completed(futures):
                # Check cancel flag
                if cache.get(f'{CANCEL_KEY_PREFIX}{task_id}'):
                    logger.info(f'Batch task {task_id} cancelled at {current}/{total}')
                    cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
                        'current': current, 'total': total, 'status': 'cancelled',
                        'current_question': None, 'success_count': success_count,
                        'error_count': error_count, 'errors': errors,
                    }), timeout=3600)
                    return {'status': 'cancelled', 'current': current, 'total': total}

                q_id, success, error = future.result()
                current += 1

                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors[str(q_id)] = error or 'Unknown error'

                # Update progress
                cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
                    'current': current, 'total': total, 'status': 'running',
                    'current_question': q_id, 'success_count': success_count,
                    'error_count': error_count, 'errors': dict(errors),
                }), timeout=3600)

        # All done
        cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
            'current': total, 'total': total, 'status': 'completed',
            'current_question': None, 'success_count': success_count,
            'error_count': error_count, 'errors': errors,
        }), timeout=3600)

        return {'status': 'completed', 'success_count': success_count,
                'error_count': error_count, 'errors': errors}

    except Exception as e:
        logger.exception(f'Batch task {task_id} failed')
        cache.set(f'{PROGRESS_KEY_PREFIX}{task_id}', json.dumps({
            'current': current, 'total': total, 'status': 'failed',
            'current_question': None, 'success_count': success_count,
            'error_count': error_count, 'errors': errors,
            'task_error': str(e),
        }), timeout=3600)
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def single_generate_ai_answers(self, question_id: int, model: str = None):
    """为单道题生成 A/B/C 模式 AI 答案（轻量任务，不跑全流程）。

    此任务被 auto_trigger_ai_generation signal 触发，也可手动调用。

    Args:
        question_id: 题目 ID
        model: 可选 AI 模型覆盖（如 'qwen3.6-plus'），默认由 AIReviewService 决定
    """
    try:
        service = AIReviewService()
        results = service.process_question_full(question_id, model=model)
        service.save_results_to_question(question_id, results)

        # 记录失败信息（可选，需 ExamQuestion 有 ai_generation_error 字段）
        if results.get('errors'):
            question = ExamQuestion.objects.get(id=question_id)
            if hasattr(question, 'ai_generation_error') or 'ai_generation_error' in [f.name for f in ExamQuestion._meta.get_fields()]:
                question.ai_generation_error = json.dumps(results['errors'])
                question.save(update_fields=['ai_generation_error'])

        return {'status': 'success', 'question_id': question_id}
    except Exception as e:
        logger.exception(f'AI generation failed for question {question_id}: {e}')
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
