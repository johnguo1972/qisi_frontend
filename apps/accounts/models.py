from django.contrib.auth.models import AbstractBaseUser
from django.db import models


class UserAccount(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True)
    role_type = models.CharField(max_length=20)  # teacher/student/parent/admin
    login_name = models.CharField(max_length=64, blank=True, null=True)
    mobile = models.CharField(max_length=20, unique=True)
    display_name = models.CharField(max_length=64)
    subject = models.CharField(max_length=20, blank=True, null=True)  # teacher subject
    stages = models.JSONField(blank=True, null=True)  # teacher stages: ['小学', '初中', '高中']
    avatar_url = models.CharField(max_length=255, blank=True, null=True)
    grade_level = models.CharField(max_length=20, blank=True, null=True)  # student current grade: 一年级/二年级/.../九年级/高一/高二/高三
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'mobile'

    objects = models.Manager()

    class Meta:
        db_table = 'user_account'

    def __str__(self):
        return f"{self.display_name} ({self.role_type})"

    def is_active(self):
        return self.status == 'active'

    def is_staff(self):
        return self.role_type == 'admin'

    def is_superuser(self):
        return self.role_type == 'admin'


class StudentParentBind(models.Model):
    id = models.BigAutoField(primary_key=True)
    student_user_id = models.ForeignKey(
        UserAccount, on_delete=models.CASCADE, related_name='parent_binds_as_student'
    )
    parent_user_id = models.ForeignKey(
        UserAccount, on_delete=models.CASCADE, related_name='parent_binds_as_parent'
    )
    relation_type = models.CharField(max_length=20)  # father/mother/guardian
    bind_status = models.CharField(max_length=20, default='pending')
    bound_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_parent_bind'

    def __str__(self):
        return f"{self.student_user_id} <-> {self.parent_user_id} ({self.relation_type})"
