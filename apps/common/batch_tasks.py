"""Celery tasks for batch AI processing of questions."""
import logging
from celery import shared_task
from apps.accounts.models import UserAccount
from apps.common.ai_service import create_ai_review_service
from apps.review.models import AIProcessingJob, AIQueueCapacityExceeded
from apps.review.tasks import dispatch_queued_ai_items_task as dispatch_queued_ai_items

logger = logging.getLogger(__name__)

# Kept as public compatibility constants for student progress polling. New
# durable batch jobs do not write these transient cache records.
CANCEL_KEY_PREFIX = 'batch_cancel:'
PROGRESS_KEY_PREFIX = 'batch_progress:'

@shared_task(bind=True, max_retries=0)
def batch_ai_process_questions(self, question_ids, model=None, creator_id=None):
    """Compatibility adapter: persist a job instead of spawning local threads.

    New HTTP callers create jobs directly.  Legacy callers must provide their
    initiating teacher ID so audit ownership and status polling remain intact.
    """
    if not creator_id:
        logger.warning('Legacy AI batch rejected without creator')
        return {'status': 'failed', 'error': 'creator_required'}
    try:
        creator = UserAccount.objects.get(id=creator_id)
        created = AIProcessingJob.create_for_questions(
            creator=creator,
            question_ids=question_ids,
            source=AIProcessingJob.Source.LEGACY,
            model=model,
        )
    except UserAccount.DoesNotExist:
        return {'status': 'failed', 'error': 'creator_not_found'}
    except AIQueueCapacityExceeded:
        return {'status': 'rejected', 'error': 'ai_queue_capacity_exceeded'}

    dispatch_queued_ai_items.delay()
    return {
        'status': 'pending',
        'job_id': str(created.job.id) if created.job else None,
        'accepted': created.accepted_count,
        'deduplicated': created.duplicate_question_ids,
    }


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def single_generate_ai_answers(self, question_id: int, model: str = None):
    """Keep legacy automatic jobs registered while safely disabling them."""
    result = {
        'status': 'skipped',
        'question_id': str(question_id),
        'reason': 'automatic_generation_disabled',
    }
    logger.info(
        'Automatic AI generation skipped',
        extra={
            'question_id': str(question_id),
            'status': result['status'],
            'reason': result['reason'],
        },
    )
    return result
