import uuid_utils.compat
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('institutions', '0002_multi_role_memberships'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentImportTask',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('file_path', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('uploaded', 'uploaded'), ('validating', 'validating'), ('partially_succeeded', 'partially_succeeded'), ('succeeded', 'succeeded'), ('failed', 'failed')], default='uploaded', max_length=30)),
                ('total_count', models.PositiveIntegerField(default=0)),
                ('success_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('error_file_path', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('class_obj', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_imports', to='institutions.class')),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_imports', to='institutions.institution')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_import_tasks', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'student_import_task', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='StudentImportRow',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('row_no', models.PositiveIntegerField()),
                ('raw_data', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('matched', 'matched'), ('unmatched', 'unmatched'), ('failed', 'failed'), ('created', 'created')], default='failed', max_length=20)),
                ('error_code', models.CharField(blank=True, default='', max_length=50)),
                ('error_message', models.CharField(blank=True, default='', max_length=255)),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_import_rows', to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='institutions.studentimporttask')),
            ],
            options={'db_table': 'student_import_row'},
        ),
        migrations.AddConstraint(
            model_name='studentimportrow',
            constraint=models.UniqueConstraint(fields=('task', 'row_no'), name='uq_student_import_task_row'),
        ),
    ]
