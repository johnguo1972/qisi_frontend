from django.db import migrations


class Migration(migrations.Migration):
    """Join the remote question-relation and local idempotency branches."""

    dependencies = [
        ('study', '0005_questionrelation'),
        ('study', '0005_answerattempt_idempotency_key'),
    ]

    operations = []
