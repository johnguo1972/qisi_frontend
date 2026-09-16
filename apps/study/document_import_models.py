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
    tree_node = models.ForeignKey(
        'courses.CourseTree', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='document_import_tasks',
    )
    source_file = models.CharField(max_length=500)
    # Optional isolated business context. Ordinary document imports retain
    # their existing default values and behavior.
    import_purpose = models.CharField(max_length=40, default='document_import')
    source_type = models.CharField(max_length=40, default='document_import')
    wrong_drill_source_set_id = models.UUIDField(null=True, blank=True, db_index=True)
    document_fingerprint = models.CharField(max_length=64, blank=True, default='', db_index=True)
    detected_mime = models.CharField(max_length=127)
    document_type = models.CharField(max_length=4, choices=DocumentType.choices)
    page_count = models.PositiveIntegerField()
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    linked_count = models.PositiveIntegerField(default=0)
    candidate_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_question_count = models.PositiveIntegerField(default=0)
    error_summary = models.CharField(max_length=1000, blank=True, default='')
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'question_document_import_task'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(progress__lte=100), name='ck_document_import_progress_100',
            ),
        ]


class QuestionDocumentImportItem(models.Model):
    """Durable state and payload for one document question candidate."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        DISPATCHED = 'dispatched', 'Dispatched'
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        RETRYING = 'retrying', 'Retrying'

    class IngestStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        INGESTING = 'ingesting', 'Ingesting'
        INGESTED = 'ingested', 'Ingested'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    document_import_task = models.ForeignKey(
        QuestionDocumentImportTask, on_delete=models.CASCADE, related_name='items',
    )
    source_position = models.PositiveIntegerField()
    question_no = models.CharField(max_length=100, blank=True, default='')
    source_fingerprint = models.CharField(max_length=64, blank=True, default='', db_index=True)
    candidate_json = models.JSONField(default=dict)
    asset_files_json = models.JSONField(default=dict)
    prompt_version = models.CharField(max_length=64, default='document_structure:v1')
    model_name = models.CharField(max_length=100, default='qwen3.7-plus')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ingest_status = models.CharField(
        max_length=16, choices=IngestStatus.choices, default=IngestStatus.PENDING,
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    structured_result_json = models.JSONField(null=True, blank=True)
    ingest_result_json = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_message_safe = models.CharField(max_length=500, blank=True, default='')
    ingest_error_code = models.CharField(max_length=64, blank=True, default='')
    ingest_error_message_safe = models.CharField(max_length=500, blank=True, default='')
    celery_task_id = models.CharField(max_length=255, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    worker_heartbeat_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'question_document_import_item'
        constraints = [
            models.UniqueConstraint(
                fields=['document_import_task', 'source_position'],
                name='uq_document_import_item_task_position',
            ),
        ]
        indexes = [
            models.Index(
                fields=['document_import_task', 'status'],
                name='question_do_documen_7a6c0a_idx',
            ),
            models.Index(
                fields=['document_import_task', 'ingest_status'],
                name='question_do_documen_5df9c3_idx',
            ),
        ]
