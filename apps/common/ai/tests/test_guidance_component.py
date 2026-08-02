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
    [
        '```json\n{"evaluation": "围栏评价"}\n```',
        '\n```JSON\r\n{"evaluation": "围栏评价"}\r\n```\t',
        '```\n{"evaluation": "围栏评价"}\n```',
    ],
)
def test_student_evaluation_parses_complete_json_fences(content):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": content})

    assert component.evaluate_student_reply(
        GuidanceContext("题目", "D", "我的思路")
    ) == "围栏评价"


@pytest.mark.parametrize(
    "content",
    [
        "先比较 {x} 与 y，再继续计算。",
        "{x}",
        "[提示]",
        "{broken}",
    ],
)
def test_student_evaluation_keeps_plain_text_with_non_json_markers(content):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": content})

    assert component.evaluate_student_reply(
        GuidanceContext("题目", "D", "我的思路")
    ) == content


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   ",
        '{"evaluation": ""}',
        '{"evaluation": 7}',
        '{"other": "ok"}',
        '{"evaluation": "ok", "unexpected": "poison"}',
        "[]",
        "{broken",
        '```json\n{"evaluation":\n```',
        '```JSON\n[]\n```',
        '```json\n{"evaluation": "ok", "unexpected": true}\n```',
        '```python\n{"evaluation": "POISON"}\n```',
        '```javascript\n{"evaluation": "POISON"}\n```',
        '```text\n{"evaluation": "POISON"}\n```',
        '```json\n{"evaluation": "POISON"}',
        '```json\n{"evaluation": "POISON"}\n``` trailing',
        '```json\n{"evaluation": "POISON"} trailing\n```',
        '{"evaluation": "POISON"} trailing',
        '[] trailing',
        '[提示',
    ],
)
def test_student_evaluation_rejects_malformed_or_empty_content(content):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": content})

    with pytest.raises(AIResponseError):
        component.evaluate_student_reply(
            GuidanceContext("题目", "D", "我的思路")
        )


@pytest.mark.parametrize(
    "blank",
    [
        "\u2003",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        " \t\u200b\u200c\u200d\u2060\ufeff\u2003 ",
    ],
)
def test_evaluation_rejects_visually_blank_plain_and_json_values(blank):
    from apps.common.ai.components.guidance import GuidanceContext

    context = GuidanceContext("题目", "D", "我的思路")
    for content in (blank, '{"evaluation": "' + blank + '"}'):
        component, _, _ = _component({"guidance_evaluate": content})
        with pytest.raises(AIResponseError):
            component.evaluate_student_reply(context)


def test_evaluation_preserves_nonempty_text_with_internal_format_character():
    from apps.common.ai.components.guidance import GuidanceContext

    content = '{"evaluation": "正确\u200b，请继续。"}'
    component, _, _ = _component({"guidance_evaluate": content})

    assert component.evaluate_student_reply(
        GuidanceContext("题目", "D", "我的思路")
    ) == "正确\u200b，请继续。"


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


@pytest.mark.parametrize(
    "content",
    [
        (
            '{"steps": ['
            '{"question": "第一问", "hint": "提示一"},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            '], "unexpected": "poison"}'
        ),
        (
            '{"steps": ['
            '{"question": "第一问", "hint": "提示一", '
            '"key_points": ["poison"]},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
        (
            '{"steps": ['
            '{"question": "第一问", "hint": "提示一", '
            '"unexpected": true},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
        (
            '{"steps": ['
            '{"question": "第一问"},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
        (
            '{"steps": ['
            '{"question": "第一问", "hint": ""},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
        (
            '{"steps": ['
            '{"question": " ", "hint": "提示一"},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
        (
            '{"steps": ['
            '{"question": "第一问", "hint": 7},'
            '{"question": "第二问", "hint": "提示二"},'
            '{"question": "第三问", "hint": "提示三"}'
            "]}"
        ),
    ],
)
def test_generation_rejects_fields_not_declared_by_frozen_prompt(content):
    from apps.common.ai.components.guidance import GuidanceComponent, QuestionInput

    client = RecordingAIClient({"guidance_generate": content})

    with pytest.raises(AIResponseError):
        GuidanceComponent(client, RecordingPromptRegistry()).generate(
            QuestionInput(stem="题目")
        )


def test_generation_accepts_five_complete_declared_steps():
    from apps.common.ai.components.guidance import GuidanceComponent, QuestionInput

    content = (
        '{"steps": ['
        '{"question": "第一问", "hint": "提示一"},'
        '{"question": "第二问", "hint": "提示二"},'
        '{"question": "第三问", "hint": "提示三"},'
        '{"question": "第四问", "hint": "提示四"},'
        '{"question": "第五问", "hint": "提示五"}'
        "]}"
    )
    component = GuidanceComponent(
        RecordingAIClient({"guidance_generate": content}),
        RecordingPromptRegistry(),
    )

    assert len(component.generate(QuestionInput(stem="题目"))["steps"]) == 5


@pytest.mark.parametrize("field", ["question", "hint"])
@pytest.mark.parametrize(
    "blank",
    [
        "\u2003",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
        " \t\u200b\u2060\ufeff\u2003 ",
    ],
)
def test_generation_rejects_visually_blank_question_and_hint(field, blank):
    import json

    from apps.common.ai.components.guidance import GuidanceComponent, QuestionInput

    first = {"question": "第一问", "hint": "提示一"}
    first[field] = blank
    content = (
        '{"steps": ['
        + json.dumps(first, ensure_ascii=False)
        + ',{"question": "第二问", "hint": "提示二"},'
        + '{"question": "第三问", "hint": "提示三"}'
        + "]}"
    )

    with pytest.raises(AIResponseError):
        GuidanceComponent(
            RecordingAIClient({"guidance_generate": content}),
            RecordingPromptRegistry(),
        ).generate(QuestionInput(stem="题目"))


def test_generation_preserves_nonempty_fields_with_internal_format_character():
    from apps.common.ai.components.guidance import GuidanceComponent, QuestionInput

    content = (
        '{"steps": ['
        '{"question": "第一\u200b问", "hint": "提示\u2060一"},'
        '{"question": "第二问", "hint": "提示二"},'
        '{"question": "第三问", "hint": "提示三"}'
        "]}"
    )
    component = GuidanceComponent(
        RecordingAIClient({"guidance_generate": content}),
        RecordingPromptRegistry(),
    )

    first = component.generate(QuestionInput(stem="题目"))["steps"][0]
    assert first == {"question": "第一\u200b问", "hint": "提示\u2060一"}


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
