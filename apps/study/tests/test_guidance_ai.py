from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError
from apps.study import ai_helper, guidance_views


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
