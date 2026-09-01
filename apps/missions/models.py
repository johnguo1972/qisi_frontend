import uuid
from django.db import models
import uuid_utils.compat as uuid_compat
from apps.accounts.models import UserAccount


class LearningMission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission_no = models.CharField(max_length=32, unique=True, editable=False)
    mission_name = models.CharField(max_length=120)
    goal_text = models.CharField(max_length=255, blank=True, default='')
    creator_teacher_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default='draft')
    # New assignments use one flat question list.  The legacy level mode is
    # retained so existing assignments can continue to be answered and graded.
    assignment_mode = models.CharField(max_length=20, default='levels')
    mission_kind = models.CharField(max_length=30, default='regular')
    source_type = models.CharField(max_length=30, default='question_bank')
    # Phase 4 wrong-book matrix provenance. Nullable to preserve legacy missions.
    source_matrix_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_generation_batch_id = models.UUIDField(null=True, blank=True, db_index=True)
    parent_mission_id = models.UUIDField(null=True, blank=True, db_index=True)
    class_obj = models.ForeignKey(
        'institutions.Class', on_delete=models.SET_NULL,
        null=True, blank=True, db_column='class_id',
        related_name='class_missions',
        verbose_name='所属班级',
    )
    default_mode_policy = models.CharField(max_length=50, blank=True, null=True)
    target_student_ids = models.JSONField(default=list, blank=True)
    course = models.ForeignKey(
        'courses.Course', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='course_id', related_name='learning_missions',
    )
    # The worksheet PDF generated when a mission is published.  Keep the
    # storage-relative path so all clients can receive a stable media URL.
    pdf_file_path = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'learning_mission'

    def save(self, *args, **kwargs):
        if not self.mission_no:
            self.mission_no = f"MS{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mission_no} - {self.mission_name}"

    @property
    def creator_teacher(self):
        """Alias for the FK field named creator_teacher_id."""
        return self.creator_teacher_id


class MissionClassAssignment(models.Model):
    """A class-specific publication of a mission.

    ``LearningMission.class_obj`` remains for one release cycle so old data and
    clients continue to work. New code should use this relation whenever it
    needs the set of assigned classes.
    """
    STATUS_CHOICES = [('active', 'active'), ('removed', 'removed')]

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE, related_name='class_assignments')
    class_obj = models.ForeignKey(
        'institutions.Class', on_delete=models.CASCADE, related_name='mission_assignments',
        db_column='class_id',
    )
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    target_student_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mission_class_assignment'
        constraints = [
            models.UniqueConstraint(
                fields=['mission', 'class_obj'], name='uq_mission_class_assignment',
            ),
        ]
        indexes = [models.Index(fields=['class_obj', 'status'], name='idx_mca_class_status')]


class MissionLevel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE, related_name='levels')
    level_no = models.IntegerField()
    level_name = models.CharField(max_length=100)
    level_type = models.CharField(max_length=30)  # practice/review/retry/variant/check
    pass_rule_json = models.JSONField(default=dict)
    mode_policy = models.CharField(max_length=50, blank=True, null=True)
    hint_strength = models.CharField(max_length=20, default='medium')

    class Meta:
        db_table = 'mission_level'
        ordering = ['level_no']

    def __str__(self):
        return f"{self.mission.mission_no} - L{self.level_no}: {self.level_name}"


class MissionQuestionRel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE)
    level = models.ForeignKey(MissionLevel, on_delete=models.CASCADE)
    question_id = models.UUIDField()
    sort_no = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    source_type = models.CharField(max_length=20, default='manual_select')
    target_student_ids = models.JSONField(default=list, blank=True)
    # P2 publication snapshot: later edits to the source question must not
    # change an already published class mission.
    question_snapshot = models.JSONField(null=True, blank=True)
    # Per-student provenance for personalized LearningMission relations.
    source_matrix_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_student_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_wrong_book_item_id = models.UUIDField(null=True, blank=True, db_index=True)
    source_role = models.CharField(max_length=30, blank=True, default='')
    source_provider = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table = 'mission_question_rel'
        ordering = ['sort_no']
        constraints = [
            models.UniqueConstraint(
                fields=['mission', 'source_student_id', 'question_id', 'source_wrong_book_item_id'],
                name='uq_mission_phase4_source_question',
            ),
        ]

    def __str__(self):
        return f"{self.mission.mission_no} - Q{self.question_id} (sort={self.sort_no})"


class TeacherWrongBookMatrix(models.Model):
    """A teacher's sparse, versioned wrong-question matrix for one source mission."""
    STATUS_CHOICES = [
        ('draft', 'draft'), ('saved', 'saved'), ('generating', 'generating'),
        ('generated', 'generated'), ('partially_failed', 'partially_failed'),
        ('scope_changed', 'scope_changed'), ('closed', 'closed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    source_mission = models.ForeignKey(
        LearningMission, on_delete=models.CASCADE, related_name='wrongbook_matrices',
    )
    creator_teacher = models.ForeignKey(
        UserAccount, on_delete=models.CASCADE, related_name='wrongbook_matrices',
    )
    class_obj = models.ForeignKey(
        'institutions.Class', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='class_id', related_name='wrongbook_matrices',
    )
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    marked_count = models.PositiveIntegerField(default=0)
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    last_generation_batch_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_wrongbook_matrix'
        constraints = [
            models.UniqueConstraint(
                fields=['source_mission'], name='uq_wrongbook_matrix_source_mission',
            ),
        ]


class TeacherWrongBookMatrixStudent(models.Model):
    STATUS_CHOICES = [('active', 'active'), ('removed', 'removed')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='students')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wrongbook_matrix_memberships')
    class_obj = models.ForeignKey('institutions.Class', on_delete=models.CASCADE, db_column='class_id')
    source_assignment_id = models.UUIDField(null=True, blank=True)
    student_name_snapshot = models.CharField(max_length=100, blank=True, default='')
    student_no_snapshot = models.CharField(max_length=100, blank=True, default='')
    class_name_snapshot = models.CharField(max_length=200, blank=True, default='')
    sort_no = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        db_table = 'teacher_wrongbook_matrix_student'
        constraints = [
            models.UniqueConstraint(
                fields=['matrix', 'student', 'class_obj'], name='uq_wrongbook_matrix_student_class',
            ),
        ]
        ordering = ['sort_no', 'student_name_snapshot', 'id']


class TeacherWrongBookMatrixQuestion(models.Model):
    STATUS_CHOICES = [('active', 'active'), ('removed', 'removed')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='questions')
    source_question_id = models.UUIDField()
    source_relation = models.ForeignKey(MissionQuestionRel, on_delete=models.CASCADE, related_name='wrongbook_matrix_questions')
    question_no_snapshot = models.CharField(max_length=50, blank=True, default='')
    sort_no = models.PositiveIntegerField(default=0)
    question_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        db_table = 'teacher_wrongbook_matrix_question'
        constraints = [
            models.UniqueConstraint(
                fields=['matrix', 'source_question_id'], name='uq_wrongbook_matrix_question',
            ),
        ]
        ordering = ['sort_no', 'id']


class TeacherWrongBookCell(models.Model):
    STATUS_CHOICES = [
        ('marked', 'marked'), ('cancelled', 'cancelled'),
        ('generated', 'generated'), ('locked', 'locked'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='cells')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wrongbook_matrix_cells')
    source_question_id = models.UUIDField()
    source_relation = models.ForeignKey(MissionQuestionRel, on_delete=models.CASCADE, related_name='wrongbook_matrix_cells')
    wrong_book_item = models.ForeignKey('wrongbook.WrongBookItem', on_delete=models.PROTECT, related_name='teacher_matrix_cells')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='marked')
    marked_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='marked_wrongbook_cells')
    marked_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    generated_batch_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teacher_wrongbook_cell'
        constraints = [
            models.UniqueConstraint(
                fields=['matrix', 'student', 'source_question_id'], name='uq_wrongbook_matrix_cell',
            ),
        ]


class WrongBookGenerationBatch(models.Model):
    STATUS_CHOICES = [
        ('queued', 'queued'), ('generating', 'generating'), ('snapshotting', 'snapshotting'),
        ('publishing', 'publishing'), ('awaiting_selection', 'awaiting_selection'),
        ('published', 'published'),
        ('partially_failed', 'partially_failed'), ('failed', 'failed'), ('retrying', 'retrying'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='generation_batches')
    requested_by = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wrongbook_generation_batches')
    request_version = models.PositiveIntegerField()
    request_cell_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='queued')
    related_limit = models.PositiveSmallIntegerField(default=3)
    generation_mode = models.CharField(max_length=30, default='legacy')
    candidate_limit = models.PositiveSmallIntegerField(default=10)
    selection_limit = models.PositiveSmallIntegerField(default=3)
    requested_count = models.PositiveIntegerField(default=0)
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    published_task_count = models.PositiveIntegerField(default=0)
    error_json = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=100)
    ai_confirmation_key = models.CharField(max_length=100, blank=True, default='')
    ai_supplement_mission_id = models.UUIDField(null=True, blank=True)
    teacher_selection_confirmation_key = models.CharField(max_length=100, blank=True, default='')
    final_mission_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wrongbook_generation_batch'
        constraints = [
            models.UniqueConstraint(
                fields=['matrix', 'idempotency_key'], name='uq_wrongbook_generation_idempotency',
            ),
        ]
        ordering = ['-created_at']


class WrongBookGenerationItem(models.Model):
    STATUS_CHOICES = [
        ('queued', 'queued'), ('generating', 'generating'), ('generated', 'generated'),
        ('snapshot_failed', 'snapshot_failed'), ('published', 'published'),
        ('publish_failed', 'publish_failed'), ('failed', 'failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    batch = models.ForeignKey(WrongBookGenerationBatch, on_delete=models.CASCADE, related_name='items')
    cell = models.ForeignKey(TeacherWrongBookCell, on_delete=models.CASCADE, related_name='generation_items')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wrongbook_generation_items')
    source_question_id = models.UUIDField()
    source_wrong_book_item = models.ForeignKey('wrongbook.WrongBookItem', on_delete=models.PROTECT, related_name='generation_items')
    related_question_ids = models.JSONField(default=list, blank=True)
    selected_question_ids = models.JSONField(default=list, blank=True)
    selected_count = models.PositiveSmallIntegerField(default=0)
    shortage_reason = models.CharField(max_length=255, blank=True, default='')
    selection_required = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='queued')
    target_mission = models.ForeignKey(LearningMission, on_delete=models.SET_NULL, null=True, blank=True, related_name='wrongbook_generation_items')
    error_code = models.CharField(max_length=50, blank=True, default='')
    error_stage = models.CharField(max_length=30, blank=True, default='')
    error_message = models.CharField(max_length=500, blank=True, default='')
    result_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wrongbook_generation_item'
        constraints = [
            models.UniqueConstraint(fields=['batch', 'cell'], name='uq_wrongbook_generation_item_cell'),
        ]


class RelatedQuestionRecommendation(models.Model):
    STATUS_CHOICES = [
        ('suggested', 'suggested'), ('teacher_selected', 'teacher_selected'),
        ('rejected', 'rejected'), ('discarded', 'discarded'),
    ]
    PROVIDER_CHOICES = [('rule', 'rule'), ('ai', 'ai')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='recommendations')
    source_batch = models.ForeignKey(WrongBookGenerationBatch, on_delete=models.CASCADE, related_name='recommendations')
    source_student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wrongbook_recommendations')
    source_question_id = models.UUIDField()
    source_wrong_book_item = models.ForeignKey('wrongbook.WrongBookItem', on_delete=models.PROTECT, related_name='recommendations')
    candidate_question_id = models.UUIDField()
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=100, blank=True, default='')
    prompt_version = models.CharField(max_length=50, blank=True, default='')
    score = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    confidence = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')
    discard_reason = models.CharField(max_length=255, blank=True, default='')
    requested_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='requested_wrongbook_recommendations')
    confirmed_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='confirmed_wrongbook_recommendations')
    result_json = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'related_question_recommendation'
        constraints = [
            models.UniqueConstraint(
                fields=['matrix', 'source_batch', 'source_student', 'source_question_id', 'candidate_question_id'],
                name='uq_wrongbook_recommendation_candidate',
            ),
        ]


class RelatedQuestionRecommendationCall(models.Model):
    STATUS_CHOICES = [('queued', 'queued'), ('succeeded', 'succeeded'), ('failed', 'failed')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='recommendation_calls')
    source_batch = models.ForeignKey(WrongBookGenerationBatch, on_delete=models.CASCADE, related_name='recommendation_calls')
    provider = models.CharField(max_length=20, default='ai')
    model_name = models.CharField(max_length=100, blank=True, default='')
    prompt_version = models.CharField(max_length=50, blank=True, default='')
    request_json = models.JSONField(default=dict, blank=True)
    returned_count = models.PositiveIntegerField(default=0)
    call_count = models.PositiveIntegerField(default=1)
    cost_json = models.JSONField(default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    error_message = models.CharField(max_length=500, blank=True, default='')
    trace_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'related_question_recommendation_call'


class TeacherWrongBookMatrixAudit(models.Model):
    ACTION_CHOICES = [
        ('scope_created', 'scope_created'), ('scope_refreshed', 'scope_refreshed'),
        ('mark_saved', 'mark_saved'), ('mark_cancelled', 'mark_cancelled'),
        ('generation_requested', 'generation_requested'), ('generation_completed', 'generation_completed'),
        ('recommendation_requested', 'recommendation_requested'), ('recommendation_confirmed', 'recommendation_confirmed'),
        ('retry_requested', 'retry_requested'), ('matrix_closed', 'matrix_closed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    matrix = models.ForeignKey(TeacherWrongBookMatrix, on_delete=models.CASCADE, related_name='audits')
    actor = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='wrongbook_matrix_audits')
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    version = models.PositiveIntegerField(null=True, blank=True)
    batch = models.ForeignKey(WrongBookGenerationBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='audits')
    payload = models.JSONField(default=dict, blank=True)
    trace_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teacher_wrongbook_matrix_audit'
        ordering = ['-created_at']
