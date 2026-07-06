"""Integration tests for question-edit page enhancements.

Tests verify knowledge point association and image crop functionality
work together with the question-edit page (commit 5d8e958).
"""
import pytest
from apps.parser.models import ExamQuestion, ExamPage, QuestionImage


@pytest.mark.django_db
class TestQuestionEditIntegration:
    """Test question-edit page enhancements."""

    def test_update_question_with_knowledge_points(self, teacher_client, sample_question):
        """Update question with knowledge point associations via API."""
        kp_data = [
            {"id": 1, "label": "一元二次方程求解"},
            {"id": 2, "label": "判别式"},
        ]
        resp = teacher_client.patch(
            f'/api/v1/review/questions/{sample_question.id}/update/',
            {
                'stem': '更新后的题干内容',
                'knowledge_points': kp_data,
                'difficulty': 4.50,
            },
            format='json',
        )
        assert resp.status_code == 200, f"Unexpected response: {resp.json()}"
        body = resp.json()
        assert body['success'] is True

        # Verify persistence
        sample_question.refresh_from_db()
        assert sample_question.stem == '更新后的题干内容'
        assert sample_question.knowledge_points == kp_data
        assert sample_question.difficulty == 4.50

    def test_crop_image_returns_success(self, teacher_client, sample_question, tmp_path):
        """Crop image API returns success with valid bbox."""
        # Ensure the question has an associated page with an image
        paper = sample_question.paper
        # Create a fake page image for cropping
        from django.conf import settings
        from PIL import Image as PILImage

        exam_dir = settings.MEDIA_ROOT / 'exams' / str(paper.id)
        exam_dir.mkdir(parents=True, exist_ok=True)
        crops_dir = exam_dir / 'crops'
        crops_dir.mkdir(parents=True, exist_ok=True)

        page_image_path = exam_dir / 'page_1.png'
        img = PILImage.new('RGB', (800, 1200), color='white')
        img.save(str(page_image_path))

        # Create the ExamPage record
        rel_path = f'exams/{paper.id}/page_1.png'
        ExamPage.objects.create(
            paper=paper,
            page_no=1,
            image_path=rel_path,
        )
        # Link question to the page
        sample_question.page_start = 1
        sample_question.save()

        # Call crop endpoint with valid bbox
        resp = teacher_client.post(
            f'/api/v1/review/questions/{sample_question.id}/images/crop/',
            {
                'x1': 50,
                'y1': 50,
                'x2': 400,
                'y2': 300,
                'page_no': 1,
                'description': '测试裁剪插图',
            },
            format='json',
        )
        assert resp.status_code == 200, f"Unexpected response: {resp.json()}"
        body = resp.json()
        assert body['code'] == 0
        assert 'data' in body
        assert 'id' in body['data']

        # Verify the QuestionImage was created
        assert QuestionImage.objects.filter(question=sample_question).count() == 1
        qi = QuestionImage.objects.get(question=sample_question)
        assert qi.bbox == [50, 50, 400, 300]
        assert qi.description == '测试裁剪插图'
