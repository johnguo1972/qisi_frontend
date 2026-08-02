from __future__ import annotations

import pytest

from apps.common.ai.config import AIConfig
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.types import AIResult
from apps.common.exceptions import AIRequestError


class RecordingPromptRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def render(self, task_key: str, **variables):
        self.calls.append((task_key, variables))
        return f"system:{task_key}", f"user:{task_key}"


class RecordingAIClient:
    def __init__(self, responses: dict[str, str | BaseException]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None = None,
    ) -> AIResult:
        self.calls.append(
            {
                "task_key": task_key,
                "system": system,
                "user": user,
                "images": tuple(images),
                "trace_id": trace_id,
            }
        )
        response = self.responses[task_key]
        if isinstance(response, BaseException):
            raise response
        return AIResult(
            content=response,
            provider="qwen",
            model="qwen3.7-flash",
            latency_ms=3,
            raw_response={
                "choices": [{"message": {"content": response}}]
            },
        )


def _component(responses):
    from apps.common.ai.components.guidance import GuidanceComponent

    client = RecordingAIClient(responses)
    registry = RecordingPromptRegistry()
    return GuidanceComponent(client, registry), client, registry


def test_generate_routes_through_registry_client_and_parser():
    from apps.common.ai.components.guidance import QuestionInput

    content = (
        '{"steps": ['
        '{"question": "先找什么条件？", "hint": "阅读题干"},'
        '{"question": "可以用什么关系？", "hint": "回忆公式"},'
        '{"question": "怎样验证结果？", "hint": "代回检查"}'
        "]}"
    )
    component, client, registry = _component({"guidance_generate": content})

    result = component.generate(
        QuestionInput(
            stem="题目",
            answer="D",
            metadata={"trace_id": "trace-7"},
        )
    )

    assert result == {
        "steps": [
            {"question": "先找什么条件？", "hint": "阅读题干"},
            {"question": "可以用什么关系？", "hint": "回忆公式"},
            {"question": "怎样验证结果？", "hint": "代回检查"},
        ]
    }
    assert registry.calls == [
        ("guidance_generate", {"stem": "题目", "answer": "D"})
    ]
    assert client.calls == [
        {
            "task_key": "guidance_generate",
            "system": "system:guidance_generate",
            "user": "user:guidance_generate",
            "images": (),
            "trace_id": "trace-7",
        }
    ]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("思路正确，请继续。", "思路正确，请继续。"),
        ('{"evaluation": "思路正确，请继续。"}', "思路正确，请继续。"),
    ],
)
def test_student_evaluation_accepts_legacy_text_and_json(content, expected):
    from apps.common.ai.components.guidance import GuidanceContext

    component, client, registry = _component({"guidance_evaluate": content})

    result = component.evaluate_student_reply(
        GuidanceContext(
            question_text="题目",
            reference_answer="D",
            student_answer="我的思路",
            trace_id="student-trace",
        )
    )

    assert result == expected
    assert registry.calls == [
        (
            "guidance_evaluate",
            {
                "question_text": "题目",
                "reference_answer": "D",
                "student_answer": "我的思路",
            },
        )
    ]
    assert client.calls[0]["task_key"] == "guidance_evaluate"
    assert client.calls[0]["trace_id"] == "student-trace"


@pytest.mark.parametrize(
    "content",
    ["", "   ", '{"evaluation": ""}', '{"evaluation": 7}', "{broken"],
)
def test_student_evaluation_rejects_malformed_or_empty_content(content):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": content})

    with pytest.raises(AIResponseError):
        component.evaluate_student_reply(
            GuidanceContext("题目", "D", "我的思路")
        )


def test_teacher_evaluation_returns_compatibility_object():
    from apps.common.ai.components.guidance import GuidanceContext

    component, client, registry = _component(
        {"teacher_guidance_evaluate": '{"evaluation": "回答基本正确。"}'}
    )

    result = component.evaluate_teacher_reply(
        GuidanceContext("题目", "D", "学生回答", trace_id="teacher-trace")
    )

    assert result == {"evaluation": "回答基本正确。"}
    assert registry.calls[0][0] == "teacher_guidance_evaluate"
    assert client.calls[0]["task_key"] == "teacher_guidance_evaluate"
    assert client.calls[0]["trace_id"] == "teacher-trace"


@pytest.mark.parametrize(
    "error",
    [
        AIRequestError("provider failed"),
        AIRequestError("AI provider request timed out"),
        AIResponseError("malformed response"),
    ],
)
def test_component_propagates_domain_failures_to_compatibility_boundary(error):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": error})

    with pytest.raises(type(error), match=str(error)):
        component.evaluate_student_reply(
            GuidanceContext("题目", "D", "学生回答")
        )


def test_generation_rejects_out_of_contract_step_count():
    from apps.common.ai.components.guidance import GuidanceComponent, QuestionInput

    client = RecordingAIClient(
        {
            "guidance_generate": (
                '{"steps": ['
                '{"question": "第一问", "hint": "提示"},'
                '{"question": "第二问", "hint": "提示"}'
                "]}"
            )
        }
    )

    with pytest.raises(AIResponseError):
        GuidanceComponent(client, RecordingPromptRegistry()).generate(
            QuestionInput(stem="题目")
        )


def test_all_guidance_tasks_are_qwen_flash_with_300_second_timeout():
    config = AIConfig.load()

    for task_key in (
        "guidance_generate",
        "guidance_evaluate",
        "teacher_guidance_evaluate",
    ):
        task = config.get_task_config(task_key)
        assert task.provider == "qwen"
        assert task.model == "qwen3.7-flash"
        assert task.timeout_seconds == 300
