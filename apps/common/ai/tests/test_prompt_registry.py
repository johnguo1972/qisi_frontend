from __future__ import annotations

from pathlib import Path

import pytest

from apps.common.ai.config import AIConfig
from apps.common.ai.exceptions import AIConfigError, AIPromptError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai_prompts import AIPrompts


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv(
        "QWEN_API_URL", "https://example.test/qwen/chat/completions"
    )


def write_prompt_cfg(
    tmp_path: Path,
    *,
    system: str = "只输出 JSON。",
    user: str = "题干：{stem}\n图形事实：{figure_facts}",
    variables: str = "stem, figure_facts",
) -> Path:
    indented_system = system.replace("\n", "\n  ")
    indented_user = user.replace("\n", "\n  ")
    cfg = tmp_path / "ai_config.cfg"
    cfg.write_text(
        f"""[provider:qwen]
api_url_env = QWEN_API_URL
api_key_env = QWEN_API_KEY

[task:mode_a_answer]
provider = qwen
model = qwen3.7-flash
prompt = mode_a_answer
temperature = 0.2
max_tokens = 4096
timeout_seconds = 300
retry_count = 3
retry_backoff_seconds = 1, 2, 4
response_format = json

[prompt:mode_a_answer]
system = {indented_system}
user = {indented_user}
variables = {variables}
""",
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def registry(tmp_path, provider_env):
    return PromptRegistry(AIConfig.load(write_prompt_cfg(tmp_path)))


def test_prompt_registry_rejects_missing_variable(registry):
    with pytest.raises(AIPromptError, match="stem"):
        registry.render("mode_a_answer", figure_facts="{}")


def test_prompt_registry_rejects_unknown_variable(registry):
    with pytest.raises(AIPromptError, match="extra"):
        registry.render(
            "mode_a_answer", stem="求 x", figure_facts="{}", extra="secret"
        )


def test_prompt_registry_renders_system_and_user_without_placeholders(registry):
    system, user = registry.render(
        "mode_a_answer", stem="求 x", figure_facts={"AB": "AC"}
    )

    assert system == "只输出 JSON。"
    assert user == "题干：求 x\n图形事实：{'AB': 'AC'}"
    assert "{stem}" not in user
    assert "{figure_facts}" not in user


def test_config_rejects_declared_variables_that_do_not_match_templates(
    tmp_path, provider_env
):
    cfg = write_prompt_cfg(tmp_path, variables="stem, unrelated")

    with pytest.raises(AIConfigError, match="variables"):
        AIConfig.load(cfg)


def test_default_registry_preserves_prompt_constraints(provider_env):
    registry = PromptRegistry(AIConfig.load())

    system, user = registry.render(
        "mode_b_answer",
        normalized_text="已知 x=1，求 x+1",
        vision_json="{}",
        knowledge_refs="一元一次方程",
    )
    assert "questions 数量只能是 3 或 4" in system
    assert "correct_option、reference_answer、analysis" in system
    assert "final_answer, summary" in system
    assert "已知 x=1，求 x+1" in user

    system, user = registry.render(
        "vision_question_parse",
        question_no="7",
        question_type="single_choice",
        question_type_label="单选题",
        section_title="一、选择题",
        page_start=1,
        page_end=2,
        multi_page_notice="请综合两页内容。",
    )
    assert "## 输出格式要求" in system
    assert "question_no" in system
    assert "images" in system
    assert "第 7 题" in user
    assert "请综合两页内容。" in user

    _, user = registry.render(
        "variant_generate",
        question_context="## 原题信息\n题干：求 x",
        variant_mode="数值变化",
        question_type="single_choice",
    )
    assert "## 原题信息" in user
    assert "## 变式要求" in user


def test_default_registry_renders_every_declared_task(provider_env):
    registry = PromptRegistry(AIConfig.load())
    values = {
        "ocr_text": "题目",
        "has_figure": True,
        "ocr_confidence": "high",
        "normalized_text": "题目",
        "vision_json": "{}",
        "knowledge_refs": "无",
        "solver_output": "{}",
        "candidate_result": "{}",
        "subject_hint": "math",
        "stem": "题目",
        "answer": "A",
        "question_text": "题目",
        "reference_answer": "A",
        "student_answer": "A",
        "guidance_text": "先找已知条件",
        "current_question": "下一步怎么算？",
        "variant_mode": "数值变化",
        "question_context": "题干：题目",
        "variant_json": "{}",
        "original_question_context": "题干：题目",
        "question_no": "1",
        "question_type": "single_choice",
        "question_type_label": "单选题",
        "section_title": "一、选择题",
        "page_start": 1,
        "page_end": 1,
        "multi_page_notice": "",
    }

    for task_key in registry.task_keys:
        variables = registry.get_variables(task_key)
        system, user = registry.render(
            task_key, **{name: values[name] for name in variables}
        )
        assert system or user
        assert all(f"{{{name}}}" not in system + user for name in variables)


@pytest.mark.parametrize(
    ("task_key", "legacy_prompt", "variables"),
    [
        (
            "knowledge_analysis",
            AIPrompts.analyze_knowledge("题目", ""),
            {"normalized_text": "题目", "subject_hint": ""},
        ),
        (
            "mode_a_answer",
            AIPrompts.solve_mode_a("题目", "{}", ""),
            {
                "normalized_text": "题目",
                "vision_json": "{}",
                "knowledge_refs": "",
            },
        ),
        (
            "mode_b_answer",
            AIPrompts.solve_mode_b("题目", "{}", ""),
            {
                "normalized_text": "题目",
                "vision_json": "{}",
                "knowledge_refs": "",
            },
        ),
        (
            "mode_c_answer",
            AIPrompts.solve_mode_c("题目", "{}", ""),
            {
                "normalized_text": "题目",
                "vision_json": "{}",
                "knowledge_refs": "",
            },
        ),
    ],
)
def test_registry_empty_values_match_legacy_common_prompt_defaults(
    provider_env, task_key, legacy_prompt, variables
):
    system, user = PromptRegistry(AIConfig.load()).render(task_key, **variables)

    assert system == legacy_prompt["system"]
    assert user == legacy_prompt["user"]


@pytest.mark.parametrize(
    ("task_key", "variables", "expected_line"),
    [
        (
            "guidance_generate",
            {"stem": "题目", "answer": ""},
            "答案：见解析",
        ),
        (
            "guidance_evaluate",
            {
                "question_text": "题目",
                "reference_answer": "",
                "student_answer": "回答",
            },
            "参考答案：见解析",
        ),
        (
            "teacher_guidance_evaluate",
            {
                "question_text": "题目",
                "reference_answer": "",
                "student_answer": "回答",
            },
            "正确答案：见解析",
        ),
    ],
)
def test_registry_preserves_empty_answer_fallbacks(
    provider_env, task_key, variables, expected_line
):
    _, user = PromptRegistry(AIConfig.load()).render(task_key, **variables)

    assert expected_line in user


def test_registry_defaults_do_not_make_missing_variables_optional(provider_env):
    registry = PromptRegistry(AIConfig.load())

    with pytest.raises(AIPromptError, match="subject_hint"):
        registry.render("knowledge_analysis", normalized_text="题目")


def test_question_probe_prompt_requests_complete_canonical_taxonomy(provider_env):
    system, _ = PromptRegistry(AIConfig.load()).render(
        "question_probe",
        ocr_text="题目",
        has_figure=False,
        ocr_confidence="unknown",
    )

    for field_name in (
        "subject",
        "question_type",
        "grade",
        "semester",
        "chapter",
        "difficulty",
        "knowledge_points",
    ):
        assert f"{field_name} (" in system


_LEGACY_GUIDANCE_GENERATE_SYSTEM = """你是一位擅长苏格拉底式教学的中学教师。
根据题目信息和学生可能的知识水平，设计3-5个递进式引导问题。
每个问题应引导学生自主思考，而非直接给出答案。

输出严格JSON格式，不要包含markdown代码块：
{
  "steps": [
    {"question": "第一个引导问题", "hint": "提示学生思考的方向"},
    {"question": "第二个引导问题", "hint": "进一步深入提示"}
  ]
}"""


def _legacy_guidance_generate_prompt(answer: str) -> tuple[str, str]:
    return (
        _LEGACY_GUIDANCE_GENERATE_SYSTEM,
        "请为以下题目设计引导问题：\n"
        "题干：题目\n"
        f"答案：{answer or '见解析'}\n"
        "请设计3-5个递进式引导问题，帮助学生自主思考。",
    )


def _legacy_student_evaluation_prompt(answer: str) -> tuple[str, str]:
    return (
        "你是一位耐心的老师，对学生回答给出 1-2 句简明评价与鼓励。",
        "题目：题目\n"
        f"参考答案：{answer or '见解析'}\n"
        "学生回答：学生作答\n"
        "请评价。",
    )


def _legacy_teacher_evaluation_prompt(answer: str) -> tuple[str, str]:
    return (
        "你是一位经验丰富的教师。请对学生回答进行简明评价（1-2句），"
        "指出是否正确、有什么不足，然后给出鼓励。",
        "题目：题目\n"
        f"正确答案：{answer or '见解析'}\n"
        "学生回答：学生作答\n"
        "请评价学生的回答。",
    )


@pytest.mark.parametrize("answer", ["", "D"])
def test_guidance_generate_matches_complete_legacy_messages(
    provider_env, answer
):
    legacy = _legacy_guidance_generate_prompt(answer)

    rendered = PromptRegistry(AIConfig.load()).render(
        "guidance_generate", stem="题目", answer=answer
    )

    assert rendered == legacy


@pytest.mark.parametrize("answer", ["", "D"])
def test_guidance_evaluate_matches_complete_legacy_messages(
    provider_env, answer
):
    legacy = _legacy_student_evaluation_prompt(answer)

    rendered = PromptRegistry(AIConfig.load()).render(
        "guidance_evaluate",
        question_text="题目",
        reference_answer=answer,
        student_answer="学生作答",
    )

    assert rendered == legacy


@pytest.mark.parametrize("answer", ["", "D"])
def test_teacher_guidance_evaluate_matches_complete_legacy_messages(
    provider_env, answer
):
    legacy = _legacy_teacher_evaluation_prompt(answer)

    rendered = PromptRegistry(AIConfig.load()).render(
        "teacher_guidance_evaluate",
        question_text="题目",
        reference_answer=answer,
        student_answer="学生作答",
    )

    assert rendered == legacy
