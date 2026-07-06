from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0006_alter_examquestion_ai_answer_a_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='examquestion',
            name='ai_probe_result',
            field=models.JSONField(null=True, blank=True, verbose_name='AI探查结果'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_vision_extract',
            field=models.JSONField(null=True, blank=True, verbose_name='AI读图结果'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_verifier_result',
            field=models.JSONField(null=True, blank=True, verbose_name='AI校验结果'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_processed_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='AI处理时间'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_processing_status',
            field=models.CharField(
                max_length=20, default='pending',
                choices=[
                    ('pending', '待处理'),
                    ('running', '处理中'),
                    ('success', '处理成功'),
                    ('failed', '处理失败'),
                ],
                verbose_name='AI处理状态',
            ),
        ),
    ]
