"""Test setup for the externally managed knowledge_points table."""
import pytest

from apps.knowledge.models import KnowledgePoint


@pytest.fixture(autouse=True)
def ensure_knowledge_points_table(db):
    """Provision the unmanaged table in the isolated pytest database only."""
    from django.db import connection

    table_name = KnowledgePoint._meta.db_table
    created = table_name not in connection.introspection.table_names()
    if created:
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(KnowledgePoint)
    yield
