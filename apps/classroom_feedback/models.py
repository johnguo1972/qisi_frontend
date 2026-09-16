import uuid_utils.compat as uuid_compat
from django.db import models


class ClassroomFeedbackReport(models.Model):
    STATUS_CHOICES = [
        ('queued', '排队中'), ('running', '生成中'), ('ready', '已完成'),
        ('partial', '部分完成'), ('failed', '失败'), ('stale', '数据已更新'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    mission = models.ForeignKey('missions.LearningMission', on_delete=models.CASCADE, related_name='classroom_feedback_reports')
    class_obj = models.ForeignKey('institutions.Class', on_delete=models.CASCADE, related_name='classroom_feedback_reports')
    source_matrix = models.ForeignKey('missions.TeacherWrongBookMatrix', on_delete=models.PROTECT, related_name='classroom_feedback_reports')
    source_matrix_version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    generation_no = models.PositiveIntegerField(default=1)
    idempotency_key = models.CharField(max_length=100, blank=True, default='')
    participant_count = models.PositiveIntegerField(default=0)
    question_count = models.PositiveIntegerField(default=0)
    total_wrong_count = models.PositiveIntegerField(default=0)
    average_wrong_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class_summary_json = models.JSONField(default=dict, blank=True)
    class_feedback_text = models.TextField(blank=True, default='')
    input_snapshot = models.JSONField(default=dict, blank=True)
    prompt_version = models.CharField(max_length=50, default='classroom-feedback-v1')
    model_name = models.CharField(max_length=100, default='qwen3.7-flash')
    pdf_file_path = models.CharField(max_length=500, blank=True, default='')
    error_message = models.CharField(max_length=1000, blank=True, default='')
    created_by = models.ForeignKey('accounts.UserAccount', on_delete=models.SET_NULL, null=True, related_name='classroom_feedback_reports_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'classroom_feedback_report'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mission', 'class_obj', '-created_at'], name='cf_report_mission_class_idx'),
            models.Index(fields=['source_matrix', 'source_matrix_version'], name='cf_report_matrix_ver_idx'),
        ]


class ClassroomFeedbackQuestionStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    report = models.ForeignKey(ClassroomFeedbackReport, on_delete=models.CASCADE, related_name='question_stats')
    source_question_id = models.UUIDField()
    node_id = models.UUIDField(null=True, blank=True)
    node_name_snapshot = models.CharField(max_length=200, blank=True, default='')
    node_sort_no = models.PositiveIntegerField(default=0)
    question_no = models.CharField(max_length=50, blank=True, default='')
    wrong_count = models.PositiveIntegerField(default=0)
    wrong_rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    knowledge_labels = models.JSONField(default=list, blank=True)
    question_snapshot = models.JSONField(default=dict, blank=True)
    sort_no = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'classroom_feedback_question_stat'
        constraints = [models.UniqueConstraint(fields=['report', 'source_question_id'], name='cf_question_report_source_unique')]
        ordering = ['sort_no', 'id']


class ClassroomFeedbackKnowledgeStat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    report = models.ForeignKey(ClassroomFeedbackReport, on_delete=models.CASCADE, related_name='knowledge_stats')
    knowledge_key = models.CharField(max_length=120)
    knowledge_name = models.CharField(max_length=255)
    question_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    denominator = models.PositiveIntegerField(default=0)
    error_rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    mastery_level = models.CharField(max_length=30, default='attention')
    question_ids = models.JSONField(default=list, blank=True)
    sort_no = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'classroom_feedback_knowledge_stat'
        constraints = [models.UniqueConstraint(fields=['report', 'knowledge_key'], name='cf_knowledge_report_key_unique')]
        ordering = ['sort_no', 'knowledge_name', 'id']


class ClassroomFeedbackStudent(models.Model):
    AI_STATUS_CHOICES = [('pending', '待生成'), ('succeeded', '已生成'), ('fallback', '规则兜底'), ('failed', '失败')]

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    report = models.ForeignKey(ClassroomFeedbackReport, on_delete=models.CASCADE, related_name='student_feedbacks')
    student = models.ForeignKey('accounts.UserAccount', on_delete=models.PROTECT, related_name='classroom_feedback_rows')
    student_name_snapshot = models.CharField(max_length=100, blank=True, default='')
    class_name_snapshot = models.CharField(max_length=200, blank=True, default='')
    student_no_snapshot = models.CharField(max_length=100, blank=True, default='')
    wrong_question_ids = models.JSONField(default=list, blank=True)
    wrong_question_nos = models.JSONField(default=list, blank=True)
    wrong_count = models.PositiveIntegerField(default=0)
    wrong_rate = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    knowledge_summary = models.JSONField(default=list, blank=True)
    review_arrangement = models.JSONField(default=list, blank=True)
    feedback_text = models.TextField(blank=True, default='')
    ai_status = models.CharField(max_length=20, choices=AI_STATUS_CHOICES, default='pending')
    ai_model = models.CharField(max_length=100, default='qwen3.7-flash')
    prompt_version = models.CharField(max_length=50, default='classroom-feedback-v1')
    ai_input_fingerprint = models.CharField(max_length=64, blank=True, default='')
    ai_error_message = models.CharField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'classroom_feedback_student'
        constraints = [models.UniqueConstraint(fields=['report', 'student'], name='cf_student_report_student_unique')]
        ordering = ['student_name_snapshot', 'student_no_snapshot', 'id']
