from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('study', '0005_questionrelation')]

    operations = [migrations.AddField(
        model_name='answerattempt', name='idempotency_key',
        field=models.CharField(blank=True, default='', db_index=True, max_length=100),
    )]
