from __future__ import annotations

import inspect
import traceback
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.config import (
    AIConfig,
    AIProviderConfig,
    AITaskConfig,
    reset_ai_config_for_tests,
)
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError
from apps.courses import ai_service, tasks, views
from apps.courses.models import Course, CourseQuestionLink, VariantTask
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion


_SURROGATE_API_KEYS = ("\ud800", "\udfff", "正常\ud800key")
_NORMAL_UNICODE_API_KEY = "正常共享密钥"


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


def test_legacy_module_call_ai_keeps_argument_order():
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


def test_deepseek_availability_converts_missing_config_to_skip(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "load_ai_config",
        lambda: (_ for _ in ()).throw(
            AIConfigError("DEEPSEEK_API_KEY is not configured")
        ),
    )

    assert ai_service.deepseek_verification_available() is False


def test_real_course_factory_constructs_and_skips_optional_missing_deepseek_key(
    monkeypatch,
):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    reset_ai_config_for_tests()
    try:
        generator = tasks.variant_generator_component_factory()
        available = tasks.deepseek_verification_available()
    finally:
        if "generator" in locals():
            generator._ai_client.close()
        reset_ai_config_for_tests()

    assert available is False


def _legacy_config(*, qwen_api_key: str = "qwen-test-key"):
    providers = {
        "qwen": AIProviderConfig(
            name="qwen",
            api_url="https://example.test/qwen",
            api_key=qwen_api_key,
        ),
        "deepseek": AIProviderConfig(
            name="deepseek",
            api_url="https://example.test/deepseek",
            api_key="deepseek-test-key",
        ),
    }
    tasks_by_key = {
        "variant_generate": AITaskConfig(
            key="variant_generate",
            provider="qwen",
            model="qwen3.7-plus",
            prompt="unused",
            prompt_key="variant_generate",
            temperature=0.5,
            max_tokens=8192,
            timeout_seconds=300,
            retry_count=0,
            retry_backoff_seconds=(),
            response_format="json",
        ),
        "variant_verify_deepseek": AITaskConfig(
            key="variant_verify_deepseek",
            provider="deepseek",
            model="deepseek-v4-pro",
            prompt="unused",
            prompt_key="variant_verify_deepseek",
            temperature=0.1,
            max_tokens=8192,
            timeout_seconds=300,
            retry_count=0,
            retry_backoff_seconds=(),
            response_format="json",
        ),
    }
    return AIConfig(providers=providers, tasks=tasks_by_key, prompts={})


def test_legacy_module_call_ai_accepts_default_positional_and_keyword_forms(
    monkeypatch,
):
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def complete(self, task_key, **kwargs):
            calls.append((task_key, kwargs))
            return SimpleNamespace(content=task_key)

    config = _legacy_config()
    monkeypatch.setattr(ai_service, "load_ai_config", lambda: config)
    monkeypatch.setattr(ai_service, "AIClient", FakeClient)

    default_result = ai_service.call_ai(
        "system", "user", "qwen3.7-plus"
    )
    positional_result = ai_service.call_ai(
        "verify-system",
        "verify-user",
        "deepseek-v4-pro",
        "https://example.test/deepseek",
        "deepseek-test-key",
        2000,
        0.1,
    )
    keyword_result = ai_service.call_ai(
        system_prompt="system-2",
        user_prompt="user-2",
        model="qwen3.7-plus",
        api_url="https://example.test/qwen",
        api_key="qwen-test-key",
        max_tokens=8192,
        temperature=0.5,
    )

    assert (default_result, positional_result, keyword_result) == (
        "variant_generate",
        "variant_verify_deepseek",
        "variant_generate",
    )
    assert [call[0] for call in calls] == [
        "variant_generate",
        "variant_verify_deepseek",
        "variant_generate",
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "unconfigured-model"},
        {
            "model": "qwen3.7-plus",
            "api_url": "https://attacker.test/qwen",
        },
        {"model": "qwen3.7-plus", "api_key": "wrong-key"},
        {"model": "qwen3.7-plus", "api_key": "错误密钥"},
        {"model": "qwen3.7-plus", "max_tokens": 1234},
        {"model": "qwen3.7-plus", "max_tokens": []},
        {"model": "qwen3.7-plus", "temperature": 1.5},
        {"model": "qwen3.7-plus", "temperature": []},
    ],
)
def test_legacy_module_call_ai_rejects_unconfigured_overrides_safely(
    monkeypatch, overrides
):
    calls = []
    monkeypatch.setattr(ai_service, "load_ai_config", _legacy_config)
    monkeypatch.setattr(
        ai_service,
        "AIClient",
        lambda: calls.append("constructed") or None,
    )

    with pytest.raises(
        AIRequestError, match="Legacy AI request does not match configured task"
    ) as caught:
        ai_service.call_ai("system", "user", **overrides)

    assert calls == []
    assert "wrong-key" not in str(caught.value)
    assert "attacker" not in str(caught.value)


def _capture_surrogate_key_error(key_index: int) -> AIRequestError:
    try:
        ai_service.call_ai(
            "system",
            "user",
            model="qwen3.7-plus",
            api_key=_SURROGATE_API_KEYS[key_index],
        )
    except AIRequestError as error:
        return error
    raise AssertionError("legacy surrogate key was not rejected")


@pytest.mark.parametrize("key_index", range(len(_SURROGATE_API_KEYS)))
def test_legacy_module_call_ai_rejects_surrogate_keys_without_leaking(
    monkeypatch, key_index
):
    calls = []
    monkeypatch.setattr(ai_service, "load_ai_config", _legacy_config)
    monkeypatch.setattr(
        ai_service,
        "AIClient",
        lambda: calls.append("constructed") or None,
    )

    error = _capture_surrogate_key_error(key_index)
    formatted = "".join(
        traceback.TracebackException(
            type(error),
            error,
            error.__traceback__,
            capture_locals=True,
        ).format()
    )
    escaped_key = _SURROGATE_API_KEYS[key_index].encode(
        "unicode_escape"
    ).decode("ascii")

    assert str(error) == "Legacy AI request does not match configured task"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert _SURROGATE_API_KEYS[key_index] not in formatted
    assert escaped_key not in formatted
    assert calls == []


def test_legacy_module_call_ai_preserves_matching_normal_unicode_key(
    monkeypatch,
):
    calls = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def complete(self, task_key, **kwargs):
            calls.append((task_key, kwargs))
            return SimpleNamespace(content="unicode-key-ok")

    config = _legacy_config(qwen_api_key=_NORMAL_UNICODE_API_KEY)
    monkeypatch.setattr(ai_service, "load_ai_config", lambda: config)
    monkeypatch.setattr(ai_service, "AIClient", FakeClient)

    result = ai_service.call_ai(
        "system",
        "user",
        model="qwen3.7-plus",
        api_key=_NORMAL_UNICODE_API_KEY,
    )

    assert result == "unicode-key-ok"
    assert calls == [
        (
            "variant_generate",
            {"system": "system", "user": "user"},
        )
    ]


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
