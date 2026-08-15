"""Compatibility tests for review/common callers of the shared AI facade."""

from io import StringIO
from copy import deepcopy
import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.management.base import CommandError
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.common import ai_service as common_ai_service
from apps.common.ai.components import (
    DeepSeekFinalReviewComponent,
    DeepSeekIndependentVerifierComponent,
    KnowledgeAnalysisComponent,
    ModeAAnswerComponent,
    ModeBAnswerComponent,
    ModeCAnswerComponent,
    QuestionProbeComponent,
    ResultVerifierComponent,
    VisionExtractionComponent,
)
from apps.common.ai.answer_arbitration import (
    ArbitrationError,
    ArbitrationOutcome,
    ArbitrationProviderError,
)
from apps.common.ai.question_context import QuestionContextBuilder, question_context_hash
from apps.parser.models import ExamPaper, ExamQuestion, QuestionOption
from apps.knowledge.models import KnowledgePoint


def _make_question(*, stem="1 + 1 = ?"):
    paper = ExamPaper.objects.create(title="Task 6 paper", subject="math")
    return ExamQuestion.objects.create(
        paper=paper,
        stem=stem,
        answer="2",
        question_type="calculation",
    )


def _teacher_api_client() -> APIClient:
    user = UserAccount.objects.create(
        mobile=f"138{UserAccount.objects.count():08d}",
        display_name="AI compatibility teacher",
        role_type="teacher",
    )
    grant_user_role(user, "teacher")
    access = generate_tokens(user, "teacher")["access_token"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


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
            "questions": [
                {
                    "question": f"Guided step {index}",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
                    "correct_option": "B",
                    "correct_answer": "B",
                    "reference_answer": "2",
                    "analysis": "Two is correct",
                    "explanation": "Two is correct",
                }
                for index in range(1, 4)
            ],
            "final_answer": "2",
            "summary": "引导完成",
        },
        ModeCAnswerComponent: {
            "mode": "C",
            "questions": [
                {
                    "question": f"Open prompt {index}",
                    "reference_answer": "2",
                    "key_points": ["addition"],
                    "followup_hint": "Combine the values",
                }
                for index in range(1, 4)
            ],
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
    mode_components = {
        "A": ModeAAnswerComponent,
        "B": ModeBAnswerComponent,
        "C": ModeCAnswerComponent,
    }

    def component_factory(component_type):
        component = MagicMock()
        if component_type is DeepSeekIndependentVerifierComponent:
            component.run.side_effect = lambda question: {
                "independent_answer": "2",
                "independent_reasoning_summary": "The addition gives 2.",
                "reference_answer_valid": True,
                "reference_analysis_valid": None,
                "reference_issues": [],
                "key_facts": ["1 + 1 equals 2."],
                "confidence": 0.95,
                "mode_content": deepcopy(
                    responses[mode_components[question.metadata["target_mode"]]]
                ),
            }
        elif component_type is DeepSeekFinalReviewComponent:
            component.run.side_effect = lambda question: {
                "trusted_answer": "2",
                "qwen_content_valid": True,
                "candidate_issues": [],
                "confidence": 0.95,
                "mode_content": deepcopy(
                    responses[mode_components[question.metadata["target_mode"]]]
                ),
            }
        else:
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


def test_legacy_component_client_exposes_single_attempt_provider_path():
    service = MagicMock()
    service._call_ai.return_value = '{"subject":"math"}'
    service._task_route.return_value = ("qwen", "configured-model")
    client = common_ai_service._LegacyComponentClient(service)

    result = client.complete_once(
        "question_probe", system="system", user="user"
    )

    assert result.content == '{"subject":"math"}'
    service._call_ai.assert_called_once_with(
        "system",
        "user",
        task_key="question_probe",
        single_attempt=True,
    )


@pytest.mark.django_db
def test_probe_pipeline_runs_only_probe_and_knowledge_then_persists_attributes():
    """Probe-only processing must not generate vision or any answer mode."""
    question = _make_question()
    knowledge_point = KnowledgePoint.objects.create(
        subject="math",
        stage="junior",
        grade_index=7,
        grade_name="Grade 7",
        term="up",
        chapter="Numbers",
        module="integer addition",
        node_type="method",
        content="integer addition",
    )
    responses = _component_responses()
    responses[KnowledgeAnalysisComponent] = {
        "subject": "math",
        "difficulty": "L2",
        "knowledge_points": [{"subject": "math", "module": "integer addition"}],
    }
    components = {}

    def component_factory(component_type):
        component = MagicMock()
        component.run.return_value = responses[component_type]
        components[component_type] = component
        return component

    service = common_ai_service.AIReviewService(component_factory=component_factory)
    service._get_question_image_urls = MagicMock(return_value=[])

    results = service.process_question_probe(str(question.id))

    assert set(results) == {"probe", "knowledge", "errors"}
    components[QuestionProbeComponent].run.assert_called_once()
    components[KnowledgeAnalysisComponent].run.assert_called_once()
    for component_type in (
        VisionExtractionComponent,
        ModeAAnswerComponent,
        ModeBAnswerComponent,
        ModeCAnswerComponent,
        ResultVerifierComponent,
    ):
        assert component_type not in components

    service.save_results_to_question(str(question.id), results)
    question.refresh_from_db()
    assert question.ai_probe_result == results["probe"]
    assert question.ai_knowledge_enrichment["difficulty"] == "L2"
    assert question.knowledge_points == [
        {"id": str(knowledge_point.id), "module": "integer addition"}
    ]
    assert question.difficulty == 2
    assert question.ai_answer_a is None
    assert question.ai_answer_b is None
    assert question.ai_answer_c is None


@pytest.mark.parametrize(
    ("errors", "status"),
    [({}, "complete"), ({"knowledge": "unavailable"}, "partial")],
)
def test_probe_task_persists_probe_results_and_terminal_progress(errors, status):
    """Removing probe task persistence or partial reporting must break this test."""
    from apps.review import tasks

    question = MagicMock()
    facade = MagicMock()
    facade.process_question_probe.return_value = {
        "probe": {"subject": "math"},
        "knowledge": {"knowledge_points": []},
        "errors": errors,
    }
    writes = []

    with (
        patch.object(tasks.ExamQuestion.objects, "get", return_value=question),
        patch.object(tasks, "create_ai_review_service", return_value=facade),
        patch.object(
            tasks.cache,
            "set",
            side_effect=lambda key, value, timeout: writes.append(
                (key, json.loads(value), timeout)
            ),
        ),
    ):
        result = tasks.single_probe_ai_process_question.run("probe-question")

    assert result == {
        "status": status,
        "question_id": "probe-question",
        "mode": "probe",
    }
    facade.process_question_probe.assert_called_once_with(
        "probe-question", model=None
    )
    facade.save_results_to_question.assert_called_once_with(
        "probe-question", facade.process_question_probe.return_value
    )
    assert writes[-1] == (
        "single_ai_progress:None",
        {
            "status": status,
            "question_id": "probe-question",
            "step": "complete",
            "step_label": "处理完成",
            "result": {"errors": errors},
            "error": None,
        },
        3600,
    )
    facade.close.assert_called_once_with()


def test_probe_task_skips_missing_question_without_creating_facade():
    """A deleted probe target must not instantiate an AI client."""
    from apps.review import tasks

    writes = []
    with (
        patch.object(
            tasks.ExamQuestion.objects,
            "get",
            side_effect=tasks.ExamQuestion.DoesNotExist,
        ),
        patch.object(
            tasks,
            "create_ai_review_service",
            side_effect=AssertionError("missing question created a facade"),
        ) as service_factory,
        patch.object(
            tasks.cache,
            "set",
            side_effect=lambda key, value, timeout: writes.append(
                (key, json.loads(value), timeout)
            ),
        ),
    ):
        result = tasks.single_probe_ai_process_question.run("missing")

    assert result == {
        "status": "skipped",
        "question_id": "missing",
        "reason": "question_not_found",
    }
    service_factory.assert_not_called()
    assert writes[-1][1]["status"] == "skipped"


@pytest.mark.django_db
def test_probe_endpoint_dispatches_only_probe_task_with_validated_model():
    """Probe POST must dispatch the dedicated task and return its pending contract."""
    question = _make_question()
    client = _teacher_api_client()
    delayed_task = MagicMock(id="probe-task-id")

    with patch(
        "apps.review.tasks.single_probe_ai_process_question.delay",
        return_value=delayed_task,
    ) as delay:
        response = client.post(
            reverse("ai-process-probe", args=[question.id]),
            {"model": "qwen"},
            format="json",
        )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"task_id": "probe-task-id", "status": "pending", "mode": "probe"},
    }
    delay.assert_called_once_with(str(question.id), model="qwen")


@pytest.mark.django_db
def test_probe_endpoint_returns_not_found_without_dispatching():
    """A missing probe target must not enqueue any task."""
    client = _teacher_api_client()

    with patch(
        "apps.review.tasks.single_probe_ai_process_question.delay"
    ) as delay:
        response = client.post(
            reverse("ai-process-probe", args=[uuid.uuid4()]),
            {},
            format="json",
        )

    assert response.status_code == 404
    delay.assert_not_called()


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
    facade.close.assert_called_once_with()


@pytest.mark.django_db
def test_legacy_automatic_task_skips_without_creating_a_facade():
    """Legacy queued auto-generation messages must be harmless tombstones."""
    from apps.common import batch_tasks

    with (
        patch.object(
            batch_tasks,
            "create_ai_review_service",
            side_effect=AssertionError("automatic task created a facade"),
        ) as service_factory,
        patch.object(
            batch_tasks,
            "AIReviewService",
            side_effect=AssertionError("legacy constructor used"),
        ),
        patch(
            "apps.review.ai_mode_dispatch.dispatch_single_mode_ai_task",
            side_effect=AssertionError("automatic task dispatched a mode"),
        ) as mode_dispatch,
    ):
        result = batch_tasks.single_generate_ai_answers.run("legacy-question")

    assert result == {
        "status": "skipped",
        "question_id": "legacy-question",
        "reason": "automatic_generation_disabled",
    }
    service_factory.assert_not_called()
    mode_dispatch.assert_not_called()


@pytest.mark.parametrize(
    ("task_name", "args"),
    [
        ("single_ai_process_question", ("missing",)),
        ("single_mode_ai_process_question", ("missing", "A")),
        ("single_mode_ai_process_question", ("missing", "B")),
        ("single_mode_ai_process_question", ("missing", "C")),
    ],
)
def test_missing_question_manual_tasks_skip_before_creating_facade(
    task_name, args
):
    """Manual full and A/B/C jobs must terminate safely when their row is gone."""
    from apps.review import tasks

    writes = []
    with (
        patch.object(
            tasks,
            "create_ai_review_service",
            side_effect=AssertionError("missing question created a facade"),
        ) as service_factory,
        patch.object(
            tasks.ExamQuestion.objects,
            "get",
            side_effect=tasks.ExamQuestion.DoesNotExist,
        ),
        patch.object(
            tasks.cache,
            "set",
            side_effect=lambda key, value, timeout: writes.append(
                (key, json.loads(value), timeout)
            ),
        ),
    ):
        result = getattr(tasks, task_name).run(*args)

    assert result == {
        "status": "skipped",
        "question_id": "missing",
        "reason": "question_not_found",
    }
    service_factory.assert_not_called()
    assert writes[-1] == (
        "single_ai_progress:None",
        {
            "status": "skipped",
            "question_id": "missing",
            "step": "starting",
            "step_label": tasks.STEP_LABELS["starting"],
            "result": None,
            "error": "question_not_found",
        },
        3600,
    )


@pytest.mark.parametrize(
    ("mode", "field", "task_key", "model"),
    [
        ("A", "ai_answer_a", "mode_a_answer", None),
        ("B", "ai_answer_b", "mode_b_answer", None),
        ("C", "ai_answer_c", "mode_c_answer", None),
        ("A", "ai_answer_a", "mode_a_answer", "qwen3-vl-plus"),
    ],
)
def test_single_mode_task_persists_actual_route_metadata_even_when_compat_model_is_passed(
    mode, field, task_key, model
):
    """Each mode stores its configured route model without an override."""
    from apps.review import tasks

    question = SimpleNamespace(
        stem="1 + 1 = ?",
        ai_probe_result={},
        ai_vision_extract={},
        ai_verifier_result=None,
        save=MagicMock(),
    )
    service = MagicMock()
    expected_model = 'configured-route-model'
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', expected_model)
    service._get_model.return_value = model or 'compatibility-default'
    context = QuestionContextBuilder.build(
        question, normalized_text=question.stem, vision_result={}
    )
    service.solve_mode_with_arbitration.return_value = ArbitrationOutcome(
        answer={'mode': mode, 'final_answer': '2'},
        verification={
            'status': 'accepted',
            'context_hash': question_context_hash(context),
        },
        shared_verifier_result=None,
    )
    locked_queryset = MagicMock()
    locked_queryset.get.return_value = question

    with (
        patch.object(tasks.ExamQuestion.objects, "get", return_value=question),
        patch.object(
            tasks.ExamQuestion.objects,
            'select_for_update',
            return_value=locked_queryset,
        ),
        patch.object(tasks, "create_ai_review_service", return_value=service),
        patch.object(tasks.cache, "set"),
    ):
        result = tasks.single_mode_ai_process_question.run(
            "mode-model-question", mode, model=model
        )

    assert result == {
        "status": "complete",
        "question_id": "mode-model-question",
        "mode": mode,
    }
    assert getattr(question, field)["model"] == expected_model
    assert getattr(question, field)["provider"] == 'qwen'


@pytest.mark.parametrize(
    ("task_name", "args"),
    [
        ("single_ai_process_question", ("db-error",)),
        ("single_mode_ai_process_question", ("db-error", "A")),
    ],
)
def test_review_tasks_propagate_lookup_error_before_creating_facade(
    task_name, args
):
    from apps.review import tasks

    with (
        patch.object(
            tasks,
            "create_ai_review_service",
            side_effect=AssertionError("lookup error created a facade"),
        ) as service_factory,
        patch.object(
            tasks.ExamQuestion.objects,
            "get",
            side_effect=RuntimeError("database unavailable"),
        ),
        patch.object(tasks.cache, "set"),
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        getattr(tasks, task_name).run(*args)

    service_factory.assert_not_called()


def test_review_task_logs_metadata_without_ai_content_or_provider_errors(caplog):
    from apps.review import tasks

    sensitive = (
        "13812345678 token=PRIVATE_TOKEN "
        "data:image/png;base64,PRIVATE_DATA "
        "https://cdn.example.test/a.png?Signature=PRIVATE_SIGNATURE "
        "provider raw answer"
    )
    question = MagicMock(ai_processing_status="success")
    facade = MagicMock()
    facade.process_question_full_v2.return_value = {
        "answer_a": {"steps": [sensitive], "summary": sensitive},
        "vision": {"error": sensitive},
        "errors": {},
        "image_count": 1,
    }
    caplog.set_level(logging.DEBUG, logger="apps.review.tasks")

    with (
        patch.object(tasks, "create_ai_review_service", return_value=facade),
        patch.object(tasks.ExamQuestion.objects, "get", return_value=question),
        patch.object(tasks.cache, "set"),
    ):
        result = tasks.single_ai_process_question.run("safe-log")

    assert result["status"] == "complete"
    assert sensitive not in caplog.text
    for marker in (
        "13812345678",
        "PRIVATE_TOKEN",
        "PRIVATE_DATA",
        "PRIVATE_SIGNATURE",
        "provider raw answer",
    ):
        assert marker not in caplog.text
    facade.close.assert_called_once_with()


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


def test_single_mode_task_exposes_doubled_time_limits():
    from apps.review import tasks

    assert tasks.single_mode_ai_process_question.soft_time_limit == 3800
    assert tasks.single_mode_ai_process_question.time_limit == 3900


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('mode', 'field'),
    [('A', 'ai_answer_a'), ('B', 'ai_answer_b'), ('C', 'ai_answer_c')],
)
def test_single_mode_success_uses_arbitration_and_updates_only_requested_mode(
    mode, field
):
    from apps.review import tasks

    question = _make_question()
    question.ai_answer_a = {'mode': 'A', 'marker': 'old-a'}
    question.ai_answer_b = {'mode': 'B', 'marker': 'old-b'}
    question.ai_answer_c = {'mode': 'C', 'marker': 'old-c'}
    question.ai_verifier_result = {'context_hash': 'old'}
    question.save()
    old_answers = {
        name: deepcopy(getattr(question, name))
        for name in ('ai_answer_a', 'ai_answer_b', 'ai_answer_c')
    }
    original_context = QuestionContextBuilder.build(
        question,
        normalized_text=question.stem,
        vision_result={},
    )
    verification = {
        'status': 'accepted',
        'context_hash': question_context_hash(original_context),
        'trusted_answer': '2',
    }
    shared = {
        'context_hash': verification['context_hash'],
        'independent_answer': '2',
        'reference_answer_valid': True,
    }
    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', 'configured-model')
    service.solve_mode_with_arbitration.return_value = ArbitrationOutcome(
        answer={'mode': mode, 'final_answer': '2', 'verification': verification},
        verification=verification,
        shared_verifier_result=shared,
    )
    locked_queryset = MagicMock()
    locked_queryset.get.side_effect = ExamQuestion.objects.get

    with (
        patch.object(tasks, 'create_ai_review_service', return_value=service),
        patch.object(
            tasks.ExamQuestion.objects,
            'select_for_update',
            return_value=locked_queryset,
        ) as select_for_update,
        patch.object(tasks.cache, 'set'),
    ):
        result = tasks.single_mode_ai_process_question.run(
            str(question.id), mode
        )

    assert result == {
        'status': 'complete',
        'question_id': str(question.id),
        'mode': mode,
    }
    service.solve_mode_with_arbitration.assert_called_once()
    assert service.solve_mode_with_arbitration.call_args.kwargs['mode'] == mode
    select_for_update.assert_called_once_with()
    question.refresh_from_db()
    assert getattr(question, field)['final_answer'] == '2'
    for other_field, old_value in old_answers.items():
        if other_field != field:
            assert getattr(question, other_field) == old_value
    assert question.ai_verifier_result == shared
    assert question.ai_processing_status == 'success'
    assert question.ai_processed_at is not None
    service.close.assert_called_once_with()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'mutation', ['stem', 'option', 'reference_answer', 'reference_analysis']
)
def test_single_mode_locked_save_rejects_question_context_changes(mutation):
    from apps.review import tasks

    question = _make_question(stem='Which option is correct?')
    question.question_type = 'single_choice'
    question.answer = 'C'
    question.analysis = 'Original analysis'
    question.solution = 'Original solution'
    question.ai_answer_a = {'mode': 'A', 'marker': 'old-answer'}
    question.ai_verifier_result = {'context_hash': 'old-verifier'}
    question.ai_processing_status = 'success'
    question.ai_processed_at = tasks.timezone.now()
    question.save()
    for index, (label, content) in enumerate(
        [('A', 'one'), ('B', 'two'), ('C', 'three'), ('D', 'four')]
    ):
        QuestionOption.objects.create(
            question=question,
            option_label=label,
            content=content,
            sort_order=index,
        )
    original_context = QuestionContextBuilder.build(
        question,
        normalized_text=question.stem,
        vision_result={},
    )
    original_hash = question_context_hash(original_context)
    old_answer = deepcopy(question.ai_answer_a)
    old_verifier = deepcopy(question.ai_verifier_result)
    old_status = question.ai_processing_status
    old_timestamp = question.ai_processed_at

    def mutate_then_return(*_args, **_kwargs):
        if mutation == 'stem':
            ExamQuestion.objects.filter(id=question.id).update(stem='Edited stem')
        elif mutation == 'option':
            QuestionOption.objects.filter(
                question=question, option_label='A'
            ).update(content='edited option')
        elif mutation == 'reference_answer':
            ExamQuestion.objects.filter(id=question.id).update(answer='D')
        else:
            ExamQuestion.objects.filter(id=question.id).update(
                analysis='Edited analysis'
            )
        return ArbitrationOutcome(
            answer={'mode': 'A', 'final_answer': 'C'},
            verification={'status': 'accepted', 'context_hash': original_hash},
            shared_verifier_result={
                'context_hash': original_hash,
                'independent_answer': 'C',
                'reference_answer_valid': True,
                'reference_analysis_valid': True,
                'reference_issues': [],
                'key_facts': ['Original fact'],
                'confidence': 0.95,
            },
        )

    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', 'configured-model')
    service.solve_mode_with_arbitration.side_effect = mutate_then_return

    with (
        patch.object(tasks, 'create_ai_review_service', return_value=service),
        patch.object(tasks.cache, 'set'),
    ):
        result = tasks.single_mode_ai_process_question.run(str(question.id), 'A')

    assert result['status'] == 'failed'
    question.refresh_from_db()
    assert question.ai_answer_a == old_answer
    assert question.ai_verifier_result == old_verifier
    assert question.ai_processing_status == old_status
    assert question.ai_processed_at == old_timestamp


@pytest.mark.django_db
@pytest.mark.parametrize(
    'error',
    [
        ArbitrationProviderError(),
        ArbitrationError('verification failed'),
        RuntimeError('unexpected provider wrapper failure'),
    ],
)
def test_single_mode_failure_preserves_old_mode_verifier_and_success_timestamp(
    error
):
    from apps.review import tasks

    question = _make_question()
    question.ai_answer_a = {'mode': 'A', 'marker': 'byte-stable'}
    question.ai_verifier_result = {'context_hash': 'old-verifier'}
    question.ai_processing_status = 'success'
    question.ai_processed_at = tasks.timezone.now()
    question.save()
    old_answer = deepcopy(question.ai_answer_a)
    old_verifier = deepcopy(question.ai_verifier_result)
    old_processed_at = question.ai_processed_at
    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service.solve_mode_with_arbitration.side_effect = error

    with (
        patch.object(tasks, 'create_ai_review_service', return_value=service),
        patch.object(tasks.cache, 'set'),
    ):
        result = tasks.single_mode_ai_process_question.run(
            str(question.id), 'A'
        )

    assert result['status'] == 'failed'
    question.refresh_from_db()
    assert question.ai_answer_a == old_answer
    assert question.ai_verifier_result == old_verifier
    assert question.ai_processing_status == 'success'
    assert question.ai_processed_at == old_processed_at
    service.close.assert_called_once_with()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('error', 'expected_status'),
    [
        (None, 'complete'),
        (ArbitrationProviderError(), 'failed'),
        ('soft_timeout', 'failed'),
        (RuntimeError('unexpected'), 'failed'),
    ],
    ids=['success', 'handled_failure', 'soft_timeout', 'unexpected_exception'],
)
def test_single_mode_task_releases_its_owned_lock_on_every_terminal_path(
    error, expected_status
):
    from celery.exceptions import SoftTimeLimitExceeded
    from apps.review import tasks

    question = _make_question()
    task_id = f'owner-{expected_status}-{type(error).__name__}'
    lock_key = f'ai-mode-lock:{question.id}:A'
    tasks.cache.set(
        lock_key,
        json.dumps({'task_id': task_id}, separators=(',', ':')),
        timeout=4200,
    )
    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', 'configured-model')
    context = QuestionContextBuilder.build(
        question, normalized_text=question.stem, vision_result={}
    )
    service.solve_mode_with_arbitration.return_value = ArbitrationOutcome(
        answer={'mode': 'A', 'final_answer': '2'},
        verification={
            'status': 'accepted',
            'context_hash': question_context_hash(context),
        },
        shared_verifier_result=None,
    )
    if error == 'soft_timeout':
        service.solve_mode_with_arbitration.side_effect = SoftTimeLimitExceeded()
    elif error is not None:
        service.solve_mode_with_arbitration.side_effect = error

    with patch.object(tasks, 'create_ai_review_service', return_value=service):
        result = tasks.single_mode_ai_process_question.apply(
            args=(str(question.id), 'A'), task_id=task_id
        ).get()

    assert result['status'] == expected_status
    assert tasks.cache.get(lock_key) is None
    service.close.assert_called_once_with()


@pytest.mark.django_db
def test_single_mode_task_never_releases_a_newer_lock_owner():
    from apps.review import tasks

    question = _make_question()
    lock_key = f'ai-mode-lock:{question.id}:A'
    newer_owner = json.dumps({'task_id': 'newer-owner'})
    tasks.cache.set(lock_key, newer_owner, timeout=4200)
    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service.solve_mode_with_arbitration.side_effect = RuntimeError('failed')

    with patch.object(tasks, 'create_ai_review_service', return_value=service):
        result = tasks.single_mode_ai_process_question.apply(
            args=(str(question.id), 'A'), task_id='older-owner'
        ).get()

    assert result['status'] == 'failed'
    assert tasks.cache.get(lock_key) == newer_owner
    tasks.cache.delete(lock_key)


@pytest.mark.django_db
def test_single_mode_task_releases_lock_even_when_service_close_fails():
    from apps.review import tasks

    question = _make_question()
    task_id = 'close-failure-owner'
    lock_key = f'ai-mode-lock:{question.id}:A'
    tasks.cache.set(
        lock_key,
        json.dumps({'task_id': task_id}, separators=(',', ':')),
        timeout=4200,
    )
    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', 'configured-model')
    service.solve_mode_with_arbitration.return_value = ArbitrationOutcome(
        answer={'mode': 'A', 'final_answer': '2'},
        verification={'status': 'accepted'},
        shared_verifier_result=None,
    )
    service.close.side_effect = RuntimeError('close failed')

    with (
        patch.object(tasks, 'create_ai_review_service', return_value=service),
        pytest.raises(RuntimeError, match='close failed'),
    ):
        tasks.single_mode_ai_process_question.apply(
            args=(str(question.id), 'A'), task_id=task_id
        ).get()

    assert tasks.cache.get(lock_key) is None


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
            str(existing.id),
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
def test_guidance_command_preserves_explicit_uuid_selection():
    """Explicit IDs must select the UUID-backed questions passed by callers."""
    from apps.common.management.commands import generate_ai_guidance

    selected = _make_question(stem="selected one")
    also_selected = _make_question(stem="selected two")
    untouched = _make_question(stem="untouched")
    facade = MagicMock()
    facade.process_question_full.return_value = {
        "answer_b": {"mode": "B", "final_answer": "selected", "error": None}
    }
    stdout = StringIO()

    with patch.object(
        generate_ai_guidance,
        "create_ai_review_service",
        return_value=facade,
    ):
        call_command(
            "generate_ai_guidance",
            str(selected.id),
            str(also_selected.id),
            stdout=stdout,
        )

    called_question_ids = {
        call.args[0]
        for call in facade.process_question_full.call_args_list
    }
    assert called_question_ids == {selected.id, also_selected.id}
    selected.refresh_from_db()
    also_selected.refresh_from_db()
    untouched.refresh_from_db()
    assert selected.ai_answer_b["final_answer"] == "selected"
    assert also_selected.ai_answer_b["final_answer"] == "selected"
    assert untouched.ai_answer_b is None
    assert f"Processing question {selected.id}" in stdout.getvalue()
    assert f"Processing question {also_selected.id}" in stdout.getvalue()


@pytest.mark.django_db
def test_guidance_command_keeps_empty_success_for_unmatched_valid_uuid():
    """A well-formed UUID with no row must remain a successful no-op."""
    from apps.common.management.commands import generate_ai_guidance

    facade = MagicMock()
    stdout = StringIO()
    missing_id = uuid.uuid4()

    with patch.object(
        generate_ai_guidance,
        "create_ai_review_service",
        return_value=facade,
    ) as service_factory:
        call_command(
            "generate_ai_guidance",
            str(missing_id),
            stdout=stdout,
        )

    service_factory.assert_called_once_with()
    facade.process_question_full.assert_not_called()
    facade.close.assert_called_once_with()
    assert stdout.getvalue() == ""


@pytest.mark.django_db
def test_guidance_command_rejects_invalid_id_during_argument_parsing():
    """Malformed IDs must still produce a management-command parse error."""
    with pytest.raises(CommandError, match="question_ids"):
        call_command("generate_ai_guidance", "not-a-valid-id")


@pytest.mark.django_db
def test_deepseek_route_and_all_ai_timeouts_remain_fixed():
    """Review migration must not alter provider routing or timeout policy."""
    config = common_ai_service.load_ai_config()

    assert config.get_task_config("variant_verify_deepseek").provider == "deepseek"
    assert all(
        config.get_task_config(task_key).timeout_seconds == 300
        for task_key in config.task_keys
    )


class _CapturingComponent:
    def __init__(self, component_type, calls, responses):
        self._component_type = component_type
        self._calls = calls
        self._responses = responses

    def run(self, question_input):
        self._calls.append((self._component_type, question_input))
        return self._responses[self._component_type]


class _CapturingFactory:
    def __init__(self, responses):
        self.calls = []
        self.responses = responses

    def __call__(self, component_type):
        return _CapturingComponent(component_type, self.calls, self.responses)


@pytest.mark.django_db
def test_arbitration_uses_complete_real_question_context_in_stable_option_order():
    paper = ExamPaper.objects.create(title="Arbitration context", subject="math")
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        stem="Which value is correct?",
        answer="C",
        analysis="Reference analysis",
        solution="Reference solution",
        question_type="single_choice",
        subject="math",
        difficulty="2.50",
        material="Read the material",
        tables=[{"rows": [["x", "3"]]}],
        subquestions=[{"stem": "Subquestion one"}],
    )
    for label, content, sort_order in (
        ("D", "four", 3),
        ("B", "two", 1),
        ("A", "one", 0),
        ("C", "three", 2),
    ):
        QuestionOption.objects.create(
            question=question,
            option_label=label,
            content=content,
            sort_order=sort_order,
        )
    factory = _CapturingFactory(
        {
            ModeAAnswerComponent: _component_responses()[ModeAAnswerComponent]
            | {
                "final_answer": "B",
                "reasoning_content": "private Qwen chain",
            },
            DeepSeekIndependentVerifierComponent: {
                "independent_answer": "C",
                "independent_reasoning_summary": "C follows from the options.",
                "key_facts": ["C is the only matching option"],
                "reference_answer_valid": True,
                "reference_analysis_valid": False,
                "reference_issues": ["analysis requires final review"],
                "confidence": 0.95,
                "mode_content": _component_responses()[ModeAAnswerComponent]
                | {"final_answer": "C"},
            },
            DeepSeekFinalReviewComponent: {
                "trusted_answer": "C",
                "qwen_content_valid": False,
                "candidate_issues": ["Qwen answer conflicts with reference"],
                "confidence": 0.99,
                "mode_content": _component_responses()[ModeAAnswerComponent]
                | {
                    "final_answer": "C",
                    "raw_response": {"provider": "private DeepSeek raw"},
                },
            },
        }
    )
    service = common_ai_service.AIReviewService(component_factory=factory)

    outcome = service.solve_mode_with_arbitration(
        question,
        mode="A",
        image_urls=("https://cdn.example.test/q.png",),
        normalized_text="Normalized stem",
        vision_result={"figure_present": True},
        knowledge_refs="linear equations",
    )

    assert outcome.answer["verification"]["status"] == "accepted"
    assert [component for component, _context in factory.calls] == [
        ModeAAnswerComponent,
        DeepSeekIndependentVerifierComponent,
        DeepSeekFinalReviewComponent,
    ]
    for component_type, context in factory.calls:
        assert list(context.options) == [
            {"label": "A", "content": "one"},
            {"label": "B", "content": "two"},
            {"label": "C", "content": "three"},
            {"label": "D", "content": "four"},
        ]
        assert context.stem == "Which value is correct?"
        assert context.answer == "C"
        assert context.solution == "Reference solution"
        assert context.image_urls == ("https://cdn.example.test/q.png",)
        assert context.metadata["reference_analysis"] == "Reference analysis"
        assert context.metadata["question_type"] == "single_choice"
        assert context.metadata["subject"] == "math"
        assert context.metadata["difficulty"] == "2.50"
        assert context.metadata["material"] == "Read the material"
        assert context.metadata["tables"] == ({"rows": (("x", "3"),)},)
        assert context.metadata["subquestions"] == (
            {"stem": "Subquestion one"},
        )
        assert context.metadata["normalized_text"] == "Normalized stem"
        assert context.metadata["vision_result"] == {"figure_present": True}
        assert context.metadata["knowledge_refs"] == "linear equations"
        assert context.metadata["target_mode"] == "A"
        assert "RelatedManager" not in repr(context.options)
        assert "Manager" not in repr(context.options)
        if component_type is DeepSeekFinalReviewComponent:
            assert context.metadata["qwen_result"]["final_answer"] == "B"
            assert context.metadata["independent_result"][
                "independent_answer"
            ] == "C"
    assert "reasoning_content" not in outcome.answer
    assert "raw_response" not in outcome.answer


def _arbitration_outcome(mode, shared):
    verification = {
        "status": "accepted",
        "context_hash": "same-context",
        "trusted_answer": "C",
    }
    return ArbitrationOutcome(
        answer={
            "mode": mode,
            "final_answer": "C",
            "verification": dict(verification),
        },
        verification=verification,
        shared_verifier_result=shared,
    )


@pytest.mark.parametrize("entrypoint", ["process_question_full", "process_question_full_v2"])
def test_full_entrypoints_route_all_modes_through_arbitration_and_reuse_shared_verification(
    entrypoint,
):
    question = SimpleNamespace(
        stem="Which value is correct?",
        subject="math",
        ai_processing_status=None,
        save=MagicMock(),
    )
    shared = {
        "context_hash": "same-context",
        "independent_answer": "C",
        "reference_answer_valid": True,
        "reference_analysis_valid": True,
        "reference_issues": [],
        "key_facts": ["The facts select C."],
        "confidence": 0.95,
    }
    service = common_ai_service.AIReviewService(
        component_factory=lambda component_type: MagicMock()
    )
    service._get_question_image_urls = MagicMock(
        return_value=["https://cdn.example.test/q.png"]
    )
    service.analyze_knowledge = MagicMock(return_value={"knowledge_points": []})
    service.probe_and_norm = MagicMock(
        return_value={
            "subject": "math",
            "normalized_text": "Normalized stem",
            "topic_tags_top3": ["linear equations"],
        }
    )
    service.analyze_knowledge_points = MagicMock(
        return_value={"knowledge_points": []}
    )
    service.vision_extraction = MagicMock(
        return_value={"figure_present": True}
    )
    service.verify_result = MagicMock(
        side_effect=AssertionError("legacy verifier must not run")
    )
    service.solve_mode_with_arbitration = MagicMock(
        side_effect=lambda _question, *, mode, **_kwargs: _arbitration_outcome(
            mode, shared
        )
    )

    with patch.object(
        ExamQuestion.objects, "get", return_value=question
    ):
        results = getattr(service, entrypoint)("question-id")

    assert [
        call.kwargs["mode"]
        for call in service.solve_mode_with_arbitration.call_args_list
    ] == ["A", "B", "C"]
    calls = service.solve_mode_with_arbitration.call_args_list
    assert calls[0].kwargs["cached_verification"] is None
    assert calls[1].kwargs["cached_verification"] == shared
    assert calls[2].kwargs["cached_verification"] == shared
    for mode in "ABC":
        answer = results[f"answer_{mode.lower()}"]
        assert answer["mode"] == mode
        assert answer["verification"]["context_hash"] == "same-context"
    assert results["verifier"] == shared
    assert "mode_content" not in results["verifier"]
    service.verify_result.assert_not_called()


def test_full_pipeline_keeps_failed_mode_non_savable_without_legacy_fallback():
    question = SimpleNamespace(
        stem="Question",
        subject="math",
        ai_processing_status=None,
        save=MagicMock(),
    )
    service = common_ai_service.AIReviewService(
        component_factory=lambda component_type: MagicMock()
    )
    service._get_question_image_urls = MagicMock(return_value=[])
    service.analyze_knowledge = MagicMock(return_value={"knowledge_points": []})
    service.generate_answer_b = MagicMock(
        side_effect=AssertionError("legacy B fallback was called")
    )

    def arbitrate(_question, *, mode, **_kwargs):
        if mode == "B":
            raise ArbitrationProviderError()
        return _arbitration_outcome(mode, None)

    service.solve_mode_with_arbitration = MagicMock(side_effect=arbitrate)

    with patch.object(ExamQuestion.objects, "get", return_value=question):
        results = service.process_question_full("question-id")

    assert results["errors"] == {"answer_b": "arbitration_provider_failure"}
    assert results["answer_b"] == {
        "error": "arbitration_provider_failure",
        "provider": service._task_route("mode_b_answer")[0],
        "model": service._task_route("mode_b_answer")[1],
        "generated_at": results["answer_b"]["generated_at"],
    }
    service.generate_answer_b.assert_not_called()


def test_full_v2_keeps_failed_mode_partial_without_raw_solver_fallback():
    question = SimpleNamespace(
        stem="Question",
        subject="math",
        ai_processing_status=None,
        save=MagicMock(),
    )
    service = common_ai_service.AIReviewService(
        component_factory=lambda component_type: MagicMock()
    )
    service._get_question_image_urls = MagicMock(return_value=[])
    service.probe_and_norm = MagicMock(
        return_value={"normalized_text": "Question", "topic_tags_top3": []}
    )
    service.analyze_knowledge_points = MagicMock(
        return_value={"knowledge_points": []}
    )
    service.vision_extraction = MagicMock(return_value={})
    service.verify_result = MagicMock(return_value={"pass": True})
    service.solve_mode_b = MagicMock(
        side_effect=AssertionError("raw V2 B solver was called")
    )

    def arbitrate(_question, *, mode, **_kwargs):
        if mode == "B":
            raise ArbitrationProviderError()
        return _arbitration_outcome(mode, None)

    service.solve_mode_with_arbitration = MagicMock(side_effect=arbitrate)

    with patch.object(ExamQuestion.objects, "get", return_value=question):
        results = service.process_question_full_v2("question-id")

    assert results["errors"] == {"answer_b": "arbitration_provider_failure"}
    assert results["answer_b"] == {"error": "arbitration_provider_failure"}
    assert results["answer_a"]["verification"]["status"] == "accepted"
    assert results["answer_c"]["verification"]["status"] == "accepted"
    assert question.ai_processing_status == "failed"
    service.solve_mode_b.assert_not_called()


@pytest.mark.parametrize("entrypoint", ["process_question_full", "process_question_full_v2"])
@pytest.mark.parametrize("model", [None, "qwen3-vl-plus", "unsupported-model"])
def test_arbitrated_full_pipeline_uses_actual_mode_route_audit_metadata(
    entrypoint, model
):
    question = SimpleNamespace(
        stem="Question",
        subject="math",
        ai_processing_status=None,
        save=MagicMock(),
    )
    service = common_ai_service.AIReviewService(
        component_factory=lambda component_type: MagicMock()
    )
    service._get_question_image_urls = MagicMock(return_value=[])
    service.analyze_knowledge = MagicMock(return_value={"knowledge_points": []})
    service.probe_and_norm = MagicMock(
        return_value={"normalized_text": "Question", "topic_tags_top3": []}
    )
    service.analyze_knowledge_points = MagicMock(
        return_value={"knowledge_points": []}
    )
    service.vision_extraction = MagicMock(return_value={})
    service.solve_mode_with_arbitration = MagicMock(
        side_effect=lambda _question, *, mode, **_kwargs: _arbitration_outcome(
            mode, None
        )
    )

    with patch.object(ExamQuestion.objects, "get", return_value=question):
        results = getattr(service, entrypoint)("question-id", model=model)

    assert [results[f"answer_{mode.lower()}"]["model"] for mode in "ABC"] == [
        service._task_route("mode_a_answer")[1],
        service._task_route("mode_b_answer")[1],
        service._task_route("mode_c_answer")[1],
    ]
    assert [results[f"answer_{mode.lower()}"]["provider"] for mode in "ABC"] == [
        service._task_route("mode_a_answer")[0],
        service._task_route("mode_b_answer")[0],
        service._task_route("mode_c_answer")[0],
    ]
    assert all(
        call.kwargs["model"] == model
        for call in service.solve_mode_with_arbitration.call_args_list
    )


@pytest.mark.django_db
def test_shared_verifier_save_reuses_hash_matched_cache_and_failure_preserves_old_value():
    from apps.review import tasks

    question = _make_question()
    context = QuestionContextBuilder.build(
        question,
        normalized_text=question.stem,
        vision_result={},
    )
    context_hash = question_context_hash(context)
    shared = {
        'context_hash': context_hash,
        'independent_answer': '2',
        'reference_answer_valid': True,
        'reference_analysis_valid': None,
        'reference_issues': [],
        'key_facts': ['1 + 1 equals 2.'],
        'confidence': 0.96,
    }
    saver = common_ai_service.AIReviewService(
        component_factory=lambda component_type: MagicMock()
    )
    saver.save_results_to_question(
        str(question.id), {'verifier': shared, 'errors': {}}
    )
    question.refresh_from_db()
    assert question.ai_verifier_result == shared

    service = MagicMock()
    service._get_question_image_urls.return_value = []
    service._task_route.return_value = ('qwen', 'configured-model')
    service.solve_mode_with_arbitration.return_value = ArbitrationOutcome(
        answer={'mode': 'A', 'final_answer': '2'},
        verification={'status': 'accepted', 'context_hash': context_hash},
        shared_verifier_result=shared,
    )
    with (
        patch.object(tasks, 'create_ai_review_service', return_value=service),
        patch.object(tasks.cache, 'set'),
    ):
        result = tasks.single_mode_ai_process_question.run(str(question.id), 'A')
    assert result['status'] == 'complete'
    assert service.solve_mode_with_arbitration.call_args.kwargs[
        'cached_verification'
    ] == shared

    question.refresh_from_db()
    question.ai_verifier_result = shared
    question.save(update_fields=['ai_verifier_result'])
    saver.save_results_to_question(
        str(question.id),
        {'verifier': {'error': 'legacy verifier failed'}, 'errors': {'verifier': 'failed'}},
    )
    question.refresh_from_db()
    assert question.ai_verifier_result == shared
