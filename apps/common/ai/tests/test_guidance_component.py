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


def test_student_evaluation_renders_runtime_context_without_changing_task_contract():
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, registry = _component(
        {
            "guidance_evaluate": (
                '{"result":"unclear","error_type":"unclear",'
                '"evaluation":"ok","correction_direction":"add evidence",'
                '"next_question":null,"next_hint":null,"confidence":0.2}'
            )
        }
    )

    component.evaluate_student_reply(
        GuidanceContext(
            question_text="stem",
            reference_answer="final answer",
            student_answer="student reply",
            trace_id="trace-runtime",
            mode="C",
            current_question="current step",
            current_reference_answer="current direction",
            key_points=("key point",),
            question_options=({"label": "A", "content": "option"},),
            question_analysis="analysis",
            knowledge_points=("concept",),
            visual_facts=("line is horizontal",),
            history=({"step": 0, "user_answer": "previous"},),
        )
    )

    variables = registry.calls[0][1]
    assert variables["reference_answer"] == "current direction"
    assert variables["student_answer"] == "student reply"
    assert "stem" in variables["question_text"]
    assert "current step" in variables["question_text"]
    assert "key point" in variables["question_text"]
    assert "analysis" in variables["question_text"]
    assert "line is horizontal" in variables["question_text"]
    assert "previous" in variables["question_text"]


def test_student_guidance_context_separates_original_options_from_fixed_step():
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, registry = _component(
        {
            "guidance_evaluate": (
                '{"result":"unclear","error_type":"unclear",'
                '"evaluation":"请继续说明。",'
                '"correction_direction":"补充依据。",'
                '"next_question":null,"next_hint":null,"confidence":0.2}'
            )
        }
    )

    component.evaluate_student_reply(
        GuidanceContext(
            question_text="某物体的运动情况如图，错误的是（ ）",
            reference_answer="BD",
            student_answer="B. 思考适用的公式或定理",
            mode="B",
            current_reference_answer="",
            question_options=(
                "A. 分析已知条件，找出关键信息",
                "B. 思考适用的公式或定理",
            ),
            original_question_text="某物体的运动情况如图，错误的是（ ）",
            original_question_options=(
                {"label": "A", "content": "路程为18m"},
                {"label": "B", "content": "前后速度相等"},
            ),
            fixed_guidance_step={
                "question": "请先分析题目条件",
                "options": [
                    "A. 分析已知条件，找出关键信息",
                    "B. 思考适用的公式或定理",
                ],
            },
            student_selected_guidance_step="B. 思考适用的公式或定理",
            guidance_step_is_correct=None,
        )
    )

    variables = registry.calls[0][1]
    context_text = variables["question_text"]
    assert "【原题内容】" in context_text
    assert "【原题答案选项】" in context_text
    assert "路程为18m" in context_text
    assert "【固定引导步骤】" in context_text
    assert "思考适用的公式或定理" in context_text
    assert "【学生选择的引导步骤】" in context_text
    assert "【引导步骤是否正确】" not in context_text
    assert variables["reference_answer"] == "当前引导步骤暂无预设参考答案"
    assert variables["student_answer"] == "B. 思考适用的公式或定理"


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


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "\ufeff\u200b{\"evaluation\": \"直接 JSON\"}\u200c\u2060",
            "直接 JSON",
        ),
        (
            "\u200d\u2060```JSON\n"
            '{"evaluation": "围栏 JSON"}\n```'
            "\ufeff\u200b",
            "围栏 JSON",
        ),
        (
            "\u200b\ufeff \t正文\u200c内容 \u2060\u200d",
            "正文\u200c内容",
        ),
    ],
)
def test_evaluation_strips_visual_boundaries_before_classification(
    content,
    expected,
):
    from apps.common.ai.components.guidance import GuidanceContext

    component, _, _ = _component({"guidance_evaluate": content})

    assert component.evaluate_student_reply(
        GuidanceContext("题目", "D", "我的思路")
    ) == expected


@pytest.mark.parametrize(
    "content",
    [
        "\ufeff\u200b```python\n"
        '{"evaluation": "POISON"}\n```'
        "\u200c\u2060",
        "\u200b```json\n{\"evaluation\": \"POISON\"\n```\ufeff",
        "\u200d{\"evaluation\": \"POISON\", \"extra\": true}\u2060",
        "\ufeff{\"evaluation\": \"POISON\"} trailing\u200b",
        "\u200b{broken\u200c",
    ],
)
def test_evaluation_visual_boundaries_cannot_hide_malformed_structures(content):
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


def test_guidance_tasks_use_flash_and_realtime_evaluation_is_bounded():
    config = AIConfig.load()

    for task_key in (
        "guidance_generate",
        "guidance_evaluate",
        "guidance_fixed_evaluate",
        "teacher_guidance_evaluate",
    ):
        task = config.get_task_config(task_key)
        assert task.provider == "qwen"
        assert task.model == "qwen3.7-flash"
        if task_key in ("guidance_evaluate", "guidance_fixed_evaluate"):
            assert task.timeout_seconds == 10
            assert task.max_tokens in (1024, 1200)
            assert task.retry_count == 0
            assert task.provider_lease_wait_seconds == 3
        else:
            assert task.timeout_seconds == 300


def test_fixed_guidance_evaluation_uses_dedicated_schema_and_images():
    content = (
        '{"feedback":"先读取图像数据。",'
        '"known_information":"图线经过(3s,12m)。",'
        '"guidance":"请按时间段记录路程变化。",'
        '"next_question":"再观察下一段图线。",'
        '"next_hint":"关注横坐标时间变化。",'
        '"confidence":0.92}'
    )
    component, client, registry = _component(
        {"guidance_fixed_evaluate": content}
    )

    from apps.common.ai.components.guidance import GuidanceContext

    result = component.evaluate_fixed_guidance_reply(
        GuidanceContext(
            question_text="原题",
            student_answer="A. 分析已知条件",
            mode="B",
            student_selected_guidance_step="A. 分析已知条件",
            image_urls=("https://example.test/graph.png",),
        )
    )

    assert result["known_information"] == "图线经过(3s,12m)。"
    assert result["guidance"] == "请按时间段记录路程变化。"
    assert registry.calls[0][0] == "guidance_fixed_evaluate"
    assert client.calls[0]["task_key"] == "guidance_fixed_evaluate"
    assert client.calls[0]["images"] == ("https://example.test/graph.png",)


def test_fixed_guidance_evaluation_allows_omitted_optional_followups():
    component, client, _ = _component({
        "guidance_fixed_evaluate": (
            '{"feedback":"先读取图像信息",'
            '"known_information":["图线经过(3s,12m)。","3-6s保持不变。"],'
            '"guidance":"先记录各时间段的路程变化。",'
            '"confidence":0.8}'
        )
    })

    from apps.common.ai.components.guidance import GuidanceContext

    result = component.evaluate_fixed_guidance_reply(
        GuidanceContext(
            question_text="题目",
            mode="B",
            student_selected_guidance_step="A. 分析已知条件",
        )
    )

    assert result["known_information"] == "图线经过(3s,12m)。；3-6s保持不变。"
    assert result["next_question"] is None
    assert result["next_hint"] is None
    assert len(client.calls) == 1


def test_student_evaluation_parses_structured_runtime_analysis():
    from apps.common.ai.components.guidance import GuidanceComponent, GuidanceContext

    content = (
        '{"result":"partial","error_type":"concept_error",'
        '"evaluation":"方向基本正确，但把斜率和路程混淆了。",'
        '"correction_direction":"先明确纵坐标与横坐标的物理意义，再判断斜率。",'
        '"next_question":"图线斜率等于哪个物理量？",'
        '"next_hint":"关注单位和坐标轴。","confidence":0.86}'
    )
    component, client, _ = _component({"guidance_evaluate": content})

    result = component.evaluate_student_reply(
        GuidanceContext(
            question_text="stem",
            reference_answer="current answer",
            student_answer="student reply",
            mode="C",
        )
    )

    assert result == {
        "result": "partial",
        "error_type": "concept_error",
        "evaluation": "方向基本正确，但把斜率和路程混淆了。",
        "correction_direction": "先明确纵坐标与横坐标的物理意义，再判断斜率。",
        "next_question": "图线斜率等于哪个物理量？",
        "next_hint": "关注单位和坐标轴。",
        "confidence": 0.86,
    }
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    "content",
    [
        '{"result":"incorrect","error_type":"concept_error",'
        '"evaluation":"bad"}',
        '{"result":"wrong","error_type":"unclear",'
        '"evaluation":"bad","correction_direction":"fix",'
        '"next_question":null,"next_hint":null,"confidence":0.5}',
        '{"result":"incorrect","error_type":"concept_error",'
        '"evaluation":"bad","correction_direction":"fix",'
        '"next_question":null,"next_hint":null,"confidence":0.5,'
        '"unexpected":"poison"}',
    ],
)
def test_student_evaluation_rejects_invalid_structured_runtime_analysis(content):
    from apps.common.ai.components.guidance import GuidanceComponent, GuidanceContext

    component = GuidanceComponent(
        RecordingAIClient({"guidance_evaluate": content}),
        RecordingPromptRegistry(),
    )

    with pytest.raises(AIResponseError):
        component.evaluate_student_reply(
            GuidanceContext("stem", "answer", "reply", mode="C")
        )
