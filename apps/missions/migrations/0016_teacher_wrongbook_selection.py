from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0015_normalize_matrix_question_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='wrongbookgenerationbatch',
            name='candidate_limit',
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationbatch',
            name='final_mission_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationbatch',
            name='generation_mode',
            field=models.CharField(default='legacy', max_length=30),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationbatch',
            name='selection_limit',
            field=models.PositiveSmallIntegerField(default=3),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationbatch',
            name='teacher_selection_confirmation_key',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationitem',
            name='selected_question_ids',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='wrongbookgenerationitem',
            name='selection_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='wrongbookgenerationbatch',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'queued'), ('generating', 'generating'),
                    ('snapshotting', 'snapshotting'), ('publishing', 'publishing'),
                    ('awaiting_selection', 'awaiting_selection'), ('published', 'published'),
                    ('partially_failed', 'partially_failed'), ('failed', 'failed'),
                    ('retrying', 'retrying'),
                ], max_length=30, default='queued',
            ),
        ),
    ]
