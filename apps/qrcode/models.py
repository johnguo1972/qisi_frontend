import uuid_utils.compat as uuid_compat
from django.db import models

from apps.accounts.models import UserAccount
from apps.institutions.models import Class
from apps.missions.models import LearningMission
from apps.wrongbook.models import WrongBookItem


class MissionShortCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE, related_name='short_codes')
    class_obj = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, db_column='class_id')
    short_code = models.CharField(max_length=6, unique=True, db_index=True)
    payload_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default='active')
    scan_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mission_short_code'
        constraints = [models.UniqueConstraint(fields=['mission', 'class_obj'], name='uq_mission_short_code_mission_class')]


class StudentClassShortCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='class_short_codes')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, db_column='class_id', related_name='student_short_codes')
    short_code = models.CharField(max_length=8, unique=True, db_index=True)
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_class_short_code'
        unique_together = [('student', 'class_obj')]


class AttemptImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    attempt = models.ForeignKey('study.AnswerAttempt', on_delete=models.CASCADE, related_name='images')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='attempt_images')
    question_id = models.UUIDField()
    image_url = models.CharField(max_length=1000)
    page_no = models.IntegerField(default=1)
    blur_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_blurry = models.BooleanField(default=False)
    upload_status = models.CharField(max_length=20, default='completed')
    file_size = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attempt_image'
        ordering = ['page_no']
        constraints = [models.UniqueConstraint(fields=['attempt', 'page_no'], name='uq_attempt_image_attempt_page')]


class WrongbookPracticeSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='practice_sheets')
    class_obj = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, db_column='class_id')
    wrong_item = models.ForeignKey(WrongBookItem, on_delete=models.CASCADE, related_name='practice_sheets')
    sheet_code = models.CharField(max_length=6, unique=True, db_index=True)
    original_question_id = models.UUIDField()
    variant_question_ids = models.JSONField(default=list, blank=True)
    wrong_reason_hint = models.TextField(blank=True, default='')
    mode = models.CharField(max_length=20, default='online')
    answers_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default='pending')
    submit_source = models.CharField(max_length=20, blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wrongbook_practice_sheet'


class PaperScanBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE, related_name='paper_scan_batches')
    operator = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name='paper_scan_batches')
    status = models.CharField(max_length=20, default='scanning')
    expected_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'paper_scan_batch'


class PaperScanPage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    batch = models.ForeignKey(PaperScanBatch, on_delete=models.CASCADE, related_name='pages')
    student = models.ForeignKey(UserAccount, on_delete=models.PROTECT, related_name='paper_scan_pages')
    student_code = models.CharField(max_length=8)
    mission_code = models.CharField(max_length=6)
    page_no = models.PositiveIntegerField()
    total_pages = models.PositiveIntegerField(default=1)
    image_url = models.CharField(max_length=1000)
    status = models.CharField(max_length=20, default='uploaded')
    error_code = models.CharField(max_length=30, blank=True, default='')
    error_message = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'paper_scan_page'
        constraints = [models.UniqueConstraint(fields=['batch', 'student', 'page_no'], name='uq_paper_scan_batch_student_page')]
