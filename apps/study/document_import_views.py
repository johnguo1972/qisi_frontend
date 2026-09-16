"""Persistent API helpers for asynchronous course PDF/DOCX imports."""

from pathlib import Path
import uuid

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from apps.study.document_import_models import QuestionDocumentImportItem, QuestionDocumentImportTask
from apps.study.document_import_service import DocumentValidationError, validate_document_upload
from apps.study.document_import_tasks import process_document_import_task
from apps.study.ingestion import finish_ingestion_batch, start_ingestion_batch


def _task_data(task):
    batch = task.batch
    items = task.items.all()
    candidate_count = task.candidate_count or items.count()
    success_count = items.filter(
        status=QuestionDocumentImportItem.Status.SUCCESS,
        ingest_status=QuestionDocumentImportItem.IngestStatus.INGESTED,
    ).count()
    failed_question_count = items.filter(status=QuestionDocumentImportItem.Status.FAILED).count()
    running_count = items.filter(
        status__in=(
            QuestionDocumentImportItem.Status.DISPATCHED,
            QuestionDocumentImportItem.Status.RUNNING,
            QuestionDocumentImportItem.Status.RETRYING,
        ),
    ).count()
    return {
        'task_id': str(task.id),
        'batch_id': str(task.batch_id),
        'course_id': str(task.course_id),
        'tree_node_id': str(task.tree_node_id) if task.tree_node_id else None,
        'stage': task.stage,
        'progress': task.progress,
        'document_type': task.document_type,
        'import_purpose': task.import_purpose,
        'source_type': task.source_type,
        'wrong_drill_source_set_id': str(task.wrong_drill_source_set_id) if task.wrong_drill_source_set_id else None,
        'page_count': task.page_count,
        'candidate_count': candidate_count,
        'success_count': success_count or task.success_count,
        'failed_question_count': failed_question_count or task.failed_question_count,
        'running_count': running_count,
        'last_heartbeat_at': task.last_heartbeat_at,
        'total_read': batch.total_read or candidate_count,
        'created_count': batch.created_count,
        'skipped_existing_count': batch.skipped_existing_count,
        'skipped_in_package_count': batch.skipped_in_package_count,
        'failed_count': batch.failed_count or failed_question_count,
        'linked_count': task.linked_count,
        'errors': [part for part in task.error_summary.split('; ') if part][:20],
    }


def _save_upload(upload, *, course_id, document_type, storage_prefix='course_document_imports'):
    """Write an untrusted file only below our controlled media root."""
    relative_path = Path(storage_prefix) / str(course_id) / (
        f'{uuid.uuid4().hex}.{document_type}'
    )
    destination = Path(settings.MEDIA_ROOT) / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open('wb') as output:
            for chunk in upload.chunks():
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        try:
            destination.parent.rmdir()
        except OSError:
            pass
        raise
    return relative_path.as_posix()


def create_course_document_import(
    request, *, course, tree_node=None, import_purpose='document_import',
    source_type='document_import', wrong_drill_source_set_id=None,
    storage_prefix='course_document_imports', upload=None,
):
    """Create a durable import record, then dispatch only after DB commit."""
    # Ordinary course imports continue to use the existing ``file`` field.
    # Isolated business imports may pass their explicitly named upload field.
    upload = upload or request.FILES.get('file')
    if upload is None:
        raise ValidationError('file is required')
    try:
        validated = validate_document_upload(upload)
    except DocumentValidationError as exc:
        raise ValidationError(str(exc)) from exc

    source_file = None
    try:
        with transaction.atomic():
            source_file = _save_upload(
                upload, course_id=course.id, document_type=validated.document_type,
                storage_prefix=storage_prefix,
            )
            batch = start_ingestion_batch(
                actor=request.user,
                # Keep the ordinary default unchanged while allowing isolated
                # business imports (for example wrongbook_drill) to retain
                # their own auditable source type.
                source_type=source_type,
                source_name=validated.filename,
                course=course,
            )
            task = QuestionDocumentImportTask.objects.create(
                batch=batch,
                course=course,
                tree_node=tree_node,
                source_file=source_file,
                detected_mime=validated.detected_mime,
                document_type=validated.document_type,
                page_count=validated.page_count,
                import_purpose=import_purpose,
                source_type=source_type,
                wrong_drill_source_set_id=wrong_drill_source_set_id,
            )

            def dispatch():
                try:
                    result = process_document_import_task.delay(str(task.id))
                except Exception:
                    QuestionDocumentImportTask.objects.filter(pk=task.id).update(
                        stage=QuestionDocumentImportTask.Stage.FAILED,
                        progress=100,
                        error_summary='document import dispatch failed',
                    )
                    finish_ingestion_batch(
                        batch,
                        total_read=0,
                        created_count=0,
                        skipped_existing_count=0,
                        skipped_in_package_count=0,
                        failed_count=1,
                    )
                    return
                QuestionDocumentImportTask.objects.filter(pk=task.id).update(
                    celery_task_id=str(getattr(result, 'id', '') or ''),
                )

            transaction.on_commit(dispatch)
    except Exception:
        if source_file:
            source_path = Path(settings.MEDIA_ROOT) / source_file
            source_path.unlink(missing_ok=True)
            try:
                source_path.parent.rmdir()
            except OSError:
                pass
        raise

    task.refresh_from_db()
    return Response({'code': 0, 'message': 'document import queued', 'data': _task_data(task)}, status=202)


def get_course_document_import_status(*, course, task_id):
    """Return database state only when the task belongs to the route's course."""
    try:
        task = QuestionDocumentImportTask.objects.select_related('batch').get(
            pk=task_id, course=course,
        )
    except (QuestionDocumentImportTask.DoesNotExist, ValueError, TypeError) as exc:
        raise NotFound('document import task does not exist') from exc
    return Response({'code': 0, 'message': 'success', 'data': _task_data(task)})
