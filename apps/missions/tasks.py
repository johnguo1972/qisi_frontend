"""Celery entry points for phase 4 generation."""
from celery import shared_task


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_wrongbook_batch_task(self, batch_id):
    from .wrongbook_matrix import generate_batch
    return {'batch_id': str(generate_batch(batch_id).id)}
