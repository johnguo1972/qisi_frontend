"""Durable, business-level queue records for AI question processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import uuid_utils.compat as uuid_compat
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.parser.models import ExamQuestion


class AIQueueCapacityExceeded(Exception):
    """Raised before creating records when the durable queue is full."""


@dataclass(frozen=True)
class JobCreateResult:
    job: "AIProcessingJob | None"
    accepted_count: int
    duplicate_question_ids: list[str]


class AIQueueState(models.Model):
    """Single row used as the transaction lock for global queue capacity."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        db_table = "review_ai_queue_state"


class AIProcessingJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        CANCELLED = "cancelled"

    class Source(models.TextChoices):
        MANUAL = "manual"
        BATCH = "batch"
        LEGACY = "legacy"

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ai_processing_jobs",
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    model = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    cancel_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def create_for_questions(
        cls,
        *,
        creator,
        question_ids: Iterable[object],
        source: str,
        model: str | None,
    ) -> JobCreateResult:
        normalized_ids = list(dict.fromkeys(str(question_id) for question_id in question_ids))
        questions = list(ExamQuestion.objects.filter(id__in=normalized_ids))
        question_by_id = {str(question.id): question for question in questions}
        ordered_questions = [question_by_id[question_id] for question_id in normalized_ids if question_id in question_by_id]

        with transaction.atomic():
            AIQueueState.objects.get_or_create(pk=1)
            AIQueueState.objects.select_for_update().get(pk=1)

            active_question_ids = set(
                AIProcessingJobItem.objects.select_for_update()
                .filter(
                    question_id__in=[question.id for question in ordered_questions],
                    status__in=AIProcessingJobItem.active_statuses(),
                )
                .values_list("question_id", flat=True)
            )
            accepted_questions = [
                question for question in ordered_questions if question.id not in active_question_ids
            ]
            duplicate_question_ids = [
                str(question.id) for question in ordered_questions if question.id in active_question_ids
            ]
            capacity = int(getattr(settings, "AI_QUEUE_CAPACITY", 10000))
            active_count = AIProcessingJobItem.objects.filter(
                status__in=AIProcessingJobItem.active_statuses()
            ).count()
            if active_count + len(accepted_questions) > capacity:
                raise AIQueueCapacityExceeded("ai_queue_capacity_exceeded")
            if not accepted_questions:
                return JobCreateResult(None, 0, duplicate_question_ids)

            job = cls.objects.create(creator=creator, source=source, model=model)
            AIProcessingJobItem.objects.bulk_create([
                AIProcessingJobItem(job=job, question=question, model=model)
                for question in accepted_questions
            ])
            return JobCreateResult(job, len(accepted_questions), duplicate_question_ids)

    @classmethod
    def sync_status_from_items(cls, job_id: object) -> str:
        """Persist the durable job state derived from its item states.

        Queue dispatch only considers a bounded window of jobs.  Keeping a
        finished job marked queued would otherwise let it occupy that window
        forever and starve newer queued work.
        """
        with transaction.atomic():
            job = cls.objects.select_for_update().get(id=job_id)
            item_statuses = list(job.items.values_list("status", flat=True))
            active_statuses = AIProcessingJobItem.active_statuses()
            if not item_statuses or not any(
                status in active_statuses for status in item_statuses
            ):
                status = (
                    cls.Status.CANCELLED
                    if job.cancel_requested
                    else cls.Status.COMPLETED
                )
            elif any(
                status in {
                    AIProcessingJobItem.Status.DISPATCHED,
                    AIProcessingJobItem.Status.RUNNING,
                }
                for status in item_statuses
            ):
                status = cls.Status.RUNNING
            else:
                status = cls.Status.QUEUED

            update_fields: list[str] = []
            if job.status != status:
                job.status = status
                update_fields.append("status")
            if status in {cls.Status.COMPLETED, cls.Status.CANCELLED}:
                if job.finished_at is None:
                    job.finished_at = timezone.now()
                    update_fields.append("finished_at")
            elif status == cls.Status.RUNNING and job.started_at is None:
                job.started_at = timezone.now()
                update_fields.append("started_at")
            if update_fields:
                job.save(update_fields=update_fields)
            return status

    class Meta:
        db_table = "review_ai_processing_job"
        indexes = [models.Index(fields=["status", "created_at"])]


class AIProcessingJobItem(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        DISPATCHED = "dispatched"
        RUNNING = "running"
        SUCCEEDED = "succeeded"
        PARTIAL = "partial"
        FAILED = "failed"
        CANCELLED = "cancelled"

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    job = models.ForeignKey(AIProcessingJob, on_delete=models.CASCADE, related_name="items")
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="ai_processing_items")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    model = models.CharField(max_length=100, null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.UUIDField(null=True, blank=True, unique=True)
    error_code = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def active_statuses(cls) -> tuple[str, ...]:
        return (cls.Status.QUEUED, cls.Status.DISPATCHED, cls.Status.RUNNING)

    class Meta:
        db_table = "review_ai_processing_job_item"
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(status__in=("queued", "dispatched", "running")),
                name="review_ai_unique_active_question",
            )
        ]
