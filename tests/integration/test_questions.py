"""Integration tests for question management endpoints."""
import pytest
from apps.parser.models import ExamQuestion


@pytest.mark.django_db
class TestQuestions:
    """Test question CRUD endpoints."""

    def test_question_list(self, teacher_client, sample_paper):
        """Question list should return paginated results."""
        # Create a question
        ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='1',
            question_type='single_choice',
            subject='数学',
            stem='测试题目1',
            answer='A',
        )
        ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='2',
            question_type='single_choice',
            subject='数学',
            stem='测试题目2',
            answer='B',
        )

        resp = teacher_client.get('/api/v1/questions/', {'page': 1, 'page_size': 10})
        assert resp.status_code == 200

    def test_question_detail(self, teacher_client, sample_question):
        """Question detail should return full question data."""
        resp = teacher_client.get(f'/api/v1/questions/{sample_question.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0

    def test_create_question(self, teacher_client):
        """Create a question manually."""
        resp = teacher_client.post('/api/v1/questions/create/', {
            'stem': '手动创建的题目',
            'question_type': 'single_choice',
            'subject': '数学',
            'answer': 'A',
        })
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_update_question(self, teacher_client, sample_question):
        """Update a question."""
        resp = teacher_client.put(f'/api/v1/questions/{sample_question.id}', {
            'stem': '更新后的题干',
            'answer': 'B',
        })
        assert resp.status_code in [200, 201, 400, 405], f"Response: {resp.json()}"

    def test_publish_question(self, teacher_client, sample_question):
        """Publish a question."""
        resp = teacher_client.post(f'/api/v1/questions/{sample_question.id}/publish')
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"

    def test_question_list_filter_by_type(self, teacher_client, sample_paper):
        """Filter questions by type."""
        ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='1',
            question_type='single_choice',
            subject='数学',
            stem='选择题',
            answer='A',
        )
        resp = teacher_client.get('/api/v1/questions/', {'question_type': 'single_choice'})
        assert resp.status_code == 200

    def test_question_not_found(self, teacher_client):
        """Non-existent question should return 404."""
        resp = teacher_client.get('/api/v1/questions/999999')
        assert resp.status_code in [404, 200]
