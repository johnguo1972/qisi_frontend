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
