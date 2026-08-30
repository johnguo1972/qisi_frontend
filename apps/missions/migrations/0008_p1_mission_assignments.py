import uuid_utils.compat
from django.db import migrations, models
import django.db.models.deletion


def backfill_legacy_class_assignments(apps, schema_editor):
    LearningMission = apps.get_model('missions', 'LearningMission')
    MissionClassAssignment = apps.get_model('missions', 'MissionClassAssignment')
    for mission in LearningMission.objects.exclude(class_obj__isnull=True).iterator():
        MissionClassAssignment.objects.get_or_create(
            mission_id=mission.id,
            class_obj_id=mission.class_obj_id,
            defaults={
                'start_at': mission.start_at,
                'end_at': mission.end_at,
                'target_student_ids': mission.target_student_ids or [],
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0007_learningmission_pdf_file_path'),
        ('institutions', '0002_multi_role_memberships'),
    ]

    operations = [
        migrations.AddField(
            model_name='learningmission', name='mission_kind',
            field=models.CharField(default='regular', max_length=30),
        ),
        migrations.AddField(
            model_name='learningmission', name='source_type',
            field=models.CharField(default='question_bank', max_length=30),
        ),
        migrations.CreateModel(
            name='MissionClassAssignment',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('start_at', models.DateTimeField(blank=True, null=True)),
                ('end_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'active'), ('removed', 'removed')], default='active', max_length=20)),
                ('target_student_ids', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('class_obj', models.ForeignKey(db_column='class_id', on_delete=django.db.models.deletion.CASCADE, related_name='mission_assignments', to='institutions.class')),
                ('mission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_assignments', to='missions.learningmission')),
            ],
            options={'db_table': 'mission_class_assignment'},
        ),
        migrations.AddConstraint(
            model_name='missionclassassignment',
            constraint=models.UniqueConstraint(fields=('mission', 'class_obj'), name='uq_mission_class_assignment'),
        ),
        migrations.AddIndex(
            model_name='missionclassassignment',
            index=models.Index(fields=['class_obj', 'status'], name='idx_mca_class_status'),
        ),
        migrations.RunPython(backfill_legacy_class_assignments, migrations.RunPython.noop),
    ]
