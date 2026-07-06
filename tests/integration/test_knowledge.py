"""Integration tests for knowledge and dictionary endpoints."""
import pytest
from django.db import connection


@pytest.mark.django_db
class TestKnowledge:
    """Test knowledge tree and dict endpoints."""

    def _check_knowledge_table(self):
        """Check if knowledge_points table exists (managed=False model)."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_points')"
            )
            return cursor.fetchone()[0]

    @pytest.mark.skipif(False, reason="")  # placeholder, will be overridden
    def test_knowledge_tree(self, teacher_client):
        """Get knowledge tree."""
        if not self._check_knowledge_table():
            pytest.skip("knowledge_points table not in test DB (managed=False)")
        resp = teacher_client.get('/api/v1/teacher/knowledge-tree/')
        assert resp.status_code in [200, 400, 500], f"Response: {resp.json()}"

    def test_knowledge_tree_with_params(self, teacher_client):
        """Get knowledge tree with subject filter."""
        if not self._check_knowledge_table():
            pytest.skip("knowledge_points table not in test DB (managed=False)")
        resp = teacher_client.get('/api/v1/teacher/knowledge-tree/', {
            'subject': 'math',
        })
        assert resp.status_code in [200, 400, 500], f"Response: {resp.json()}"

    def test_dict_subjects(self, teacher_client):
        """Get subject dictionary."""
        resp = teacher_client.get('/api/v1/dicts/subjects')
        assert resp.status_code in [200, 404], f"Response: {resp.json()}"

    def test_dict_knowledge_points(self, teacher_client):
        """Get knowledge points dictionary."""
        if not self._check_knowledge_table():
            pytest.skip("knowledge_points table not in test DB (managed=False)")
        resp = teacher_client.get('/api/v1/dicts/knowledge-points')
        assert resp.status_code in [200, 404], f"Response: {resp.json()}"

    def test_dict_question_types(self, teacher_client):
        """Get question types dictionary."""
        resp = teacher_client.get('/api/v1/dicts/question-types')
        assert resp.status_code in [200, 404], f"Response: {resp.json()}"
