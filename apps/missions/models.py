import uuid
from django.db import models
from apps.accounts.models import UserAccount


class LearningMission(models.Model):
    id = models.BigAutoField(primary_key=True)
    mission_no = models.CharField(max_length=32, unique=True, editable=False)
    mission_name = models.CharField(max_length=120)
    goal_text = models.CharField(max_length=255, blank=True, default='')
    creator_teacher_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    start_at = models.DateTimeField(blank=True, null=True)
    end_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default='draft')
    class_obj = models.ForeignKey(
        'institutions.Class', on_delete=models.SET_NULL,
        null=True, blank=True, db_column='class_id',
        related_name='class_missions',
        verbose_name='所属班级',
    )
    default_mode_policy = models.CharField(max_length=50, blank=True, null=True)
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


class MissionLevel(models.Model):
    id = models.BigAutoField(primary_key=True)
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
    id = models.BigAutoField(primary_key=True)
    mission = models.ForeignKey(LearningMission, on_delete=models.CASCADE)
    level = models.ForeignKey(MissionLevel, on_delete=models.CASCADE)
    question_id = models.IntegerField()
    sort_no = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True)
    source_type = models.CharField(max_length=20, default='manual_select')

    class Meta:
        db_table = 'mission_question_rel'
        ordering = ['sort_no']

    def __str__(self):
        return f"{self.mission.mission_no} - Q{self.question_id} (sort={self.sort_no})"
