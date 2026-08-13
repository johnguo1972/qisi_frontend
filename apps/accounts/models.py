from django.contrib.auth.models import AbstractBaseUser
from django.db import models
import uuid_utils.compat as uuid_compat


class UserAccount(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
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

    def get_roles(self):
        from apps.accounts.roles import get_user_roles

        return get_user_roles(self)

    def has_role(self, role):
        from apps.accounts.roles import has_user_role

        return has_user_role(self, role)


class UserRole(models.Model):
    ROLE_CHOICES = [(role, role) for role in ("admin", "teacher", "parent", "student")]

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="role_grants")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, default="active")
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_role"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uq_user_role_user_role"),
        ]


class StudentParentBind(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
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


class WechatIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE, related_name='wechat_identity')
    appid = models.CharField(max_length=64)
    openid = models.CharField(max_length=128)
    unionid = models.CharField(max_length=128, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wechat_identity'
        constraints = [models.UniqueConstraint(fields=['appid', 'openid'], name='uq_wechat_appid_openid')]
