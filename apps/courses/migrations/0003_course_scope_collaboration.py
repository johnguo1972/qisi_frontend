from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid_utils.compat


SUBJECT_ALIASES = {
    '语文': 'chinese', 'chinese': 'chinese',
    '数学': 'math', 'math': 'math',
    '英语': 'english', 'english': 'english',
    '物理': 'physics', 'physics': 'physics',
    '化学': 'chemistry', 'chemistry': 'chemistry',
    '生物': 'biology', 'biology': 'biology',
    '地理': 'geography', 'geography': 'geography',
    '历史': 'history', 'history': 'history',
}


def normalize_existing_course_data(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    InstitutionMember = apps.get_model('institutions', 'InstitutionMember')
    UserAccount = apps.get_model('accounts', 'UserAccount')

    for user in UserAccount.objects.all().iterator():
        raw_subjects = user.subjects if isinstance(user.subjects, list) else [user.subject]
        subjects = []
        for value in raw_subjects:
            code = SUBJECT_ALIASES.get((value or '').strip().lower())
            if code and code not in subjects:
                subjects.append(code)
        if subjects or user.subjects:
            UserAccount.objects.filter(pk=user.pk).update(
                subject=subjects[0] if subjects else None,
                subjects=subjects or None,
            )

    for course in Course.objects.all().iterator():
        subject = SUBJECT_ALIASES.get((course.subject or '').strip().lower(), course.subject)
        membership_ids = list(
            InstitutionMember.objects.filter(
                user_id=course.teacher_id,
                role='teacher',
                status='active',
            ).values_list('institution_id', flat=True).distinct()
        )
        updates = {'subject': subject}
        if len(membership_ids) == 1:
            updates['institution_id'] = membership_ids[0]
        Course.objects.filter(pk=course.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_useraccount_subjects'),
        ('institutions', '0002_multi_role_memberships'),
        ('courses', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='institution',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='courses',
                to='institutions.institution',
                verbose_name='所属机构',
            ),
        ),
        migrations.CreateModel(
            name='CourseCollaborator',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('viewer', 'viewer'), ('editor', 'editor')], default='viewer', max_length=20)),
                ('status', models.CharField(default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='collaborators', to='courses.course')),
                ('granted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_course_collaborations', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_collaborations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'course_collaborator',
                'constraints': [models.UniqueConstraint(fields=('course', 'user'), name='uq_course_collaborator_course_user')],
            },
        ),
        migrations.CreateModel(
            name='CourseAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_audit_actions', to=settings.AUTH_USER_MODEL)),
                ('course', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='courses.course')),
                ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_audit_targets', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'course_audit_log', 'ordering': ['-created_at']},
        ),
        migrations.RunPython(normalize_existing_course_data, migrations.RunPython.noop),
    ]
