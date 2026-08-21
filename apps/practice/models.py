"""Models for the student's personal practice pool and practice sets."""
from django.conf import settings
from django.db import models
import uuid_utils.compat as uuid_compat

from apps.wrongbook.models import WrongBookItem


class PracticePoolItem(models.Model):
    SOURCE_TYPES = (
        ('original_wrong', '原错题'),
        ('recommended_variant', '关联题'),
        ('manual', '手工题'),
    )
    STATUS_CHOICES = (
        ('active', '有效'),
        ('removed', '已移除'),
    )

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_pool_items',
        db_column='student_user_id',
    )
    question_id = models.UUIDField(db_index=True)
    source_wrong_item = models.ForeignKey(
        WrongBookItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='practice_pool_items',
        db_column='source_wrong_item_id',
    )
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    recommendation_snapshot = models.JSONField(null=True, blank=True)
    display_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'practice_pool_item'
        constraints = [
            models.UniqueConstraint(
                fields=['student_user', 'question_id'],
                name='uq_practice_pool_student_question',
            ),
        ]
        indexes = [
            models.Index(
                fields=['student_user', 'status', 'created_at'],
                name='ix_pp_stu_st_created',
            ),
        ]


class PracticeSet(models.Model):
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('active', '练习中'),
        ('completed', '已完成'),
        ('archived', '已归档'),
    )
    ROLE_CHOICES = (
        ('student', '学生'),
        ('parent', '家长'),
    )

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_sets',
        db_column='student_user_id',
    )
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_practice_sets',
        db_column='created_by_user_id',
    )
    created_via_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    question_count = models.PositiveIntegerField(default=0)
    answered_count = models.PositiveIntegerField(default=0)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pdf_file_path = models.CharField(max_length=500, blank=True, default='')
    pdf_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'practice_set'
        indexes = [
            models.Index(
                fields=['student_user', 'status', 'updated_at'],
                name='ix_ps_stu_st_updated',
            ),
        ]


class PracticeSetItem(models.Model):
    SOURCE_TYPES = PracticePoolItem.SOURCE_TYPES

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    practice_set = models.ForeignKey(
        PracticeSet,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='practice_set_id',
    )
    pool_item = models.ForeignKey(
        PracticePoolItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='set_items',
        db_column='pool_item_id',
    )
    question_id = models.UUIDField()
    sort_no = models.PositiveIntegerField()
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    display_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'practice_set_item'
        constraints = [
            models.UniqueConstraint(
                fields=['practice_set', 'sort_no'],
                name='uq_practice_set_sort_no',
            ),
            models.UniqueConstraint(
                fields=['practice_set', 'question_id'],
                name='uq_practice_set_question',
            ),
        ]


class PracticeAttempt(models.Model):
    SUBMIT_SOURCES = (
        ('online', '在线'),
        ('photo', '照片'),
        ('paper', '纸笔'),
    )
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('pending_review', '待批阅'),
        ('graded', '已批阅'),
    )

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    practice_set = models.ForeignKey(
        PracticeSet,
        on_delete=models.CASCADE,
        related_name='attempts',
        db_column='practice_set_id',
    )
    set_item = models.ForeignKey(
        PracticeSetItem,
        on_delete=models.CASCADE,
        related_name='attempts',
        db_column='set_item_id',
    )
    student_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_attempts',
        db_column='student_user_id',
    )
    answer_content = models.JSONField(default=dict)
    submit_source = models.CharField(max_length=20, choices=SUBMIT_SOURCES, default='online')
    attempt_no = models.PositiveIntegerField(default=1)
    is_correct = models.BooleanField(null=True, blank=True)
    is_subjective_pending = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'practice_attempt'
        indexes = [
            models.Index(fields=['practice_set', 'set_item'], name='idx_practice_attempt_set_item'),
            models.Index(fields=['student_user', 'status'], name='ix_pa_stu_status'),
        ]


class PracticeAttemptImage(models.Model):
    STATUS_CHOICES = (
        ('uploaded', '已上传'),
        ('completed', '已完成'),
        ('rejected', '已拒绝'),
    )

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    attempt = models.ForeignKey(
        PracticeAttempt,
        on_delete=models.CASCADE,
        related_name='images',
        db_column='attempt_id',
    )
    student_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_attempt_images',
        db_column='student_user_id',
    )
    image_path = models.CharField(max_length=1000)
    page_no = models.PositiveIntegerField()
    blur_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_blurry = models.BooleanField(default=False)
    upload_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'practice_attempt_image'
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'page_no'],
                name='uq_practice_attempt_image_page',
            ),
        ]
