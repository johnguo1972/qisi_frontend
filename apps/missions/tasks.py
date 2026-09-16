"""Celery entry points for phase 4 generation."""
from celery import shared_task


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_wrongbook_batch_task(self, batch_id):
    from .wrongbook_matrix import generate_batch
    return {'batch_id': str(generate_batch(batch_id).id)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_teacher_wrongbook_batch_task(self, batch_id):
    from .teacher_wrongbook_selection import generate_teacher_batch
    return {'batch_id': str(generate_teacher_batch(batch_id).id)}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_wrong_drill_batch_task(self, batch_id):
    from .models import ClassroomWrongDrillBatch
    from .classroom_wrong_drill_service import generate_wrong_drill_batch

    batch = ClassroomWrongDrillBatch.objects.select_related(
        'matrix__source_mission', 'source_set', 'requested_by',
    ).get(pk=batch_id)
    try:
        generated = generate_wrong_drill_batch(
            mission=batch.matrix.source_mission,
            matrix=batch.matrix,
            teacher=batch.requested_by,
            source_set_id=batch.source_set_id,
            student_ids=batch.request_student_ids,
            version=batch.request_version,
            existing_batch_id=batch.id,
        )
        return {'batch_id': str(generated.id)}
    except Exception as exc:
        ClassroomWrongDrillBatch.objects.filter(pk=batch.id).update(
            status='failed', failed_count=1, errors=[{'reason_code': 'TASK_FAILED', 'message': str(exc)[:200]}],
        )
        raise
