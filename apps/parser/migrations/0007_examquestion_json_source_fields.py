from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0006_questionimage_original_file_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='examquestion',
            name='source_external_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, verbose_name='来源题目标识'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='source_question_type',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='来源题型'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='material',
            field=models.TextField(blank=True, null=True, verbose_name='材料'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='subquestions',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='子问题'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='tables',
            field=models.JSONField(blank=True, default=list, null=True, verbose_name='表格'),
        ),
    ]
