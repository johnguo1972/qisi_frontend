from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
import uuid_utils.compat as uuid_compat
from apps.accounts.models import UserAccount
from apps.missions.models import LearningMission, MissionLevel


class StudentMissionProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    progress_status = models.CharField(max_length=20, default='not_started')
    current_level = models.ForeignKey(
        MissionLevel, on_delete=models.SET_NULL, null=True, blank=True
    )
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    last_action_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_mission_progress'
        unique_together = ['mission', 'student_user_id']

    def __str__(self):
        return f"{self.mission.mission_no} - {self.student_user_id} ({self.progress_status})"


class StudentLevelProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    level = models.ForeignKey(MissionLevel, on_delete=models.CASCADE)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='locked')
    pass_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    attempt_count = models.IntegerField(default=0)
    passed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'student_level_progress'
        unique_together = ['level', 'student_user_id']

    def __str__(self):
        return f"L{self.level.level_no} - {self.student_user_id} ({self.status})"


class AnswerAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    mission = models.ForeignKey(LearningMission, on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey(MissionLevel, on_delete=models.SET_NULL, null=True, blank=True)
    question_id = models.UUIDField()
    attempt_no = models.IntegerField(default=1)
    answer_content = models.JSONField(default=dict)
    is_correct = models.BooleanField(default=False)
    is_subjective_pending = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    submit_source = models.CharField(max_length=20, default='manual')
    submitted_at = models.DateTimeField(auto_now_add=True)
    image_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=100, blank=True, default='', db_index=True)

    class Meta:
        db_table = 'answer_attempt'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Q{self.question_id} - Attempt {self.attempt_no} (correct={self.is_correct})"


class Favorite(models.Model):
    """Teacher's favorited questions."""
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, db_column='user_id')
    question_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_favorite'
        unique_together = ['user', 'question_id']
        ordering = ['-created_at']

    def __str__(self):
        return f"Favorite Q{self.question_id} by {self.user}"


class AIGuidanceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    question_id = models.UUIDField()
    mode_type = models.CharField(max_length=10)  # B/C
    session_status = models.CharField(max_length=20, default='running')
    invalid_input_count = models.IntegerField(default=0)
    script_source = models.CharField(max_length=20, default='ai_generated')
    content_log_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_guidance_session'

    def __str__(self):
        return f"AI Session Q{self.question_id} ({self.mode_type}) - {self.session_status}"


class QuestionBasket(models.Model):
    """教师题目篮子（类似购物车），用于批量操作和组卷。"""
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, db_column='user_id')
    question_id = models.UUIDField(db_index=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_question_basket'
        unique_together = ['user', 'question_id']
        ordering = ['-added_at']
        verbose_name = '题目篮子'
        verbose_name_plural = '题目篮子'

    def __str__(self):
        return f"Basket Q{self.question_id} by {self.user}"


class QuestionTag(models.Model):
    """自定义标签。"""
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name='标签名称')
    color = models.CharField(max_length=20, default='#409eff', verbose_name='标签颜色')
    created_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='创建者'
    )
    question_count = models.IntegerField(default=0, verbose_name='题目数量')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_question_tag'
        ordering = ['-question_count']
        verbose_name = '题目标签'
        verbose_name_plural = '题目标签'

    def __str__(self):
        return self.name


class QuestionTagRelation(models.Model):
    """题目-标签关联。"""
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.CASCADE,
        db_column='question_id'
    )
    tag = models.ForeignKey(
        QuestionTag, on_delete=models.CASCADE,
        db_column='tag_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_question_tag_relation'
        unique_together = ['question', 'tag']
        verbose_name = '题目标签关联'
        verbose_name_plural = '题目标签关联'


class QuestionRelation(models.Model):
    """A normalized, logically bidirectional relation between two questions."""

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    question_left = models.ForeignKey(
        'parser.ExamQuestion',
        on_delete=models.CASCADE,
        related_name='left_relations',
    )
    question_right = models.ForeignKey(
        'parser.ExamQuestion',
        on_delete=models.CASCADE,
        related_name='right_relations',
    )
    created_by = models.ForeignKey(
        UserAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_question_relation'
        constraints = [
            models.UniqueConstraint(
                fields=['question_left', 'question_right'],
                name='uq_question_relation_pair',
            ),
            models.CheckConstraint(
                condition=Q(question_left__lt=F('question_right')),
                name='ck_question_relation_canonical_pair',
            ),
        ]

    @classmethod
    def create_for_questions(cls, question_a, question_b, created_by):
        from .question_relation_service import canonical_question_pair

        left, right = canonical_question_pair(question_a, question_b)
        if left.pk == right.pk:
            raise ValidationError('题目不能关联自身')
        return cls.objects.create(
            question_left=left,
            question_right=right,
            created_by=created_by,
        )

    @classmethod
    def for_question(cls, question):
        return cls.objects.filter(Q(question_left=question) | Q(question_right=question))


class QuestionIngestionBatch(models.Model):
    """An auditable batch for one question creation or import operation."""

    class SourceType(models.TextChoices):
        JSON_IMPORT = 'json_import', 'JSON import'
        MANUAL_CREATE = 'manual_create', 'Manual create'
        PHOTO_CREATE = 'photo_create', 'Photo create'
        COURSE_MATERIAL_IMPORT = 'course_material_import', 'Course material import'
        COURSE_LINK_IMPORT = 'course_link_import', 'Course link import'

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        PARTIAL_SUCCESS = 'partial_success', 'Partial success'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    actor = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='question_ingestion_batches')
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='question_ingestion_batches',
    )
    paper = models.ForeignKey(
        'papers.ExamPaper', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='question_ingestion_batches',
    )
    source_name = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    total_read = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    skipped_existing_count = models.PositiveIntegerField(default=0)
    skipped_in_package_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'question_ingestion_batch'
        ordering = ['-finished_at', '-created_at']
