import string
import random

from django.db import models, transaction
import uuid_utils.compat as uuid_compat

from apps.accounts.models import UserAccount


def _generate_invite_code() -> str:
    """Generate an 8-character uppercase alphanumeric code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


class Institution(models.Model):
    """Educational institution (school, training center, etc.)."""

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
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

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='institution_memberships')
    role = models.CharField(max_length=20)  # admin/teacher
    status = models.CharField(max_length=20, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'institution_member'
        constraints = [
            models.UniqueConstraint(
                fields=['institution', 'user', 'role'],
                name='uq_institution_member_role',
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.institution} ({self.role})"


class Class(models.Model):
    """A class belonging to an institution, managed by teachers."""

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    class_no = models.CharField(max_length=20, unique=True, blank=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='classes')
    creator_teacher = models.ForeignKey(
        UserAccount, on_delete=models.SET_NULL, null=True,
        related_name='created_classes',
    )
    class_name = models.CharField(max_length=200)
    grade_level = models.CharField(max_length=20, blank=True, null=True)
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

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
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

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, db_column='class_id', related_name='class_students')
    student = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='student_classes')
    join_type = models.CharField(max_length=20)  # invite/manual/import
    status = models.CharField(max_length=20, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_student'
        unique_together = ('class_obj', 'student')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} in {self.class_obj}"


class StudentImportTask(models.Model):
    """Auditable batch import of students into one class."""
    STATUS_CHOICES = [
        ('uploaded', 'uploaded'), ('validating', 'validating'),
        ('partially_succeeded', 'partially_succeeded'),
        ('succeeded', 'succeeded'), ('failed', 'failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='student_imports')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='student_imports')
    uploaded_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, related_name='student_import_tasks')
    file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='uploaded')
    total_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_file_path = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'student_import_task'
        ordering = ['-created_at']


class StudentImportRow(models.Model):
    STATUS_CHOICES = [('matched', 'matched'), ('unmatched', 'unmatched'), ('failed', 'failed'), ('created', 'created')]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    task = models.ForeignKey(StudentImportTask, on_delete=models.CASCADE, related_name='rows')
    row_no = models.PositiveIntegerField()
    student = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_import_rows')
    raw_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='failed')
    error_code = models.CharField(max_length=50, blank=True, default='')
    error_message = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'student_import_row'
        constraints = [models.UniqueConstraint(fields=['task', 'row_no'], name='uq_student_import_task_row')]


class ClassJoinRequest(models.Model):
    """A request to join a class (for approval workflow)."""

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
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
