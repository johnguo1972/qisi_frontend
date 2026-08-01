from __future__ import annotations

from pathlib import Path

import pytest

from apps.common.ai.config import AIConfig
from apps.common.ai.exceptions import AIConfigError, AIPromptError
from apps.common.ai.prompt_registry import PromptRegistry


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
