from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError
from apps.study import ai_helper, guidance_views


def _authenticated_student_client(student):
    from rest_framework.test import APIClient

    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role
    from apps.accounts.services import generate_tokens
    from apps.institutions.models import Class, ClassStudent, Institution

    grant_user_role(student, "student")
    teacher = UserAccount.objects.create(
        role_type="teacher",
        mobile=f"t{student.mobile}",
        display_name="Test teacher",
    )
    institution = Institution.objects.create(
        institution_name="Guidance permission institution",
        created_by=teacher,
    )
    class_obj = Class.objects.create(
        institution=institution,
        creator_teacher=teacher,
        class_name="Guidance permission class",
    )
    ClassStudent.objects.create(
        class_obj=class_obj,
        student=student,
        join_type="manual",
        status="active",
    )
    client = APIClient()
    token = generate_tokens(student, "student")["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _plain_view_handler(decorated_view):
    return decorated_view.cls.post.__closure__[0].cell_contents


class _Session:
    def __init__(self, **overrides):
        self.id = "session-7"
        self.session_status = "running"
        self.mode_type = "C"
        self.invalid_input_count = 0
        self.question_id = 7
        self.content_log_json = {"step_index": 0, "steps": [], "answers": []}
        self.saved_update_fields: list[object] = []
        for key, value in overrides.items():
            setattr(self, key, value)

    def save(self, *args, **kwargs):
        self.saved_update_fields.append(kwargs.get("update_fields"))


class _SessionManager:
    def __init__(self, session):
        self.session = session

    def filter(self, **kwargs):
        return SimpleNamespace(update=lambda **values: 0)

    def create(self, **values):
        for key, value in values.items():
            if key in {"student_user_id", "question_id"}:
                continue
            setattr(self.session, key, value)
        self.session.question_id = values["question_id"]
        return self.session

    def get(self, **kwargs):
        return self.session


def _install_study_models(monkeypatch, session, question):
    class SessionModel:
        class DoesNotExist(Exception):
            pass

        objects = _SessionManager(session)

    class QuestionModel:
        class DoesNotExist(Exception):
            pass

        objects = SimpleNamespace(get=lambda **kwargs: question)

    monkeypatch.setattr(guidance_views, "AIGuidanceSession", SessionModel)
    monkeypatch.setattr(guidance_views, "ExamQuestion", QuestionModel)
    monkeypatch.setattr(
        guidance_views,
        "_build_question_info",
        lambda question: {"stem": question.stem},
    )


def _question(**overrides):
    values = {
        "stem": "题目",
        "answer": "D",
        "question_type": "fill_blank",
        "ai_answer_b": {},
        "ai_answer_c": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_start_c_guidance_generates_three_steps_and_persists_legacy_shape(
    monkeypatch,
):
    session = _Session()
    question = _question()
    _install_study_models(monkeypatch, session, question)

    class Component:
        def generate(self, question_input):
            assert question_input.stem == "题目"
            assert question_input.answer == "D"
            return {
                "steps": [
                    {"question": "第一问", "hint": "提示一"},
                    {"question": "第二问", "hint": "提示二"},
                    {"question": "第三问", "hint": "提示三"},
                ]
            }

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    monkeypatch.setattr(
        guidance_views,
        "call_qwen_for_guidance_with_question",
        lambda *args: pytest.fail("legacy Qwen helper was called"),
        raising=False,
    )
    request = SimpleNamespace(
        data={"question_id": 7, "mode_type": "C"},
        user=SimpleNamespace(id=9),
    )

    response = _plain_view_handler(guidance_views.start_guidance)(request)

    assert response.status_code == 200
    assert response.data["code"] == 0
    assert response.data["message"] == "success"
    assert response.data["data"] == {
        "session_id": "session-7",
        "mode": "C",
        "step_index": 0,
        "total_steps": 3,
        "hint": "第一问",
        "question_info": {"stem": "题目"},
    }
    assert session.content_log_json["ai_c_generated"] == {
        "questions": [
            {
                "question": "第一问",
                "reference_answer": "提示一",
                "key_points": [],
            },
            {
                "question": "第二问",
                "reference_answer": "提示二",
                "key_points": [],
            },
            {
                "question": "第三问",
                "reference_answer": "提示三",
                "key_points": [],
            },
        ]
    }
    assert session.saved_update_fields == [["content_log_json"]]


def test_start_c_guidance_never_persists_component_extra_step_fields(
    monkeypatch,
):
    session = _Session()
    question = _question()
    _install_study_models(monkeypatch, session, question)

    class Component:
        def generate(self, question_input):
            return {
                "steps": [
                    {
                        "question": "第一问",
                        "hint": "提示一",
                        "key_points": ["POISON"],
                        "unexpected": "POISON",
                    },
                    {"question": "第二问", "hint": "提示二"},
                    {"question": "第三问", "hint": "提示三"},
                ],
                "unexpected": "POISON",
            }

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
    )
    request = SimpleNamespace(
        data={"question_id": 7, "mode_type": "C"},
        user=SimpleNamespace(id=9),
    )

    response = _plain_view_handler(guidance_views.start_guidance)(request)

    assert response.status_code == 200
    generated = session.content_log_json["ai_c_generated"]
    assert generated["questions"][0]["key_points"] == []
    assert "POISON" not in str(generated)


@pytest.mark.parametrize(
    "error",
    [
        AIConfigError("missing key"),
        AIRequestError("provider failed"),
        AIRequestError("AI provider request timed out"),
        AIResponseError("malformed response"),
    ],
)
def test_start_c_guidance_keeps_existing_b_downgrade_on_ai_failure(
    monkeypatch, error
):
    session = _Session()
    question = _question()
    _install_study_models(monkeypatch, session, question)

    called = []

    class Component:
        def generate(self, question_input):
            called.append(question_input)
            raise error

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    request = SimpleNamespace(
        data={"question_id": 7, "mode_type": "C"},
        user=SimpleNamespace(id=9),
    )

    response = _plain_view_handler(guidance_views.start_guidance)(request)

    assert response.status_code == 200
    assert response.data["data"]["mode"] == "B"
    assert response.data["data"]["downgraded"] is True
    assert response.data["data"]["downgrade_reason"] == (
        "非固定选项引导数据不可用，已降级到固定选项引导模式"
    )
    assert session.mode_type == "B"
    assert session.session_status == "downgraded"
    assert len(called) == 1


def test_student_c_reply_uses_injected_component_and_preserves_envelope(
    monkeypatch,
):
    session = _Session(
        content_log_json={"step_index": 0, "steps": [], "answers": []}
    )
    question = _question(
        ai_answer_c={
            "questions": [
                {"question": "第一问"},
                {"question": "第二问"},
            ]
        }
    )
    _install_study_models(monkeypatch, session, question)

    class Component:
        def evaluate_student_reply(self, context):
            assert context.question_text == "题目"
            assert context.reference_answer == "D"
            assert context.student_answer == "我的回答"
            return "思路正确，请继续。"

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    monkeypatch.setattr(
        guidance_views,
        "call_qwen_for_guidance",
        lambda *args: pytest.fail("legacy Qwen helper was called"),
        raising=False,
    )
    request = SimpleNamespace(
        data={"reply": "我的回答"}, user=SimpleNamespace(id=9)
    )

    response = _plain_view_handler(guidance_views.guidance_reply)(
        request, "session-7"
    )

    assert response.status_code == 200
    assert response.data["code"] == 0
    assert response.data["message"] == "success"
    assert response.data["data"] == {
        "mode": "C",
        "step_index": 1,
        "total_steps": 2,
        "evaluation": "思路正确，请继续。",
        "next_hint": "第二问",
        "is_completed": False,
    }
    assert session.content_log_json["answers"] == [
        {"step": 0, "user_answer": "我的回答"}
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AIConfigError("missing key"), "（AI 暂不可用）"),
        (
            AIRequestError("provider failed"),
            "（AI 评价暂时不可用：AIRequestError）",
        ),
        (
            AIRequestError("AI provider request timed out"),
            "（AI 评价暂时不可用：AIRequestError）",
        ),
        (
            AIResponseError("malformed response"),
            "（AI 评价暂时不可用：AIResponseError）",
        ),
    ],
)
def test_student_c_reply_keeps_legacy_ai_failure_text(
    monkeypatch, error, expected
):
    session = _Session()
    question = _question(
        ai_answer_c={
            "questions": [
                {"question": "第一问"},
                {"question": "第二问"},
            ]
        }
    )
    _install_study_models(monkeypatch, session, question)

    class Component:
        def evaluate_student_reply(self, context):
            raise error

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    request = SimpleNamespace(
        data={"reply": "我的回答"}, user=SimpleNamespace(id=9)
    )

    response = _plain_view_handler(guidance_views.guidance_reply)(
        request, "session-7"
    )

    assert response.status_code == 200
    assert response.data["data"]["evaluation"] == expected
    assert response.data["data"]["next_hint"] == "第二问"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AIConfigError("missing key"), "（AI 暂不可用）"),
        (
            AIRequestError("provider failed"),
            "（AI 评价暂时不可用：AIRequestError）",
        ),
        (
            AIRequestError("AI provider request timed out"),
            "（AI 评价暂时不可用：AIRequestError）",
        ),
        (
            AIResponseError("malformed response"),
            "（AI 评价暂时不可用：AIResponseError）",
        ),
    ],
)
def test_legacy_student_evaluation_wrapper_keeps_safe_fallback(
    monkeypatch, error, expected
):
    class Component:
        def evaluate_student_reply(self, context):
            raise error

    monkeypatch.setattr(
        ai_helper, "guidance_component_factory", lambda: Component(), raising=False
    )

    assert ai_helper.call_qwen_for_guidance("system", "user") == expected


@pytest.mark.parametrize(
    "error",
    [
        AIConfigError("missing key"),
        AIRequestError("provider failed"),
        AIRequestError("AI provider request timed out"),
        AIResponseError("malformed response"),
    ],
)
def test_legacy_generation_wrapper_keeps_empty_dict_fallback(
    monkeypatch, error
):
    called = []

    class Component:
        def generate(self, question_input):
            called.append(question_input)
            raise error

    monkeypatch.setattr(
        ai_helper, "guidance_component_factory", lambda: Component(), raising=False
    )

    assert ai_helper.call_qwen_for_guidance_with_question("题目", "D") == {}
    assert len(called) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("content", "forbidden_marker"),
    [
        (
            '{"steps": ['
            '{"question": "第一问", "hint": "提示一", '
            '"key_points": ["POISON"]},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}",
            "POISON",
        ),
        (
            '{"steps": ['
            '{"question": "\u200b", "hint": "提示一"},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}",
            "\u200b",
        ),
        (
            "\ufeff\u200b"
            '{"steps": ['
            '{"question": "第一问", "hint": "提示一"},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            '], "unexpected": "POISON"}'
            "\u2060\u200c",
            "POISON",
        ),
    ],
)
def test_student_start_endpoint_rejects_provider_extra_without_db_pollution(
    monkeypatch,
    content,
    forbidden_marker,
):
    from rest_framework.test import APIClient

    from apps.accounts.models import UserAccount
    from apps.common.ai.components.guidance import GuidanceComponent
    from apps.papers.models import ExamPaper
    from apps.parser.models import ExamQuestion
    from apps.study.models import AIGuidanceSession

    student = UserAccount.objects.create(
        role_type="student",
        mobile="13970000071",
        display_name="Task7学生",
    )
    paper = ExamPaper.objects.create(
        title="Task7试卷",
        subject="数学",
        stage="初中",
        grade="9",
        source_file_path="task7/test.docx",
        status="uploaded",
        uploaded_by=student,
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        question_type="fill_blank",
        subject="数学",
        stem="题目",
        answer="D",
    )
    class Client:
        def complete(self, task_key, **kwargs):
            return AIResult(
                content=content,
                provider="qwen",
                model="qwen3.7-flash",
                latency_ms=1,
                raw_response={
                    "choices": [{"message": {"content": content}}]
                },
            )

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: GuidanceComponent(Client()),
    )
    client = _authenticated_student_client(student)

    response = client.post(
        "/api/v1/student/guidance/sessions",
        {"question_id": str(question.id), "mode_type": "C"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["data"]["mode"] == "B"
    assert response.json()["data"]["downgraded"] is True
    session = AIGuidanceSession.objects.get(
        student_user_id=student,
        question_id=question.id,
    )
    assert session.session_status == "downgraded"
    assert "ai_c_generated" not in session.content_log_json
    assert forbidden_marker not in str(session.content_log_json)


@pytest.mark.django_db
def test_student_reply_endpoint_rejects_cf_hidden_unknown_fence_without_pollution(
    monkeypatch,
):
    import uuid

    from rest_framework.test import APIClient

    from apps.accounts.models import UserAccount
    from apps.common.ai.components.guidance import GuidanceComponent
    from apps.papers.models import ExamPaper
    from apps.parser.models import ExamQuestion
    from apps.study.models import AIGuidanceSession

    student = UserAccount.objects.create(
        role_type="student",
        mobile="13970000073",
        display_name="Task7回复学生",
    )
    paper = ExamPaper.objects.create(
        title="Task7回复试卷",
        subject="数学",
        stage="初中",
        grade="9",
        source_file_path="task7/reply.docx",
        status="uploaded",
        uploaded_by=student,
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="2",
        question_type="fill_blank",
        subject="数学",
        stem="题目",
        answer="D",
        ai_answer_c={
            "questions": [
                {"question": "第一问", "reference_answer": "一"},
                {"question": "第二问", "reference_answer": "二"},
                {"question": "第三问", "reference_answer": "三"},
            ]
        },
    )
    session = AIGuidanceSession.objects.create(
        id=uuid.UUID(int=7),
        student_user_id=student,
        question_id=question.id,
        mode_type="C",
        session_status="running",
        content_log_json={"step_index": 0, "steps": [], "answers": []},
    )
    provider_content = (
        "\ufeff\u200b```python\n"
        '{"evaluation": "POISON"}\n```'
        "\u200c\u2060"
    )

    class Client:
        def complete(self, task_key, **kwargs):
            return AIResult(
                content=provider_content,
                provider="qwen",
                model="qwen3.7-flash",
                latency_ms=1,
                raw_response={
                    "choices": [{"message": {"content": provider_content}}]
                },
            )

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: GuidanceComponent(Client()),
    )
    client = _authenticated_student_client(student)

    response = client.post(
        "/api/v1/student/guidance/sessions/7/reply",
        {"reply": "我认为应该先整理已知条件"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["data"]["evaluation"] == (
        "（AI 评价暂时不可用：AIResponseError）"
    )
    assert "POISON" not in str(response.json())
    session.refresh_from_db()
    assert "POISON" not in str(session.content_log_json)
