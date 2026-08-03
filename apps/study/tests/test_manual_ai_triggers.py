from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion
from apps.study import photo_views


def _plain_view_handler(decorated_view):
    return decorated_view.cls.post.__closure__[0].cell_contents


def _create_paper():
    return ExamPaper.objects.create(
        title="Manual AI trigger test paper",
        subject="M",
        source_file_path="tests/manual-ai-trigger.png",
    )


@pytest.mark.django_db
def test_auto_parsed_question_creation_does_not_dispatch_ai_task():
    paper = _create_paper()

    with patch(
        "apps.common.batch_tasks.single_generate_ai_answers.delay"
    ) as delay:
        ExamQuestion.objects.create(
            paper=paper,
            question_no="1",
            question_type="short_answer",
            stem="What is 1 + 1?",
            parse_status="auto_parsed",
        )

    delay.assert_not_called()


@pytest.mark.django_db
def test_successful_photo_create_keeps_ai_processing_manual(tmp_path, monkeypatch):
    paper = _create_paper()
    crop_dir = tmp_path / "crops"
    crop_dir.mkdir()
    crop_file = crop_dir / "question.png"
    crop_file.write_bytes(b"test image")
    monkeypatch.setattr(photo_views.settings, "MEDIA_ROOT", tmp_path)

    class VisionParser:
        def recognize_photo(self, image_sources):
            assert image_sources == [str(crop_file)]
            return {
                "question_no": "2",
                "question_type": "short_answer",
                "stem": "Photo-recognized question",
            }

        def close(self):
            pass

    request = SimpleNamespace(
        FILES=SimpleNamespace(getlist=lambda _name: []),
        POST={
            "paper_id": str(paper.id),
            "crop_file_path": "crops/question.png",
            "page_no": "1",
        },
        user=SimpleNamespace(id=1),
    )

    with (
        patch(
            "apps.common.batch_tasks.single_generate_ai_answers.delay"
        ) as delay,
        patch.object(
            photo_views,
            "upload_crop_image_safe",
            return_value=None,
        ),
        patch.object(
            photo_views,
            "vision_parser_component_factory",
            return_value=VisionParser(),
        ),
    ):
        response = _plain_view_handler(photo_views.photo_create_question)(request)

    assert response.status_code == 200
    assert response.data["message"] == "璇嗗埆鎴愬姛锛屽彲鎵嬪伐杩涜 AI 澶勭悊"
    assert response.data["data"]["ai_generation_status"] == "not_started"
    delay.assert_not_called()
