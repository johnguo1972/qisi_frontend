import uuid_utils.compat as uuid_compat
from django.db import models


class QuestionDocumentImportTask(models.Model):
    """Persistent lifecycle state for one course document import."""

    class DocumentType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        DOCX = 'docx', 'DOCX'

    class Stage(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        EXTRACTING = 'extracting', 'Extracting'
        STRUCTURING = 'structuring', 'Structuring'
        IMPORTING = 'importing', 'Importing'
        SUCCESS = 'success', 'Success'
        PARTIAL_SUCCESS = 'partial_success', 'Partial success'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    batch = models.OneToOneField(
        'study.QuestionIngestionBatch', on_delete=models.CASCADE,
        related_name='document_import_task',
    )
    course = models.ForeignKey(
        'courses.Course', on_delete=models.CASCADE, related_name='document_import_tasks',
    )
    source_file = models.CharField(max_length=500)
    detected_mime = models.CharField(max_length=127)
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    page_count = models.PositiveIntegerField()
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    linked_count = models.PositiveIntegerField(default=0)
    error_summary = models.CharField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'question_document_import_task'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress__lte=100), name='ck_document_import_progress_100',
            ),
        ]
