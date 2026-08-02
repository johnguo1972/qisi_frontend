from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError
from apps.courses import ai_service, tasks, views
from apps.courses.models import Course, CourseQuestionLink, VariantTask
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion


VALID_VARIANT = {
    "stem": "若 x + 3 = 8，则 x 等于多少？",
    "question_type": "single_choice",
    "options": [
        {"label": "A", "content": "3"},
        {"label": "B", "content": "4"},
        {"label": "C", "content": "5"},
        {"label": "D", "content": "6"},
    ],
    "answer": "C",
    "analysis": "移项。",
    "solution": "x=5。",
    "difficulty": 2,
    "knowledge_points": [{"module": "方程"}],
    "variant_mode": "数值变化",
    "changes_from_original": "常数变化。",
}


def _generation_result(variant=None):
    parsed = dict(variant or VALID_VARIANT)
    return {
        "parsed": parsed,
        "raw_response": "provider generation raw",
        "response_json": '{"id":"generation"}',
        "provider": "qwen",
        "model": "qwen3.7-plus",
        "latency_ms": 31,
    }


def _verification_result(*, passed=True, summary="校验通过"):
    return {
        "passed": passed,
        "issues": [] if passed else ["答案需复核"],
        "score": 0.95 if passed else 0.55,
        "summary": summary,
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "latency_ms": 17,
    }


class FakeGenerator:
    def __init__(self, result=None, error=None, order=None):
        self.result = result or _generation_result()
        self.error = error
        self.calls = []
        self.order = order

    def generate(self, question, variant_mode):
        assert isinstance(question, QuestionInput)
        self.calls.append((question, variant_mode))
        if self.order is not None:
            self.order.append("variant_generate")
        if self.error is not None:
            raise self.error
        return self.result


class FakeVerifier:
    def __init__(self, outcomes=None, order=None):
        self.outcomes = list(outcomes or [_verification_result()])
        self.calls = []
        self.order = order

    def verify(self, task_key, original, candidate):
        self.calls.append((task_key, original, candidate))
        if self.order is not None:
            self.order.append(task_key)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def variant_records(db):
    teacher = UserAccount.objects.create(
        mobile="13800009001",
        display_name="变式教师",
        role_type="teacher",
    )
    outsider = UserAccount.objects.create(
        mobile="13800009002",
        display_name="其他教师",
        role_type="teacher",
    )
    paper = ExamPaper.objects.create(title="变式试卷", subject="math")
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        question_type="single_choice",
        subject="math",
        stem="若 x + 2 = 7，则 x 等于多少？",
        answer="C",
        analysis="移项。",
        solution="x=5。",
        difficulty=2,
        knowledge_points=[{"module": "方程"}],
        review_status="confirmed",
    )
    course = Course.objects.create(
        name="变式课程",
        subject="math",
        grade_level="七年级",
        teacher=teacher,
    )
    CourseQuestionLink.objects.create(
        course=course,
        question=question,
        source="manual",
    )
    return SimpleNamespace(
        teacher=teacher,
        outsider=outsider,
        paper=paper,
        question=question,
        course=course,
    )


def _install_components(monkeypatch, generator, verifier, *, available=True):
    monkeypatch.setattr(
        tasks,
        "variant_generator_component_factory",
        lambda: generator,
        raising=False,
    )
    monkeypatch.setattr(
        tasks,
        "result_verifier_component_factory",
        lambda: verifier,
        raising=False,
    )
    monkeypatch.setattr(
        tasks,
        "deepseek_verification_available",
        lambda: available,
        raising=False,
    )
    monkeypatch.setattr(
        tasks,
        "call_ai",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy provider path used")
        ),
        raising=False,
    )


@pytest.mark.django_db
def test_task_calls_qwen_then_deepseek_and_persists_confirmable_fields(
    monkeypatch, variant_records
):
    order = []
    generator = FakeGenerator(order=order)
    verifier = FakeVerifier(order=order)
    _install_components(monkeypatch, generator, verifier)

    result = tasks.generate_variant_task.run(
        variant_records.question.id, "数值变化"
    )

    assert order == ["variant_generate", "variant_verify_deepseek"]
    assert len(generator.calls) == 1
    assert len(verifier.calls) == 1
    variant_task = VariantTask.objects.get(id=result["variant_task_id"])
    generated = ExamQuestion.objects.get(id=result["question_id"])
    assert result["status"] == "success"
    assert variant_task.status == "success"
    assert variant_task.generator_result == {
        "status": "generated",
        "model": "qwen3.7-plus",
        "latency_ms": 31,
        "raw_response": "provider generation raw",
        "timestamp": variant_task.generator_result["timestamp"],
    }
    assert variant_task.verifier_result == _verification_result()
    assert variant_task.generated_question == VALID_VARIANT
    assert variant_task.completed_at is not None
    assert generated.original_question == variant_records.question
    assert generated.review_status == "need_review"
    assert generated.need_review is True
    assert generated.stem == VALID_VARIANT["stem"]
    assert list(
        generated.options.order_by("sort_order").values_list(
            "option_label", flat=True
        )
    ) == ["A", "B", "C", "D"]


@pytest.mark.django_db
def test_failed_verification_retries_only_deepseek_once_without_regeneration(
    monkeypatch, variant_records
):
    order = []
    generator = FakeGenerator(order=order)
    verifier = FakeVerifier(
        [
            _verification_result(passed=False, summary="首次失败"),
            _verification_result(),
        ],
        order=order,
    )
    _install_components(monkeypatch, generator, verifier)

    result = tasks.generate_variant_task.run(
        variant_records.question.id, "数值变化"
    )

    assert result["status"] == "success"
    assert order == [
        "variant_generate",
        "variant_verify_deepseek",
        "variant_verify_deepseek",
    ]
    assert len(generator.calls) == 1
    assert len(verifier.calls) == 2
    task = VariantTask.objects.get(id=result["variant_task_id"])
    assert task.verifier_result["passed"] is True


@pytest.mark.django_db
def test_missing_deepseek_key_keeps_existing_skip_and_never_calls_verifier(
    monkeypatch, variant_records
):
    generator = FakeGenerator()
    verifier = FakeVerifier()
    _install_components(monkeypatch, generator, verifier, available=False)
    monkeypatch.setattr(
        tasks,
        "get_deepseek_model",
        lambda: (_ for _ in ()).throw(
            AssertionError("DeepSeek config accessed after missing-key skip")
        ),
    )

    result = tasks.generate_variant_task.run(
        variant_records.question.id, "数值变化"
    )

    task = VariantTask.objects.get(id=result["variant_task_id"])
    assert result["status"] == "success"
    assert len(generator.calls) == 1
    assert verifier.calls == []
    assert task.verifier_result is None


@pytest.mark.django_db
@pytest.mark.parametrize("error_type", [AIRequestError, AIResponseError])
def test_verifier_provider_or_payload_error_retries_once_without_qwen_fallback(
    monkeypatch, variant_records, error_type
):
    order = []
    generator = FakeGenerator(order=order)
    verifier = FakeVerifier(
        [error_type("deepseek failed"), error_type("deepseek failed again")],
        order=order,
    )
    _install_components(monkeypatch, generator, verifier)
    monkeypatch.setattr(tasks.time, "sleep", lambda _seconds: None)

    result = tasks.generate_variant_task.run(
        variant_records.question.id, "数值变化"
    )

    task = VariantTask.objects.get(id=result["variant_task_id"])
    assert order == [
        "variant_generate",
        "variant_verify_deepseek",
        "variant_verify_deepseek",
    ]
    assert len(generator.calls) == 1
    assert task.status == "success"
    assert task.verifier_result == {
        "error": "deepseek failed again",
        "model": "deepseek-v4-pro",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("error", [AIRequestError("qwen down"), AIResponseError("bad json")])
def test_generation_failure_sets_error_state_and_keeps_celery_retry_contract(
    monkeypatch, variant_records, error
):
    generator = FakeGenerator(error=error)
    verifier = FakeVerifier()
    _install_components(monkeypatch, generator, verifier)
    captured = {}

    def retry(*, exc, countdown):
        captured.update(exc=exc, countdown=countdown)
        raise exc

    monkeypatch.setattr(tasks.generate_variant_task, "retry", retry)

    with pytest.raises(type(error), match=str(error)):
        tasks.generate_variant_task.run(
            variant_records.question.id, "数值变化"
        )

    variant_task = VariantTask.objects.get(
        original_question=variant_records.question
    )
    assert variant_task.status == "failed"
    assert variant_task.error_message == str(error)
    assert variant_task.completed_at is not None
    assert captured["countdown"] == 30
    assert captured["exc"] is error


def test_legacy_service_is_a_thin_component_adapter(monkeypatch):
    generator = FakeGenerator()
    verifier = FakeVerifier()
    monkeypatch.setattr(
        ai_service,
        "variant_generator_component_factory",
        lambda: generator,
        raising=False,
    )
    monkeypatch.setattr(
        ai_service,
        "result_verifier_component_factory",
        lambda: verifier,
        raising=False,
    )

    service = ai_service.VariantAIService()
    generated = service.generate(_question_input(), "数值变化")
    verified = service.verify({}, VALID_VARIANT)

    assert generated["provider"] == "qwen"
    assert verified["provider"] == "deepseek"
    assert len(generator.calls) == 1
    assert len(verifier.calls) == 1


def test_legacy_module_call_ai_keeps_argument_order_and_forwards_to_shared_task(
    monkeypatch,
):
    calls = []

    class FakeClient:
        def complete(self, task_key, **kwargs):
            calls.append((task_key, kwargs))
            return SimpleNamespace(content="shared-result")

    monkeypatch.setattr(ai_service, "AIClient", FakeClient)

    parameters = tuple(inspect.signature(ai_service.call_ai).parameters)
    assert parameters == (
        "system_prompt",
        "user_prompt",
        "model",
        "api_url",
        "api_key",
        "max_tokens",
        "temperature",
    )
    assert ai_service.call_ai("system", "user", "legacy-model") == "shared-result"
    assert calls == [
        (
            "variant_generate",
            {"system": "system", "user": "user"},
        )
    ]


def test_deepseek_availability_converts_missing_config_to_skip(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "load_ai_config",
        lambda: (_ for _ in ()).throw(
            AIConfigError("DEEPSEEK_API_KEY is not configured")
        ),
    )

    assert ai_service.deepseek_verification_available() is False


def _question_input():
    return QuestionInput(
        stem="原题",
        answer="1",
        metadata={"question_type": "fill_blank"},
    )


@pytest.mark.django_db
def test_single_view_uses_injectable_dispatch_and_keeps_envelope_and_permission(
    monkeypatch, variant_records
):
    dispatched = []
    monkeypatch.setattr(
        views,
        "generate_variant_task_dispatch",
        lambda **kwargs: dispatched.append(kwargs) or SimpleNamespace(id="task-1"),
        raising=False,
    )
    monkeypatch.setattr(
        tasks.generate_variant_task,
        "delay",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("non-injectable dispatch used")
        ),
    )
    request = APIRequestFactory().post(
        "/unused",
        {"variant_mode": "数值变化", "tree_node_id": None},
        format="json",
    )
    force_authenticate(request, user=variant_records.teacher)

    response = views.question_generate_variant(
        request,
        course_id=variant_records.course.id,
        question_id=variant_records.question.id,
    )

    assert response.status_code == 200
    assert response.data == {
        "success": True,
        "data": {
            "task_id": "task-1",
            "status": "pending",
            "question_id": variant_records.question.id,
        },
        "message": "变式题生成任务已提交",
    }
    assert dispatched == [
        {
            "question_id": variant_records.question.id,
            "variant_mode": "数值变化",
            "tree_node_id": None,
        }
    ]

    unauthorized = APIRequestFactory().post(
        "/unused", {"variant_mode": "数值变化"}, format="json"
    )
    denied = views.question_generate_variant(
        unauthorized,
        course_id=variant_records.course.id,
        question_id=variant_records.question.id,
    )
    assert denied.status_code in (401, 403)


@pytest.mark.django_db
def test_batch_view_uses_injectable_dispatch_and_keeps_envelope(
    monkeypatch, variant_records
):
    dispatched = []
    monkeypatch.setattr(
        views,
        "batch_variant_task_dispatch",
        lambda **kwargs: dispatched.append(kwargs) or SimpleNamespace(id="batch-1"),
        raising=False,
    )
    monkeypatch.setattr(
        tasks.batch_generate_variants_task,
        "delay",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("non-injectable batch dispatch used")
        ),
    )
    question_ids = [variant_records.question.id]
    request = APIRequestFactory().post(
        "/unused",
        {"question_ids": question_ids, "variant_mode": "情境变化"},
        format="json",
    )
    force_authenticate(request, user=variant_records.teacher)

    response = views.question_batch_generate_variant(
        request, course_id=variant_records.course.id
    )

    assert response.status_code == 200
    assert response.data == {
        "success": True,
        "data": {
            "task_id": "batch-1",
            "status": "pending",
            "question_count": 1,
        },
        "message": "已提交 1 道变式题生成任务",
    }
    assert dispatched == [
        {
            "question_ids": [str(question_id) for question_id in question_ids],
            "variant_mode": "情境变化",
            "tree_node_id": None,
        }
    ]


@pytest.mark.django_db
def test_confirm_view_keeps_confirmed_persistence_and_response(
    variant_records,
):
    generated = ExamQuestion.objects.create(
        paper=variant_records.paper,
        question_no="temporary",
        question_type="fill_blank",
        subject="math",
        stem="变式题",
        original_question=variant_records.question,
        review_status="need_review",
        need_review=True,
    )
    task = VariantTask.objects.create(
        original_question=variant_records.question,
        variant_mode="数值变化",
        status="success",
        generated_question=VALID_VARIANT,
    )
    generated.question_no = f"VAR-{task.id}"
    generated.save(update_fields=["question_no"])
    request = APIRequestFactory().post("/unused", {}, format="json")
    force_authenticate(request, user=variant_records.teacher)

    response = views.variant_task_confirm(
        request, course_id=variant_records.course.id, task_id=task.id
    )

    generated.refresh_from_db()
    task.refresh_from_db()
    assert response.status_code == 200
    assert response.data == {
        "success": True,
        "data": {"question_id": generated.id},
        "message": "变式题已确认入库",
    }
    assert generated.review_status == "confirmed"
    assert generated.need_review is False
    assert task.status == "confirmed"
