from django.db import migrations


def use_bigint_for_external_knowledge_table(apps, schema_editor):
    """Align the new FK column with the provisioned knowledge_points BIGINT id.

    The historical unmanaged model migration described that external table's
    key as UUID, while the real table (and current model) use BIGINT.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'ALTER TABLE question_knowledge_match '
        'ALTER COLUMN knowledge_point_id TYPE bigint '
        'USING NULLIF(knowledge_point_id::text, \'\')::bigint'
    )


def restore_uuid_column(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'ALTER TABLE question_knowledge_match '
        'ALTER COLUMN knowledge_point_id TYPE uuid '
        'USING NULLIF(knowledge_point_id::text, \'\')::uuid'
    )


class Migration(migrations.Migration):
    dependencies = [('knowledge', '0003_questionknowledgematch')]
    operations = [migrations.RunPython(use_bigint_for_external_knowledge_table, restore_uuid_column)]
