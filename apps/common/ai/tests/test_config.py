from __future__ import annotations

import traceback
from pathlib import Path
from textwrap import dedent

import pytest

from apps.common.ai.config import (
    AIConfig,
    AIPromptConfig,
    load_ai_config,
    reset_ai_config_for_tests,
)
from apps.common.ai.exceptions import AIConfigError


REQUIRED_TASKS = {
    "question_probe",
    "knowledge_analysis",
    "mode_a_answer",
    "mode_b_answer",
    "mode_b_structure_repair",
    "mode_c_answer",
    "result_verify",
    "vision_fact_extract",
    "vision_page_parse",
    "vision_question_parse",
    "vision_position_detect",
    "guidance_generate",
    "guidance_evaluate",
    "teacher_guidance_evaluate",
    "variant_generate",
    "variant_verify_deepseek",
    "deepseek_baseline_solve",
    "deepseek_independent_verify",
    "deepseek_final_review",
    "photo_recognize",
    "course_material_recognize",
}

EXPECTED_ROUTE_MATRIX = {
    "question_probe": ("qwen", "qwen3.7-flash", 300.0),
    "knowledge_analysis": ("qwen", "qwen3.7-flash", 300.0),
    "mode_a_answer": ("qwen", "qwen3.7-plus", 300.0),
    "mode_b_answer": ("qwen", "qwen3.7-plus", 300.0),
    "mode_b_structure_repair": ("qwen", "qwen3.7-plus", 300.0),
    "mode_c_answer": ("qwen", "qwen3.7-plus", 300.0),
    "result_verify": ("qwen", "qwen3.7-flash", 300.0),
    "vision_fact_extract": ("qwen", "qwen3-vl-plus", 300.0),
    "vision_page_parse": ("qwen", "qwen3-vl-plus", 300.0),
    "vision_question_parse": ("qwen", "qwen3-vl-plus", 300.0),
    "vision_position_detect": ("qwen", "qwen3.7-plus", 300.0),
    "guidance_generate": ("qwen", "qwen3.7-flash", 300.0),
    "guidance_evaluate": ("qwen", "qwen3.7-flash", 300.0),
    "teacher_guidance_evaluate": ("qwen", "qwen3.7-flash", 300.0),
    "variant_generate": ("qwen", "qwen3.7-plus", 300.0),
    "variant_verify_deepseek": ("deepseek", "deepseek-v4-pro", 300.0),
    "deepseek_baseline_solve": ("deepseek", "deepseek-v4-pro", 300.0),
    "deepseek_independent_verify": ("deepseek", "deepseek-v4-pro", 300.0),
    "deepseek_final_review": ("deepseek", "deepseek-v4-pro", 300.0),
    "photo_recognize": ("qwen", "qwen3-vl-plus", 300.0),
    "course_material_recognize": ("qwen", "qwen3-vl-plus", 300.0),
}


@pytest.fixture(autouse=True)
def _reset_cached_config():
    reset_ai_config_for_tests()
    yield
    reset_ai_config_for_tests()


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv(
        "QWEN_API_URL", "https://example.test/qwen/chat/completions"
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv(
        "DEEPSEEK_API_URL", "https://example.test/deepseek/chat/completions"
    )


def write_minimal_cfg(
    tmp_path: Path,
    *,
    task: str = "question_probe",
    provider: str = "qwen",
    model: str = "qwen3.7-flash",
    prompt: str = "请分析题目 {question_text}",
    temperature: str = "0.2",
    max_tokens: str = "4096",
    timeout_seconds: str = "300",
    retry_count: str = "3",
    retry_backoff_seconds: str = "1, 2, 4",
    response_format: str = "json",
    enable_thinking: str | None = None,
    reasoning_effort: str | None = None,
) -> Path:
    env_prefix = "QWEN" if provider == "qwen" else "DEEPSEEK"
    cfg = tmp_path / "ai_config.cfg"
    thinking_options = "\n".join(
        option
        for option in (
            (
                f"enable_thinking = {enable_thinking}"
                if enable_thinking is not None
                else ""
            ),
            (
                f"reasoning_effort = {reasoning_effort}"
                if reasoning_effort is not None
                else ""
            ),
        )
        if option
    )
    cfg.write_text(
        dedent(
            f"""
            [provider:{provider}]
            api_url_env = {env_prefix}_API_URL
            api_key_env = {env_prefix}_API_KEY

            [task:{task}]
            provider = {provider}
            model = {model}
            prompt = {task}
            temperature = {temperature}
            max_tokens = {max_tokens}
            timeout_seconds = {timeout_seconds}
            retry_count = {retry_count}
            retry_backoff_seconds = {retry_backoff_seconds}
            response_format = {response_format}
            {thinking_options}

            [prompt:{task}]
            template = {prompt}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return cfg


def assert_untrusted_value_is_redacted(error: BaseException, marker: str) -> None:
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    if marker in str(error) or marker in formatted:
        pytest.fail("AIConfigError leaked untrusted configuration text", pytrace=False)
    if error.__cause__ is not None or error.__context__ is not None:
        pytest.fail("AIConfigError retained an untrusted exception chain", pytrace=False)


def test_loads_task_and_provider_from_cfg(tmp_path, provider_env):
    loaded = AIConfig.load(write_minimal_cfg(tmp_path))

    assert loaded.get_task_config("question_probe").model == "qwen3.7-flash"
    assert loaded.get_provider_config("qwen").api_url.endswith("chat/completions")
    assert loaded.get_task_config("question_probe").timeout_seconds == 300


def test_position_detection_routes_to_qwen37_plus_with_300_second_timeout(
    provider_env,
):
    loaded = AIConfig.load()

    position_task = loaded.get_task_config("vision_position_detect")
    assert position_task.model == "qwen3.7-plus"
    assert position_task.timeout_seconds == 300


def test_answer_verification_tasks_enable_deepseek_thinking(provider_env):
    config = AIConfig.load()

    for key in (
        "deepseek_baseline_solve",
        "deepseek_independent_verify",
        "deepseek_final_review",
    ):
        task = config.get_task_config(key)
        assert task.provider == "deepseek"
        assert task.model == "deepseek-v4-pro"
        assert task.timeout_seconds == 300
        assert task.retry_count == 1
        assert task.enable_thinking is True
        assert task.reasoning_effort == "high"

    for key in ("mode_a_answer", "mode_b_answer", "mode_c_answer"):
        assert config.get_task_config(key).retry_count == 1


@pytest.mark.parametrize(
    ("option", "bad_value"),
    [("enable_thinking", "maybe"), ("reasoning_effort", "extreme")],
)
def test_rejects_invalid_thinking_configuration_without_echoing_value(
    tmp_path, provider_env, option, bad_value
):
    with pytest.raises(AIConfigError) as caught:
        AIConfig.load(write_minimal_cfg(tmp_path, **{option: bad_value}))

    assert option in str(caught.value)
    assert_untrusted_value_is_redacted(caught.value, bad_value)


def test_provider_repr_does_not_expose_api_key(tmp_path, provider_env):
    provider = AIConfig.load(write_minimal_cfg(tmp_path)).get_provider_config("qwen")

    assert "test-qwen-key" not in repr(provider)


def test_missing_required_env_fails_without_leaking_secret(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/chat/completions")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    with pytest.raises(AIConfigError, match="QWEN_API_KEY") as caught:
        AIConfig.load(write_minimal_cfg(tmp_path))

    assert "chat/completions" not in str(caught.value)


def test_malformed_config_error_redacts_source_text_and_exception_chain(
    tmp_path,
):
    marker = "-".join(("sk", "live", "sensitive", "token"))
    cfg = tmp_path / "malformed.cfg"
    cfg.write_text(f"[provider:qwen]\n{marker}\n", encoding="utf-8")

    with pytest.raises(AIConfigError) as caught:
        AIConfig.load(cfg)

    assert_untrusted_value_is_redacted(caught.value, marker)


def test_rejects_missing_provider_section(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    task_config = cfg.read_text(encoding="utf-8").split(
        "[task:question_probe]", 1
    )[1]
    cfg.write_text(
        "[task:question_probe]" + task_config,
        encoding="utf-8",
    )

    with pytest.raises(AIConfigError, match="provider"):
        AIConfig.load(cfg)


@pytest.mark.parametrize(
    ("option", "bad_value"),
    [
        ("max_tokens", "not-an-integer"),
        ("max_tokens", "0"),
        ("retry_count", "-1"),
        ("temperature", "not-a-float"),
        ("temperature", "2.01"),
        ("timeout_seconds", "299.9"),
        ("retry_backoff_seconds", "1, -2, 4"),
        ("retry_backoff_seconds", "1, nan, 4"),
    ],
)
def test_rejects_invalid_numeric_values(
    tmp_path, provider_env, option, bad_value
):
    kwargs = {option: bad_value}

    with pytest.raises(AIConfigError, match=option):
        AIConfig.load(write_minimal_cfg(tmp_path, **kwargs))


def test_rejects_unknown_provider(tmp_path, provider_env):
    with pytest.raises(AIConfigError, match="unknown provider"):
        AIConfig.load(write_minimal_cfg(tmp_path, provider="other"))


def test_rejects_unknown_section(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    cfg.write_text(
        cfg.read_text(encoding="utf-8") + "\n[typo:question_probe]\nvalue = ignored\n",
        encoding="utf-8",
    )

    with pytest.raises(AIConfigError, match="unknown section"):
        AIConfig.load(cfg)


@pytest.mark.parametrize("model", ["qwen-legacy-plus", "qwen3-vl-max", "deepseek-v4-pro"])
def test_rejects_invalid_qwen_task_model(tmp_path, provider_env, model):
    with pytest.raises(AIConfigError, match="model"):
        AIConfig.load(write_minimal_cfg(tmp_path, model=model))


def test_invalid_model_error_redacts_configured_value(tmp_path, provider_env):
    marker = "-".join(("model", "sensitive", "token"))

    with pytest.raises(AIConfigError) as caught:
        AIConfig.load(write_minimal_cfg(tmp_path, model=marker))

    assert_untrusted_value_is_redacted(caught.value, marker)


def test_invalid_numeric_error_redacts_configured_value_and_exception_chain(
    tmp_path, provider_env
):
    marker = "-".join(("numeric", "sensitive", "token"))

    with pytest.raises(AIConfigError) as caught:
        AIConfig.load(write_minimal_cfg(tmp_path, max_tokens=marker))

    assert_untrusted_value_is_redacted(caught.value, marker)


def test_rejects_unconfigured_deepseek_model(tmp_path, provider_env):
    with pytest.raises(AIConfigError, match="model"):
        AIConfig.load(
            write_minimal_cfg(
                tmp_path,
                task="variant_verify_deepseek",
                provider="deepseek",
                model="deepseek-unconfigured",
            )
        )


def test_rejects_qwen_route_for_deepseek_verification_task(
    tmp_path, provider_env
):
    with pytest.raises(AIConfigError, match="provider route"):
        AIConfig.load(
            write_minimal_cfg(
                tmp_path,
                task="variant_verify_deepseek",
                provider="qwen",
                model="qwen3.7-flash",
            )
        )


def test_rejects_missing_prompt_section(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    content = cfg.read_text(encoding="utf-8").split("[prompt:question_probe]", 1)[0]
    cfg.write_text(content, encoding="utf-8")

    with pytest.raises(AIConfigError, match="prompt"):
        AIConfig.load(cfg)


def test_reads_utf8_chinese_and_preserves_prompt_braces(tmp_path, provider_env):
    loaded = AIConfig.load(
        write_minimal_cfg(tmp_path, prompt="请根据 {question_text} 提出追问：为什么？")
    )

    assert loaded.get_task_config("question_probe").prompt == (
        "请根据 {question_text} 提出追问：为什么？"
    )


def test_exposes_immutable_prompt_configuration(tmp_path, provider_env):
    loaded = AIConfig.load(write_minimal_cfg(tmp_path))

    prompt = loaded.get_prompt_config("question_probe")

    assert isinstance(prompt, AIPromptConfig)
    assert prompt.system == ""
    assert prompt.user == "请分析题目 {question_text}"
    assert prompt.variables == ("question_text",)
    with pytest.raises((AttributeError, TypeError)):
        prompt.user = "changed"


def test_default_config_declares_every_task_with_300_second_timeout(provider_env):
    loaded = AIConfig.load()

    assert set(loaded.task_keys) == REQUIRED_TASKS
    assert {loaded.get_task_config(key).timeout_seconds for key in REQUIRED_TASKS} == {
        300.0
    }
    assert {
        key: loaded.get_task_config(key).provider for key in REQUIRED_TASKS
    } == {
        key: "deepseek"
        if key
        in {
            "variant_verify_deepseek",
            "deepseek_baseline_solve",
            "deepseek_independent_verify",
            "deepseek_final_review",
        }
        else "qwen"
        for key in REQUIRED_TASKS
    }


def test_default_config_matches_complete_approved_route_matrix(provider_env):
    loaded = AIConfig.load()

    assert {
        key: (
            loaded.get_task_config(key).provider,
            loaded.get_task_config(key).model,
            loaded.get_task_config(key).timeout_seconds,
        )
        for key in loaded.task_keys
    } == EXPECTED_ROUTE_MATRIX


@pytest.mark.parametrize("prefix", ["provider", "task"])
def test_rejects_trim_normalized_section_name_collisions(
    tmp_path, provider_env, prefix
):
    cfg = write_minimal_cfg(tmp_path)
    section = cfg.read_text(encoding="utf-8").split(
        f"[{prefix}:question_probe]" if prefix == "task" else "[provider:qwen]",
        1,
    )[1]
    section_body = section.split("\n[", 1)[0]
    name = "question_probe" if prefix == "task" else "qwen"
    cfg.write_text(
        cfg.read_text(encoding="utf-8")
        + f"\n[{prefix}: {name} ]\n{section_body.strip()}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        AIConfigError, match=f"duplicate {prefix} section"
    ) as caught:
        AIConfig.load(cfg)

    assert str(caught.value) == (
        f"AI configuration contains duplicate {prefix} section"
    )


def test_env_example_placeholders_boot_default_ai_config(monkeypatch):
    env_path = Path(__file__).resolve().parents[4] / ".env.example"
    values = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()

    assert "AI_MODEL" not in values
    for name in ("QWEN_API_URL", "QWEN_API_KEY", "DEEPSEEK_API_URL"):
        assert values.get(name)
        monkeypatch.setenv(name, values[name])
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    loaded = AIConfig.load()

    assert loaded.get_provider_config("qwen").api_url == values["QWEN_API_URL"]
    assert loaded.get_provider_config("deepseek").api_key == ""


def test_default_config_allows_only_explicitly_optional_deepseek_key(
    monkeypatch,
):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.setenv("DEEPSEEK_API_URL", "https://example.test/deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    loaded = AIConfig.load()

    assert loaded.get_provider_config("qwen").api_key == "test-qwen-key"
    assert loaded.get_provider_config("deepseek").api_key == ""


def test_optional_deepseek_key_does_not_make_provider_url_optional(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-qwen-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.delenv("DEEPSEEK_API_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(AIConfigError, match="DEEPSEEK_API_URL"):
        AIConfig.load()


def test_rejects_invalid_api_key_optional_declaration(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            "api_key_env = QWEN_API_KEY",
            "api_key_env = QWEN_API_KEY\napi_key_optional = sometimes",
        ),
        encoding="utf-8",
    )

    with pytest.raises(AIConfigError, match="api_key_optional"):
        AIConfig.load(cfg)


def test_rejects_optional_qwen_key_in_independent_config(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/qwen")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    cfg = write_minimal_cfg(tmp_path)
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace(
            "api_key_env = QWEN_API_KEY",
            "api_key_env = QWEN_API_KEY\napi_key_optional = true",
        ),
        encoding="utf-8",
    )

    with pytest.raises(AIConfigError) as caught:
        AIConfig.load(cfg)

    assert str(caught.value) == (
        "Optional AI provider credentials are restricted"
    )
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_runtime_loader_caches_first_successful_load(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    first = load_ai_config(cfg)
    cfg.unlink()

    assert load_ai_config(cfg) is first


def test_reset_allows_tests_to_replace_cached_config(tmp_path, provider_env):
    cfg = write_minimal_cfg(tmp_path)
    first = load_ai_config(cfg)
    reset_ai_config_for_tests()

    second = load_ai_config(cfg)

    assert second is not first
