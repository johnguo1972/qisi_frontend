"""Celery tasks for single question AI processing."""
import json
import logging
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from apps.common.ai_service import AIReviewService, create_ai_review_service
from apps.parser.models import ExamQuestion

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

    service = create_ai_review_service()

    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        service.close()
        set_progress('failed', 'starting', '题目不存在', error=f'Question {question_id} not found')
        return {'status': 'failed', 'error': f'Question {question_id} not found'}
    except Exception:
        service.close()
        raise

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
def single_mode_ai_process_question(self, question_id, mode, model=None):
    """AI processing for a single mode (A/B/C only), reusing existing probe/vision results.

    Args:
        mode: 'A', 'B', or 'C'
    """
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

    service = create_ai_review_service()

    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        service.close()
        set_progress('failed', 'starting', '题目不存在', error=f'Question {question_id} not found')
        return {'status': 'failed', 'error': f'Question {question_id} not found'}
    except Exception:
        service.close()
        raise

    try:
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

        # Generate only the requested mode
        mode_key = f'ai_answer_{mode.lower()}'
        if mode == 'A':
            answer = service.solve_mode_a(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
        elif mode == 'B':
            answer = service.solve_mode_b(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
        elif mode == 'C':
            answer = service.solve_mode_c(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
        else:
            set_progress('failed', 'failed', f'未知模式: {mode}', error=f'Unknown mode: {mode}')
            service.close()
            return {'status': 'failed', 'error': f'Unknown mode: {mode}'}

        # Save result
        answer['mode'] = mode
        answer['model'] = service._get_model(model)
        processed_at = timezone.now()
        answer['generated_at'] = processed_at.strftime('%Y-%m-%dT%H:%M:%S')
        answer['confirmed'] = False
        answer['confirmed_at'] = None
        answer['edited_content'] = None
        answer['error'] = None

        # Update DB field
        setattr(question, mode_key, answer)
        question.ai_processed_at = processed_at
        question.ai_processing_status = 'success'
        question.save()

        logger.info(
            '[AI RESULT] single mode complete',
            extra={
                'mode': mode,
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

        set_progress('complete', '处理完成', f'{mode}模式处理完成', result={
            'mode': mode,
            'image_count': len(image_urls),
        })

        response = {
            'status': 'complete',
            'question_id': question_id,
            'mode': mode,
        }
        service.close()
        return response

    except Exception as e:
        service.close()
        logger.error(
            'AI single mode processing failed',
            extra={
                'question_id': str(question_id),
                'mode': mode,
                'status': 'failed',
            },
        )
        set_progress('failed', 'failed', '处理失败', error=str(e))
        return {'status': 'failed', 'error': str(e)}
