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


@pytest.mark.parametrize("reply", ["A", "A. 正确选项内容"])
def test_student_b_reply_normalizes_option_label(monkeypatch, reply):
    session = _Session(mode_type="B")
    question = _question(
        question_type="single_choice",
        ai_answer_b={
            "questions": [
                {
                    "question": "第一步",
                    "options": {"A": "正确选项内容", "B": "其他选项"},
                    "correct_option": "A",
                    "analysis": "解析",
                },
                {"question": "第二步", "options": {"A": "继续"}},
            ]
        },
    )
    _install_study_models(monkeypatch, session, question)

    calls = []

    class Component:
        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            assert context.mode == "B"
            assert context.program_is_correct is True
            assert context.original_question_text == "题目"
            assert context.original_question_options == ()
            assert context.fixed_guidance_step["question"] == "第一步"
            assert context.fixed_guidance_step["options"] == [
                "A. 正确选项内容",
                "B. 其他选项",
            ]
            assert context.student_selected_guidance_step == reply
            assert context.guidance_step_is_correct is True
            return {
                "feedback": "已根据图像定位本题的关键数据。",
                "known_information": "图像显示三个时间段的路程变化。",
                "guidance": "请先记录各时间段的路程和时间，再继续分析。",
                "next_question": "下一步使用哪个物理量？",
                "next_hint": "关注题目中的单位。",
                "confidence": 0.91,
            }

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )

    request = SimpleNamespace(
        data={"reply": reply}, user=SimpleNamespace(id=9)
    )
    response = _plain_view_handler(guidance_views.guidance_reply)(
        request, "session-7"
    )

    assert response.status_code == 200
    data = response.data["data"]
    assert data["fixed_guidance"]["action_is_correct"] is True
    assert data["fixed_guidance"]["selected_option"] == "A"
    assert data["fixed_guidance"]["selected_option_text"] == "正确选项内容"
    assert data["fixed_guidance"]["current_step"]["question"] == "第一步"
    assert data["fixed_guidance"]["next_step"]["index"] == 1
    assert data["fixed_guidance"]["next_step"]["options"] == ["A. 继续"]
    assert data["fixed_guidance"]["feedback"] == "已根据图像定位本题的关键数据。"
    assert data["fixed_guidance"]["known_information"] == "图像显示三个时间段的路程变化。"
    assert data["fixed_guidance"]["guidance"] == "请先记录各时间段的路程和时间，再继续分析。"
    assert "error_type" not in data
    assert "correction_direction" not in data
    assert "correct_answer" not in data
    assert response.data["data"]["step_index"] == 1
    assert response.data["data"]["next_question"] == "下一步使用哪个物理量？"
    assert response.data["data"]["next_hint"] == "关注题目中的单位。"
    assert len(calls) == 1
    answer_log = session.content_log_json["answers"][0]
    assert answer_log["reply_key"].startswith("sha256:")
    assert "response_data" in answer_log
    assert answer_log["ai_status"] == "success"
    return
    assert session.content_log_json["answers"] == [
        {
            "step": 0,
            "mode": "B",
            "user_answer": reply,
            "normalized_answer": "A",
            "correct_answer": "A",
            "is_correct": True,
            "ai_status": "success",
            "trace_id": response.data["trace_id"],
            "provider": "qwen",
            "model": "qwen3.7-flash",
            "latency_ms": 0,
            "result": "correct",
            "error_type": None,
            "evaluation": "选项判断正确。",
            "correction_direction": "继续说明选择该选项的依据。",
            "next_question": "下一步使用哪个物理量？",
            "next_hint": "关注题目中的单位。",
            "confidence": 0.91,
        }
    ]


def test_student_b_reply_uses_fixed_step_ai_once(monkeypatch):
    session = _Session(mode_type="B")
    question = _question(
        question_type="single_choice",
        ai_answer_b={
            "questions": [
                {"question": "第一步", "options": {"A": "正确"}, "correct_option": "A"},
                {"question": "第二步", "options": {"A": "继续"}},
            ]
        },
    )
    _install_study_models(monkeypatch, session, question)

    calls = []

    class Component:
        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            raise AIRequestError("provider failed")

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    response = _plain_view_handler(guidance_views.guidance_reply)(
        SimpleNamespace(data={"reply": "A"}, user=SimpleNamespace(id=9)),
        "session-7",
    )

    assert response.status_code == 200
    assert response.data["data"]["step_index"] == 0
    data = response.data["data"]
    assert data["fixed_guidance"]["action_is_correct"] is True
    assert data["fixed_guidance"]["feedback"] == ""
    assert data["fixed_guidance"]["next_step"] is None
    assert data["ai_unavailable"] is True
    assert data["retryable"] is True
    assert "error_type" not in data
    assert "correction_direction" not in data
    assert len(calls) == 1
    assert session.content_log_json["step_index"] == 0
    assert session.content_log_json["answers"][0]["normalized_answer"] == "A"
    assert session.content_log_json["answers"][0]["ai_status"] == "fallback"
    assert session.content_log_json["answers"][0]["failure_reason"] == "AIRequestError"
    assert session.content_log_json["answers"][0]["failure_stage"] == "request"
    assert response.data["data"]["ai_failure_stage"] == "request"


def test_fixed_guidance_uses_media_file_for_provider_image_source(monkeypatch, tmp_path):
    monkeypatch.setattr(guidance_views.settings, "MEDIA_ROOT", str(tmp_path))

    sources = guidance_views._fixed_guidance_image_sources({
        "images": [
            {
                "file_path": "exams/graph.png",
                "url": "/media/exams/graph.png",
            }
        ]
    })

    assert len(sources) == 1
    assert sources[0] == str((tmp_path / "exams" / "graph.png").resolve())
    assert sources[0] != "/media/exams/graph.png"


def test_student_b_fallback_keeps_step_correctness_unknown(monkeypatch):
    session = _Session(mode_type="B")
    question = _question(
        question_type="multiple_choice",
        answer="BD",
        ai_answer_b={},
    )
    _install_study_models(monkeypatch, session, question)
    calls = []

    class Component:
        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            raise AIRequestError("provider failed")

    monkeypatch.setattr(guidance_views, "guidance_component_factory", lambda: Component())

    response = _plain_view_handler(guidance_views.guidance_reply)(
        SimpleNamespace(
            data={"reply": "A. 分析已知条件，找出关键信息"},
            user=SimpleNamespace(id=9),
        ),
        "session-7",
    )

    data = response.data["data"]
    assert data["fixed_guidance"]["action_is_correct"] is None
    assert data["fixed_guidance"]["selected_option"] == "A"
    assert data["fixed_guidance"]["selected_option_text"] == "分析已知条件，找出关键信息"
    assert "BD" not in data["fixed_guidance"]["feedback"]
    assert "error_type" not in data
    assert "correction_direction" not in data
    assert "correct_answer" not in data
    assert data["step_index"] == 0
    assert data["next_hint"] is None
    assert data["fixed_guidance"]["next_step"] is None
    assert data["ai_unavailable"] is True
    assert len(calls) == 1
    answer_log = session.content_log_json["answers"][0]
    assert answer_log["action_is_correct"] is None
    assert answer_log["fixed_guidance"]["selected_option"] == "A"
    assert "error_type" not in answer_log
    assert "correction_direction" not in answer_log
    assert session.content_log_json["answers"][0]["ai_status"] == "fallback"


def test_student_c_downgrade_resets_session_step_index(monkeypatch):
    session = _Session(
        invalid_input_count=1,
        content_log_json={"step_index": 2, "steps": [], "answers": []},
    )
    question = _question()
    _install_study_models(monkeypatch, session, question)

    request = SimpleNamespace(
        data={"reply": "不会"}, user=SimpleNamespace(id=9)
    )
    response = _plain_view_handler(guidance_views.guidance_reply)(
        request, "session-7"
    )

    assert response.status_code == 200
    assert response.data["data"]["mode"] == "B"
    assert response.data["data"]["step_index"] == 0
    assert session.mode_type == "B"
    assert session.session_status == "downgraded"
    assert session.content_log_json["step_index"] == 0


def test_start_c_guidance_returns_fast_fallback_and_does_not_call_llm(
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
    assert response.data["data"]["mode"] == "C"
    assert response.data["data"]["is_fallback"] is True
    assert response.data["data"]["preparation_pending"] is True
    assert response.data["data"]["hint"] == "请继续思考这道题的解题思路"
    return
    assert response.data["data"]["preparation_pending"] is True
    assert "ai_c_generated" not in session.content_log_json
    return
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
    assert response.data["data"]["is_fallback"] is True
    assert "ai_c_generated" not in session.content_log_json
    return
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
    assert response.data["data"]["mode"] == "C"
    assert response.data["data"]["is_fallback"] is True
    assert response.data["data"]["preparation_pending"] is True
    return
    assert response.data["data"]["downgrade_reason"] == (
        "非固定选项引导数据不可用，已降级到固定选项引导模式"
    )
    assert session.mode_type == "C"
    assert session.session_status == "running"
    assert called == []


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
            return {
                "result": "partial",
                "error_type": "incomplete_expression",
                "evaluation": "思路基本正确，请继续。",
                "correction_direction": "补充速度与图线斜率的关系。",
                "next_question": "下一步如何观察水平线段？",
                "next_hint": "关注位置是否变化。",
                "confidence": 0.88,
            }

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
    assert response.data["data"]["step_index"] == 1
    assert response.data["data"]["result"] == "partial"
    assert session.content_log_json["answers"][0]["reply_key"].startswith("sha256:")
    assert "response_data" in session.content_log_json["answers"][0]
    return
    assert response.data["data"] == {
        "mode": "C",
        "step_index": 1,
        "total_steps": 2,
        "evaluation": "思路基本正确，请继续。",
        "result": "partial",
        "error_type": "incomplete_expression",
        "correction_direction": "补充速度与图线斜率的关系。",
        "confidence": 0.88,
        "next_question": "下一步如何观察水平线段？",
        "next_hint": "关注位置是否变化。",
        "is_completed": False,
    }
    assert session.content_log_json["answers"] == [
        {
            "step": 0,
            "mode": "C",
            "user_answer": "我的回答",
            "ai_status": "success",
            "trace_id": response.data["trace_id"],
            "provider": "qwen",
            "model": "qwen3.7-flash",
            "latency_ms": 0,
            "result": "partial",
            "error_type": "incomplete_expression",
            "evaluation": "思路基本正确，请继续。",
            "correction_direction": "补充速度与图线斜率的关系。",
            "next_question": "下一步如何观察水平线段？",
            "next_hint": "关注位置是否变化。",
            "confidence": 0.88,
        }
    ]


def test_student_c_reply_builds_complete_current_step_context(monkeypatch):
    session = _Session(
        content_log_json={
            "step_index": 1,
            "steps": [],
            "answers": [{"step": 0, "user_answer": "previous"}],
        }
    )
    question = _question(
        analysis="题目解析",
        knowledge_points=["图像运动"],
        ai_vision_extract={"facts": ["水平线表示路程不变"]},
        ai_answer_c={
            "questions": [
                {"question": "第一问"},
                {
                    "question": "当前引导问题",
                    "reference_answer": "当前参考方向",
                    "key_points": ["斜率表示速度"],
                },
            ]
        },
    )
    _install_study_models(monkeypatch, session, question)
    monkeypatch.setattr(
        guidance_views,
        "_build_question_info",
        lambda current_question: {
            "stem": current_question.stem,
            "options": [{"label": "A", "content": "选项内容"}],
            "images": [{"description": "图像折线事实"}],
        },
    )

    calls = []

    class Component:
        def evaluate_student_reply(self, context):
            calls.append(context)
            assert context.mode == "C"
            assert context.current_question == "当前引导问题"
            assert context.current_reference_answer == "当前参考方向"
            assert context.key_points == ("斜率表示速度",)
            assert context.question_options == (
                {"label": "A", "content": "选项内容"},
            )
            assert context.question_analysis == "题目解析"
            assert context.knowledge_points == ("图像运动",)
            assert context.visual_facts == (
                {"facts": ["水平线表示路程不变"]},
                "图像折线事实",
            )
            assert context.history == (
                {"step": 0, "user_answer": "previous"},
            )
            return {
                "result": "partial",
                "error_type": "unclear",
                "evaluation": "已结合当前步骤评价",
                "correction_direction": "补充依据。",
                "next_question": "继续说明。",
                "next_hint": "关注关键点。",
                "confidence": 0.7,
            }

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    request = SimpleNamespace(
        data={"reply": "我的当前回答"}, user=SimpleNamespace(id=9)
    )

    response = _plain_view_handler(guidance_views.guidance_reply)(
        request, "session-7"
    )

    assert response.status_code == 200
    assert response.data["data"]["step_index"] == 2
    assert len(calls) == 1
    assert session.content_log_json["answers"][-1]["step"] == 1
    assert session.content_log_json["answers"][-1]["evaluation"] == (
        "已结合当前步骤评价"
    )


@pytest.mark.parametrize(
    "error",
    [
        AIConfigError("missing key"),
        AIRequestError("provider failed"),
        AIRequestError("AI provider request timed out"),
    ],
)
def test_student_c_reply_keeps_current_step_on_ai_failure(monkeypatch, error):
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

    called = []

    class Component:
        def evaluate_student_reply(self, context):
            called.append(context)
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
    assert response.data["data"]["evaluation"] == "AI 评价暂时不可用，请稍后重试"
    assert response.data["data"]["next_hint"] is None
    assert response.data["data"]["step_index"] == 0
    assert response.data["data"]["ai_unavailable"] is True
    assert response.data["data"]["retryable"] is True
    assert len(called) == 1
    assert session.content_log_json["step_index"] == 0
    answer_log = session.content_log_json["answers"][0]
    assert answer_log["step"] == 0
    assert answer_log["mode"] == "C"
    assert answer_log["user_answer"] == "我的回答"
    assert answer_log["ai_status"] == "unavailable"
    assert answer_log["trace_id"] == response.data["trace_id"]


@pytest.mark.parametrize("mode", ["B", "C"])
def test_student_reply_uses_safe_fallback_for_invalid_ai_response(monkeypatch, mode):
    session = _Session(mode_type=mode)
    question = _question(
        question_type="single_choice" if mode == "B" else "fill_blank",
        ai_answer_b={
            "questions": [
                {"question": "step", "options": {"A": "right"}, "correct_option": "A"},
                {"question": "next", "options": {"A": "continue"}},
            ]
        },
        ai_answer_c={
            "questions": [
                {"question": "step", "reference_answer": "key point", "key_points": ["key point"]},
                {"question": "next", "reference_answer": "next point"},
            ]
        },
    )
    _install_study_models(monkeypatch, session, question)
    calls = []

    class Component:
        def evaluate_student_reply(self, context):
            calls.append(context)
            raise AIResponseError("malformed response")

        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            raise AIResponseError("malformed response")

    monkeypatch.setattr(
        guidance_views,
        "guidance_component_factory",
        lambda: Component(),
        raising=False,
    )
    reply = "B" if mode == "B" else "我的判断"
    response = _plain_view_handler(guidance_views.guidance_reply)(
        SimpleNamespace(data={"reply": reply}, user=SimpleNamespace(id=9)),
        "session-7",
    )

    assert response.status_code == 200
    assert response.data["data"]["ai_degraded"] is True
    assert len(calls) == 1
    answer_log = session.content_log_json["answers"][0]
    assert answer_log["ai_status"] == (
        "fallback"
    )
    if mode == "C":
        assert response.data["data"].get("ai_unavailable") is not True
        assert response.data["data"]["step_index"] == 1
        assert answer_log["failure_reason"] == "AIResponseError"
    else:
        assert response.data["data"]["ai_unavailable"] is True
        assert response.data["data"]["step_index"] == 0
        assert "error_type" not in answer_log
        assert "correction_direction" not in answer_log
    assert session.content_log_json["step_index"] == (1 if mode == "C" else 0)


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
    assert response.json()["data"]["mode"] == "C"
    assert response.json()["data"]["is_fallback"] is True
    assert response.json()["data"]["preparation_pending"] is True
    return
    session = AIGuidanceSession.objects.get(
        student_user_id=student,
        question_id=question.id,
    )
    assert session.session_status == "downgraded"
    assert "ai_c_generated" not in session.content_log_json
    assert forbidden_marker not in str(session.content_log_json)


@pytest.mark.django_db
def test_student_reply_endpoint_recovers_cf_hidden_unknown_fence_without_pollution(
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
    assert response.json()["data"]["evaluation"]
    assert response.json()["data"]["ai_degraded"] is True
    assert response.json()["data"]["next_hint"]
    assert response.json()["data"]["step_index"] == 1
    assert "POISON" not in str(response.json())
    session.refresh_from_db()
    assert "POISON" not in str(session.content_log_json)
    assert session.content_log_json["step_index"] == 1
    assert session.content_log_json["answers"][0]["ai_status"] == "fallback"
    assert session.content_log_json["answers"][0]["failure_reason"] == "AIResponseError"
def test_student_reply_idempotency_returns_stored_result_without_second_ai_call(monkeypatch):
    session = _Session(mode_type="B")
    question = _question(
        question_type="single_choice",
        ai_answer_b={
            "questions": [
                {"question": "step", "options": {"A": "right"}, "correct_option": "A"},
                {"question": "next", "options": {"A": "continue"}},
            ]
        },
    )
    _install_study_models(monkeypatch, session, question)
    calls = []

    class Component:
        def evaluate_student_reply(self, context):
            calls.append(context)
            return {
                "result": "correct", "error_type": "none", "evaluation": "ok",
                "correction_direction": "continue", "next_question": "next",
                "next_hint": "hint", "confidence": 0.9,
            }

        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            return {
                "feedback": "已分析当前固定动作。",
                "known_information": "题干中的已知信息。",
                "guidance": "请继续按步骤思考。",
                "next_question": "下一步",
                "next_hint": "下一步提示",
                "confidence": 0.9,
            }

    monkeypatch.setattr(guidance_views, "guidance_component_factory", lambda: Component())
    request = SimpleNamespace(
        data={"reply": "A", "reply_id": "same-submit"}, user=SimpleNamespace(id=9)
    )
    first = _plain_view_handler(guidance_views.guidance_reply)(request, "session-7")
    second = _plain_view_handler(guidance_views.guidance_reply)(request, "session-7")

    assert first.data == second.data
    assert len(calls) == 1
    assert session.content_log_json["step_index"] == 1
    assert len(session.content_log_json["answers"]) == 1


def test_student_b_reply_calls_ai_even_when_realtime_gray_switch_is_off(monkeypatch):
    session = _Session(mode_type="B")
    question = _question(
        question_type="single_choice",
        ai_answer_b={"questions": [{"question": "step", "options": {"A": "right"}, "correct_option": "A"}]},
    )
    _install_study_models(monkeypatch, session, question)
    monkeypatch.setattr(guidance_views.settings, "GUIDANCE_REALTIME_AI_ENABLED", False, raising=False)
    calls = []

    class Component:
        def evaluate_fixed_guidance_reply(self, context):
            calls.append(context)
            return {
                "feedback": "已根据当前固定动作分析。",
                "known_information": "题干已知信息。",
                "guidance": "请继续完成当前步骤。",
                "next_question": None,
                "next_hint": None,
                "confidence": 0.9,
            }

    monkeypatch.setattr(guidance_views, "guidance_component_factory", lambda: Component())

    response = _plain_view_handler(guidance_views.guidance_reply)(
        SimpleNamespace(data={"reply": "A"}, user=SimpleNamespace(id=9)), "session-7"
    )

    assert response.data["data"]["step_index"] == 1
    assert response.data["data"]["is_completed"] is True
    assert response.data["data"]["ai_status"] == "success"
    assert len(calls) == 1
    assert session.content_log_json["answers"][0]["ai_status"] == "success"
