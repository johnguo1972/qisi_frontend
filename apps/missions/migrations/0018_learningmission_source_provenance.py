from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0017_relatedquestionrecommendation_candidate_providers'),
    ]

    operations = [
        migrations.AddField(
            model_name='learningmission',
            name='source_context',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='learningmission',
            name='source_node_ids',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
