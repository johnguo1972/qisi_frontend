"""Compatibility tests for review/common callers of the shared AI facade."""

from io import StringIO
import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from apps.common import ai_service as common_ai_service
from apps.common.ai.components import (
    KnowledgeAnalysisComponent,
    ModeAAnswerComponent,
    ModeBAnswerComponent,
    ModeCAnswerComponent,
    QuestionProbeComponent,
    ResultVerifierComponent,
    VisionExtractionComponent,
)
from apps.parser.models import ExamPaper, ExamQuestion


def _make_question(*, stem="1 + 1 = ?"):
    paper = ExamPaper.objects.create(title="Task 6 paper", subject="math")
    return ExamQuestion.objects.create(
        paper=paper,
        stem=stem,
        answer="2",
        question_type="calculation",
    )


def _component_responses():
    return {
        QuestionProbeComponent: {
            "subject": "math",
            "normalized_text": "1 + 1 = ?",
            "topic_tags_top3": ["整数加法"],
        },
        KnowledgeAnalysisComponent: {
            "subject": "math",
            "difficulty": "L2",
            "knowledge_points": [],
        },
        VisionExtractionComponent: {
            "figure_present": False,
            "entities": [],
        },
        ModeAAnswerComponent: {
            "mode": "A",
            "steps": [
                {"step": 1, "content": "识别加法"},
                {"step": 2, "content": "计算"},
                {"step": 3, "content": "检查"},
            ],
            "final_answer": "2",
            "summary": "完成",
        },
        ModeBAnswerComponent: {
            "mode": "B",
            "questions": [],
            "final_answer": "2",
            "summary": "引导完成",
        },
        ModeCAnswerComponent: {
            "mode": "C",
            "questions": [],
            "final_answer": "2",
            "summary": "开放引导完成",
        },
        ResultVerifierComponent: {
            "pass": True,
            "issues": [],
            "retry_needed": False,
        },
    }


def _real_facade_with_components():
    responses = _component_responses()

    def component_factory(component_type):
        component = MagicMock()
        component.run.return_value = responses[component_type]
        return component

    service = common_ai_service.AIReviewService(
        component_factory=component_factory
    )
    service._get_question_image_urls = MagicMock(return_value=[])
    return service


@pytest.mark.django_db
def test_shared_factory_builds_the_compatibility_facade():
    """Removing the shared facade factory must break every migrated caller."""
    service = common_ai_service.create_ai_review_service(
        component_factory=lambda component_type: MagicMock()
    )

    assert isinstance(service, common_ai_service.AIReviewService)


@pytest.mark.django_db(transaction=True)
def test_batch_task_uses_injected_facade_and_preserves_result_and_progress():
    """Batch callers must not construct a provider client outside the facade."""
    from apps.common import batch_tasks

    question = _make_question()
    facade = MagicMock()
    facade.process_question_full.return_value = {
        "knowledge": {"knowledge_points": []},
        "answer_a": {"mode": "A"},
        "answer_b": {"mode": "B"},
        "answer_c": {"mode": "C"},
        "errors": {},
    }
    writes = []

    with (
        patch.object(
            batch_tasks,
            "create_ai_review_service",
            return_value=facade,
        ) as service_factory,
        patch.object(batch_tasks.cache, "get", return_value=None),
        patch.object(
            batch_tasks.cache,
            "set",
            side_effect=lambda key, value, timeout: writes.append(
                (key, json.loads(value), timeout)
            ),
        ),
    ):
        result = batch_tasks.batch_ai_process_questions.run([str(question.id)])

    assert result == {
        "status": "completed",
        "success_count": 1,
        "error_count": 0,
        "errors": {},
    }
    service_factory.assert_called_once_with()
    facade.process_question_full.assert_called_once_with(
        str(question.id), model=None
    )
    facade.save_results_to_question.assert_called_once_with(
        str(question.id), facade.process_question_full.return_value
    )
    assert writes[0][1] == {
        "current": 0,
        "total": 1,
        "status": "running",
        "current_question": None,
        "success_count": 0,
        "error_count": 0,
        "errors": {},
    }
    assert writes[-1][1] == {
        "current": 1,
        "total": 1,
        "status": "completed",
        "current_question": None,
        "success_count": 1,
        "error_count": 0,
        "errors": {},
    }
    assert all(timeout == 3600 for _, _, timeout in writes)


@pytest.mark.django_db
def test_signal_generation_task_uses_injected_facade_and_keeps_result_shape():
    """The signal-triggered task must use the same injectable facade seam."""
    from apps.common import batch_tasks

    question = _make_question()
    facade = MagicMock()
    facade.process_question_full.return_value = {"errors": {}}

    with (
        patch.object(
            batch_tasks,
            "create_ai_review_service",
            return_value=facade,
        ) as service_factory,
        patch.object(
            batch_tasks,
            "AIReviewService",
            side_effect=AssertionError("legacy constructor used"),
        ),
    ):
        result = batch_tasks.single_generate_ai_answers.run(str(question.id))

    assert result == {"status": "success", "question_id": str(question.id)}
    service_factory.assert_called_once_with()
    facade.process_question_full.assert_called_once_with(
        str(question.id), model=None
    )
    facade.save_results_to_question.assert_called_once_with(
        str(question.id), facade.process_question_full.return_value
    )


@pytest.mark.django_db
def test_review_full_task_uses_facade_and_preserves_database_mapping():
    """The review task must keep its v2 state and A/B/C persistence contract."""
    from apps.review import tasks

    question = _make_question()
    service = _real_facade_with_components()
    writes = []

    with (
        patch.object(
            tasks, "create_ai_review_service", return_value=service
        ) as service_factory,
        patch.object(
            tasks.cache,
            "set",
            side_effect=lambda key, value, timeout: writes.append(
                (key, json.loads(value), timeout)
            ),
        ),
    ):
        result = tasks.single_ai_process_question.run(str(question.id))

    assert result == {
        "status": "complete",
        "question_id": str(question.id),
    }
    service_factory.assert_called_once_with()
    question.refresh_from_db()
    assert question.ai_answer_a["mode"] == "A"
    assert question.ai_answer_b["mode"] == "B"
    assert question.ai_answer_c["mode"] == "C"
    assert question.ai_processing_status == "success"
    assert question.ai_processed_at is not None
    assert writes[-1][1]["status"] == "complete"
    assert writes[-1][1]["result"] == {"errors": {}, "image_count": 0}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "field"),
    [
        ("A", "ai_answer_a"),
        ("B", "ai_answer_b"),
        ("C", "ai_answer_c"),
    ],
)
def test_review_single_mode_uses_facade_and_preserves_answer_metadata(
    mode, field
):
    """Single-mode migration must retain its field, timestamp and result shape."""
    from apps.review import tasks

    question = _make_question()
    service = _real_facade_with_components()

    with (
        patch.object(
            tasks, "create_ai_review_service", return_value=service
        ) as service_factory,
        patch.object(tasks.cache, "set"),
    ):
        result = tasks.single_mode_ai_process_question.run(
            str(question.id), mode
        )

    assert result == {
        "status": "complete",
        "question_id": str(question.id),
        "mode": mode,
    }
    service_factory.assert_called_once_with()
    question.refresh_from_db()
    saved_answer = getattr(question, field)
    assert saved_answer["mode"] == mode
    assert saved_answer["confirmed"] is False
    assert saved_answer["edited_content"] is None
    assert saved_answer["error"] is None
    assert saved_answer["generated_at"]
    assert question.ai_processing_status == "success"
    assert question.ai_processed_at is not None


@pytest.mark.django_db
def test_review_service_uses_shared_factory_and_keeps_summary_shape():
    """The review service wrapper must remain a thin facade/persistence map."""
    from apps.review.services import ai_review_service

    question = _make_question()
    facade = MagicMock()
    facade.process_question_full.return_value = {"errors": {}}

    def save_results(question_id, results):
        saved = ExamQuestion.objects.get(id=question_id)
        saved.ai_knowledge_enrichment = {
            "knowledge_points": [{"module": "整数加法"}]
        }
        saved.ai_answer_a = {"mode": "A"}
        saved.ai_answer_b = {"mode": "B"}
        saved.ai_answer_c = {"mode": "C"}
        saved.save()

    facade.save_results_to_question.side_effect = save_results

    with patch.object(
        ai_review_service,
        "create_ai_review_service",
        return_value=facade,
    ) as service_factory:
        result = ai_review_service.process_single_question(question.id)

    assert result == {
        "question_id": question.id,
        "knowledge_points_count": 1,
        "answer_a_generated": True,
        "answer_b_generated": True,
        "answer_c_generated": True,
        "errors": {},
    }
    service_factory.assert_called_once_with()
    facade.process_question_full.assert_called_once_with(question.id, model=None)
    facade.save_results_to_question.assert_called_once_with(
        question.id, facade.process_question_full.return_value
    )


@pytest.mark.django_db
def test_guidance_command_uses_facade_and_preserves_all_selection_and_output():
    """The command must keep --all selection and only persist valid answer B."""
    from apps.common.management.commands import generate_ai_guidance

    missing = _make_question(stem="missing B")
    existing = _make_question(stem="existing B")
    existing.ai_answer_b = {"mode": "B", "final_answer": "old"}
    existing.save(update_fields=["ai_answer_b"])

    facade = MagicMock()
    facade.process_question_full.return_value = {
        "answer_b": {"mode": "B", "final_answer": "new", "error": None}
    }
    stdout = StringIO()

    with patch.object(
        generate_ai_guidance,
        "create_ai_review_service",
        return_value=facade,
    ) as service_factory:
        call_command(
            "generate_ai_guidance",
            "1",
            "--all",
            stdout=stdout,
        )

    service_factory.assert_called_once_with()
    facade.process_question_full.assert_called_once_with(missing.id)
    missing.refresh_from_db()
    existing.refresh_from_db()
    assert missing.ai_answer_b["final_answer"] == "new"
    assert existing.ai_answer_b["final_answer"] == "old"
    assert "Found 1 questions with missing ai_answer_b" in stdout.getvalue()
    assert f"Question {missing.id} updated" in stdout.getvalue()


@pytest.mark.django_db
def test_deepseek_route_and_all_ai_timeouts_remain_fixed():
    """Review migration must not alter provider routing or timeout policy."""
    config = common_ai_service.load_ai_config()

    assert config.get_task_config("variant_verify_deepseek").provider == "deepseek"
    assert all(
        config.get_task_config(task_key).timeout_seconds == 300
        for task_key in config.task_keys
    )
