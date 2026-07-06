"""Add AI answer and knowledge enrichment fields to ExamQuestion."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser', '0004_backfill_question_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='examquestion',
            name='ai_answer_a',
            field=models.JSONField(null=True, blank=True, verbose_name='A模式AI答案'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_answer_b',
            field=models.JSONField(null=True, blank=True, verbose_name='B模式AI答案'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_answer_c',
            field=models.JSONField(null=True, blank=True, verbose_name='C模式AI答案'),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='ai_knowledge_enrichment',
            field=models.JSONField(null=True, blank=True, verbose_name='AI知识点归属'),
        ),
    ]
