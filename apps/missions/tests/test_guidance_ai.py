from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError
from apps.missions import views


def _plain_view_handler(decorated_view):
    return decorated_view.cls.post.__closure__[0].cell_contents


def _install_question(monkeypatch):
    question = SimpleNamespace(stem="题目", answer="D", ai_answer_c={})

    class QuestionModel:
        class DoesNotExist(Exception):
            pass

        objects = SimpleNamespace(get=lambda **kwargs: question)

    monkeypatch.setattr(views, "ExamQuestion", QuestionModel)
    return question


def _install_session(monkeypatch, session_id="teacher-session"):
    session = {
        "question_id": 8,
        "mode": "C",
        "turn": 0,
        "messages": [],
        "ai_c": {
            "steps": [
                {"question": "第一问"},
                {"question": "第二问"},
            ]
        },
    }
    monkeypatch.setitem(views._teacher_guidance_sessions, session_id, session)
    return session


def test_teacher_c_reply_uses_component_and_keeps_response_contract(monkeypatch):
    _install_question(monkeypatch)
    session = _install_session(monkeypatch)

    class Component:
        def evaluate_teacher_reply(self, context):
            assert context.question_text == "题目"
            assert context.reference_answer == "D"
            assert context.student_answer == "学生回答"
            return {"evaluation": "回答基本正确。"}

    monkeypatch.setattr(
        views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    monkeypatch.setattr(
        views,
        "_call_qwen",
        lambda *args, **kwargs: pytest.fail("legacy Qwen helper was called"),
        raising=False,
    )
    request = SimpleNamespace(data={"user_answer": "学生回答"})

    response = _plain_view_handler(views.teacher_guidance_reply)(
        request, "teacher-session"
    )

    assert response.status_code == 200
    assert response.data["code"] == 0
    assert response.data["message"] == "success"
    assert response.data["data"] == {
        "evaluation": "回答基本正确。",
        "next_question": "第二问",
        "is_completed": False,
        "mode": "C",
        "turn": 1,
    }
    assert session["messages"] == [
        {"role": "user", "content": "学生回答"},
        {"role": "system", "content": "评价：回答基本正确。\n\n第二问"},
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            AIConfigError("missing key"),
            "（AI评价功能暂不可用，请配置QWEN_API_KEY）",
        ),
        (
            AIRequestError("provider failed"),
            "（AI评价调用失败：provider failed）",
        ),
        (
            AIRequestError("AI provider request timed out"),
            "（AI评价调用失败：AI provider request timed out）",
        ),
        (
            AIResponseError("malformed response"),
            "（AI评价调用失败：AIResponseError）",
        ),
    ],
)
def test_teacher_c_reply_keeps_existing_failure_wording(
    monkeypatch, error, expected
):
    _install_question(monkeypatch)
    _install_session(monkeypatch)

    class Component:
        def evaluate_teacher_reply(self, context):
            raise error

    monkeypatch.setattr(
        views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    monkeypatch.setattr(
        views,
        "_call_qwen",
        lambda *args, **kwargs: pytest.fail("legacy Qwen helper was called"),
        raising=False,
    )
    request = SimpleNamespace(data={"user_answer": "学生回答"})

    response = _plain_view_handler(views.teacher_guidance_reply)(
        request, "teacher-session"
    )

    assert response.status_code == 200
    assert response.data["data"]["evaluation"] == expected
    assert response.data["data"]["next_question"] == "第二问"
    assert response.data["data"]["is_completed"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("provider_content", "forbidden_marker"),
    [
        ('```JSON\n{"evaluation": "POISON"\n```', "POISON"),
        ('```python\n{"evaluation": "POISON"}\n```', "POISON"),
        ('{"evaluation": "\u200b"}', "\u200b"),
        (
            "\ufeff\u200b```python\n"
            '{"evaluation": "POISON"}\n```'
            "\u200c\u2060",
            "POISON",
        ),
        (
            "\u200d"
            '{"evaluation": "POISON", "unexpected": true}'
            "\ufeff",
            "POISON",
        ),
    ],
)
def test_teacher_reply_endpoint_does_not_store_malformed_provider_content(
    monkeypatch,
    provider_content,
    forbidden_marker,
):
    from rest_framework.test import APIClient

    from apps.accounts.models import UserAccount
    from apps.common.ai.components.guidance import GuidanceComponent
    from apps.papers.models import ExamPaper
    from apps.parser.models import ExamQuestion

    teacher = UserAccount.objects.create(
        role_type="teacher",
        mobile="13970000072",
        display_name="Task7教师",
    )
    paper = ExamPaper.objects.create(
        title="Task7教师试卷",
        subject="数学",
        stage="初中",
        grade="9",
        source_file_path="task7/teacher.docx",
        status="uploaded",
        uploaded_by=teacher,
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
                content=provider_content,
                provider="qwen",
                model="qwen3.7-flash",
                latency_ms=1,
                raw_response={
                    "choices": [{"message": {"content": provider_content}}]
                },
            )

    monkeypatch.setattr(
        views,
        "guidance_component_factory",
        lambda: GuidanceComponent(Client()),
    )
    session_id = "teacher-endpoint-task7"
    session = {
        "question_id": question.id,
        "mode": "C",
        "turn": 0,
        "messages": [],
        "ai_c": {
            "steps": [
                {"question": "第一问"},
                {"question": "第二问"},
            ]
        },
    }
    monkeypatch.setitem(views._teacher_guidance_sessions, session_id, session)
    client = APIClient()
    client.force_authenticate(user=teacher)

    response = client.post(
        f"/api/v1/missions/guidance/reply/{session_id}/",
        {"user_answer": "学生回答"},
        format="json",
    )

    assert response.status_code == 200
    evaluation = response.json()["data"]["evaluation"]
    assert evaluation == "（AI评价调用失败：AIResponseError）"
    assert forbidden_marker not in evaluation
    assert forbidden_marker not in str(session["messages"])
