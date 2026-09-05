"""Lifecycle helpers for question ingestion audit batches."""

from django.utils import timezone

from .models import QuestionIngestionBatch


def start_ingestion_batch(*, actor, source_type, source_name, course=None, paper=None):
    """Persist a running batch before its source operation starts."""
    return QuestionIngestionBatch.objects.create(
        actor=actor,
        source_type=source_type,
        source_name=source_name,
        course=course,
        paper=paper,
        started_at=timezone.now(),
    )


def finish_ingestion_batch(
    batch,
    *,
    total_read,
    created_count,
    skipped_existing_count,
    skipped_in_package_count,
    failed_count,
):
    """Store final counters and derive the visible batch outcome."""
    completed_count = created_count + skipped_existing_count + skipped_in_package_count
    if failed_count == 0:
        status = QuestionIngestionBatch.Status.SUCCESS
    elif completed_count:
        status = QuestionIngestionBatch.Status.PARTIAL_SUCCESS
    else:
        status = QuestionIngestionBatch.Status.FAILED

    batch.total_read = total_read
    batch.created_count = created_count
    batch.skipped_existing_count = skipped_existing_count
    batch.skipped_in_package_count = skipped_in_package_count
    batch.failed_count = failed_count
    batch.status = status
    batch.finished_at = timezone.now()
    batch.save(update_fields=[
        'total_read', 'created_count', 'skipped_existing_count',
        'skipped_in_package_count', 'failed_count', 'status', 'finished_at',
    ])
    return batch
