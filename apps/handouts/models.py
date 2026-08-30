"""P2 teacher handout models."""
import uuid_utils.compat as uuid_compat
from django.conf import settings
from django.db import models


class Handout(models.Model):
    STATUS_CHOICES = [('draft', 'draft'), ('published', 'published'), ('archived', 'archived')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=50)
    stage = models.CharField(max_length=20, blank=True, default='')
    grade = models.CharField(max_length=50, blank=True, default='')
    creator_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_handouts',
    )
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handouts',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    version = models.PositiveIntegerField(default=1)
    pdf_file_path = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'handout'
        ordering = ['-updated_at']


class HandoutQuestion(models.Model):
    SOURCE_CHOICES = [
        ('question_bank', 'question_bank'), ('course', 'course'),
        ('ai', 'ai'), ('manual', 'manual'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    handout = models.ForeignKey(Handout, on_delete=models.CASCADE, related_name='questions')
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.PROTECT, related_name='handout_relations',
    )
    sort_no = models.PositiveIntegerField()
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='question_bank')
    display_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'handout_question'
        ordering = ['sort_no', 'id']
        constraints = [
            models.UniqueConstraint(fields=['handout', 'sort_no'], name='uq_handout_sort_no'),
            models.UniqueConstraint(fields=['handout', 'question'], name='uq_handout_question'),
        ]
