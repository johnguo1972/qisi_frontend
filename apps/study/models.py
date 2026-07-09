from django.db import models
from apps.accounts.models import UserAccount
from apps.missions.models import LearningMission, MissionLevel


class StudentMissionProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
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
    id = models.BigAutoField(primary_key=True)
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
    id = models.BigAutoField(primary_key=True)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    mission = models.ForeignKey(LearningMission, on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey(MissionLevel, on_delete=models.SET_NULL, null=True, blank=True)
    question_id = models.IntegerField()
    attempt_no = models.IntegerField(default=1)
    answer_content = models.JSONField(default=dict)
    is_correct = models.BooleanField(default=False)
    is_subjective_pending = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    submit_source = models.CharField(max_length=20, default='manual')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'answer_attempt'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Q{self.question_id} - Attempt {self.attempt_no} (correct={self.is_correct})"


class Favorite(models.Model):
    """Teacher's favorited questions."""
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, db_column='user_id')
    question_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_favorite'
        unique_together = ['user', 'question_id']
        ordering = ['-created_at']

    def __str__(self):
        return f"Favorite Q{self.question_id} by {self.user}"


class AIGuidanceSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    question_id = models.IntegerField()
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
