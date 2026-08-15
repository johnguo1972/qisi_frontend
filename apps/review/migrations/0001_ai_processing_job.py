import django.db.models.deletion
import uuid_utils.compat
from django.conf import settings
from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("parser", "0007_examquestion_json_source_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIQueueState",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
            ],
            options={"db_table": "review_ai_queue_state"},
        ),
        migrations.CreateModel(
            name="AIProcessingJob",
            fields=[
                ("id", models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("batch", "Batch"), ("legacy", "Legacy")], max_length=20)),
                ("model", models.CharField(blank=True, max_length=100, null=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="queued", max_length=20)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("creator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ai_processing_jobs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "review_ai_processing_job"},
        ),
        migrations.CreateModel(
            name="AIProcessingJobItem",
            fields=[
                ("id", models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("dispatched", "Dispatched"), ("running", "Running"), ("succeeded", "Succeeded"), ("partial", "Partial"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="queued", max_length=20)),
                ("model", models.CharField(blank=True, max_length=100, null=True)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("celery_task_id", models.UUIDField(blank=True, null=True, unique=True)),
                ("error_code", models.CharField(blank=True, default="", max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="review.aiprocessingjob")),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_processing_items", to="parser.examquestion")),
            ],
            options={"db_table": "review_ai_processing_job_item"},
        ),
        migrations.AddIndex(
            model_name="aiprocessingjob",
            index=models.Index(fields=["status", "created_at"], name="review_ai_p_status_834463_idx"),
        ),
        migrations.AddIndex(
            model_name="aiprocessingjobitem",
            index=models.Index(fields=["status", "created_at"], name="review_ai_p_status_0531d0_idx"),
        ),
        migrations.AddConstraint(
            model_name="aiprocessingjobitem",
            constraint=models.UniqueConstraint(condition=models.Q(("status__in", ("queued", "dispatched", "running"))), fields=("question",), name="review_ai_unique_active_question"),
        ),
    ]
