from django.db import migrations


class Migration(migrations.Migration):
    """Join the remote controlled taxonomy and local question-match branches."""

    dependencies = [
        ('knowledge', '0002_controlled_probe_taxonomy'),
        ('knowledge', '0003_knowledge_point_id_bigint'),
    ]

    operations = []
