from django.db import models
from apps.accounts.models import UserAccount


class WrongBookItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    question_id = models.IntegerField()
    first_wrong_at = models.DateTimeField(auto_now_add=True)
    latest_wrong_at = models.DateTimeField(auto_now=True)
    wrong_reason_type = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=20, default='not_reviewed')
    retry_count = models.IntegerField(default=0)
    variant_done_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'wrong_book_item'
        unique_together = ['student_user_id', 'question_id']

    def __str__(self):
        return f"Q{self.question_id} - {self.student_user_id} ({self.status})"


class MasteryRecord(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    mastery_type = models.CharField(max_length=20)  # question/knowledge
    target_code = models.CharField(max_length=64)
    mastery_status = models.CharField(max_length=20, default='not_mastered')
    mastery_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    next_review_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mastery_record'

    def __str__(self):
        return f"{self.mastery_type}:{self.target_code} - {self.student_user_id} ({self.mastery_status})"
