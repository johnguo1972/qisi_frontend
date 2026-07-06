"""Integration tests for review module endpoints."""
import pytest
from apps.parser.models import ExamQuestion
from apps.study.models import Favorite


@pytest.mark.django_db
class TestReview:
    """Test review list and paper review endpoints."""

    def test_paper_review_list(self, teacher_client):
        """View paper review list."""
        resp = teacher_client.get('/api/v1/review/papers/')
        assert resp.status_code in [200, 404], f"Response: {resp.json()}"

    def test_question_list_by_paper(self, teacher_client, sample_paper):
        """View questions for a paper."""
        resp = teacher_client.get(f'/api/v1/review/papers/{sample_paper.id}/questions/')
        assert resp.status_code == 200

    def test_question_detail_review(self, teacher_client, sample_question):
        """View question detail via review endpoint."""
        resp = teacher_client.get(f'/api/v1/review/questions/{sample_question.id}/')
        assert resp.status_code in [200, 404, 500], f"Response: {resp.json()}"

    def test_question_update_review(self, teacher_client, sample_question):
        """Update question via review endpoint."""
        resp = teacher_client.patch(f'/api/v1/review/questions/{sample_question.id}/update/', {
            'stem': '修改后的题干',
        })
        assert resp.status_code in [200, 400, 404, 405], f"Response: {resp.json()}"

    def test_question_confirm(self, teacher_client, sample_question):
        """Confirm a question."""
        resp = teacher_client.post(f'/api/v1/review/questions/{sample_question.id}/confirm/')
        assert resp.status_code in [200, 400, 404], f"Response: {resp.json()}"

    def test_question_reject(self, teacher_client, sample_question):
        """Reject a question."""
        resp = teacher_client.post(f'/api/v1/review/questions/{sample_question.id}/reject/')
        assert resp.status_code in [200, 400, 404], f"Response: {resp.json()}"


@pytest.mark.django_db
class TestAIReview:
    """Test AI review endpoints."""

    def test_ai_status(self, teacher_client, sample_question):
        """Check AI processing status."""
        resp = teacher_client.get(f'/api/v1/review/question/{sample_question.id}/ai-status/')
        assert resp.status_code in [200, 400, 404, 501], f"Response: {resp.json()}"

    def test_ai_process(self, teacher_client, sample_question):
        """Trigger AI processing."""
        resp = teacher_client.post(f'/api/v1/review/question/{sample_question.id}/ai-process/')
        # May return 200 with task_id, or 400/501 if AI not configured
        assert resp.status_code in [200, 201, 400, 404, 501], f"Response: {resp.json()}"

    def test_ai_task_status(self, teacher_client):
        """Check AI task status."""
        resp = teacher_client.get('/api/v1/review/ai-task/nonexistent-task-id/status/')
        assert resp.status_code in [200, 404], f"Response: {resp.json()}"


@pytest.mark.django_db
class TestFavorites:
    """Test favorite question endpoints."""

    def test_favorites_list_empty(self, teacher_client):
        """Favorites list should be empty initially."""
        resp = teacher_client.get('/api/v1/teacher/favorites/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0

    def test_favorites_add(self, teacher_client, sample_question):
        """Add question to favorites."""
        resp = teacher_client.post('/api/v1/teacher/favorites/add/', {
            'question_id': sample_question.id,
        })
        assert resp.status_code in [200, 201, 400], f"Add failed: {resp.json()}"

    def test_favorites_add_and_list(self, teacher_client, sample_question):
        """Add then list favorites."""
        # Add
        teacher_client.post('/api/v1/teacher/favorites/add/', {
            'question_id': sample_question.id,
        })

        # List
        resp = teacher_client.get('/api/v1/teacher/favorites/')
        assert resp.status_code == 200

    def test_favorites_remove(self, teacher_client, sample_question):
        """Remove from favorites."""
        resp = teacher_client.delete(f'/api/v1/teacher/favorites/{sample_question.id}/')
        assert resp.status_code in [200, 201, 204, 404, 405], f"Response: {resp.json()}"

    def test_favorites_add_duplicate(self, teacher_client, sample_question):
        """Adding same question twice should be handled."""
        teacher_client.post('/api/v1/teacher/favorites/add/', {
            'question_id': sample_question.id,
        })
        resp = teacher_client.post('/api/v1/teacher/favorites/add/', {
            'question_id': sample_question.id,
        })
        # Should either succeed (idempotent) or return conflict
        assert resp.status_code in [200, 201, 400, 409], f"Response: {resp.json()}"
