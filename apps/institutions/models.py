import string
import random

from django.db import models

from apps.accounts.models import UserAccount


def _generate_invite_code() -> str:
    """Generate an 8-character uppercase alphanumeric code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


class Institution(models.Model):
    """Educational institution (school, training center, etc.)."""

    id = models.BigAutoField(primary_key=True)
    institution_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.CharField(max_length=200, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')
    created_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_institutions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'institution'

    def __str__(self):
        return self.institution_name


class InstitutionMember(models.Model):
    """Links a UserAccount to an Institution with a role."""

    id = models.BigAutoField(primary_key=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='institution_memberships')
    role = models.CharField(max_length=20)  # admin/teacher
    status = models.CharField(max_length=20, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'institution_member'
        unique_together = ('institution', 'user')

    def __str__(self):
        return f"{self.user} @ {self.institution} ({self.role})"


class Class(models.Model):
    """A class belonging to an institution, managed by teachers."""

    id = models.BigAutoField(primary_key=True)
    class_no = models.CharField(max_length=20, unique=True, blank=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='classes')
    creator_teacher = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True,
        related_name='created_classes',
    )
    class_name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    max_students = models.IntegerField(default=50)
    invite_code = models.CharField(max_length=8, unique=True, blank=True)
    allow_invite_join = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'class'

    def __str__(self):
        return self.class_name

    def save(self, *args, **kwargs):
        if not self.class_no:
            # Generate class number: CLS-XXXXXXXX (8 digits)
            self.class_no = f'CLS-{random.randint(10000000, 99999999)}'
        if not self.invite_code:
            self.invite_code = _generate_invite_code()
        super().save(*args, **kwargs)


class ClassTeacher(models.Model):
    """Links a teacher to a class."""

    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, db_column='class_id', related_name='class_teachers')
    teacher = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='teacher_classes')
    role = models.CharField(max_length=20)  # owner/co_teacher

    class Meta:
        db_table = 'class_teacher'
        unique_together = ('class_obj', 'teacher')

    def __str__(self):
        return f"{self.teacher} in {self.class_obj} ({self.role})"


class ClassStudent(models.Model):
    """Links a student to a class."""

    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, db_column='class_id', related_name='class_students')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='student_classes')
    join_type = models.CharField(max_length=20)  # invite/manual/import
    status = models.CharField(max_length=20, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_student'
        unique_together = ('class_obj', 'student')

    def __str__(self):
        return f"{self.student} in {self.class_obj}"


class ClassJoinRequest(models.Model):
    """A request to join a class (for approval workflow)."""

    id = models.BigAutoField(primary_key=True)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, db_column='class_id', related_name='join_requests')
    applicant = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='join_requests')
    applicant_name = models.CharField(max_length=100)
    applicant_phone = models.CharField(max_length=20, blank=True, null=True)
    request_type = models.CharField(max_length=20)  # invite_code/self_apply
    status = models.CharField(max_length=20, default='pending')  # pending/approved/rejected
    message = models.TextField(blank=True, null=True)
    handled_by = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handled_join_requests',
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_join_request'

    def __str__(self):
        return f"{self.applicant_name} -> {self.class_obj} ({self.status})"
