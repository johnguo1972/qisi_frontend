"""Validated, process-scoped AI runtime configuration."""

from __future__ import annotations

import json
import os
import re
from configparser import Error as ConfigParserError
from configparser import RawConfigParser
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlparse

from .exceptions import AIConfigError


DEFAULT_AI_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ai_config.cfg"
SUPPORTED_PROVIDERS = frozenset({"qwen", "deepseek"})
QWEN_MODELS = frozenset({"qwen3.7-flash", "qwen3.7-plus", "qwen3-vl-plus"})
DEEPSEEK_MODELS = frozenset({"deepseek-v4-pro"})
TASK_PROVIDER_SCHEMA = {
    "question_probe": "qwen",
    "knowledge_analysis": "qwen",
    "mode_a_answer": "qwen",
    "mode_b_answer": "qwen",
    "mode_c_answer": "qwen",
    "result_verify": "qwen",
    "vision_fact_extract": "qwen",
    "vision_page_parse": "qwen",
    "vision_question_parse": "qwen",
    "vision_position_detect": "qwen",
    "guidance_generate": "qwen",
    "guidance_evaluate": "qwen",
    "teacher_guidance_evaluate": "qwen",
    "variant_generate": "qwen",
    "variant_verify_deepseek": "deepseek",
    "photo_recognize": "qwen",
}
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
PROMPT_VARIABLE_PATTERN = re.compile(
    r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})"
)


@dataclass(frozen=True)
class AIProviderConfig:
    name: str
    api_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class AIPromptConfig:
    key: str
    system: str
    user: str
    variables: tuple[str, ...]
    defaults: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AITaskConfig:
    key: str
    provider: str
    model: str
    prompt: str
    prompt_key: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    retry_count: int
    retry_backoff_seconds: tuple[float, ...]
    response_format: str | None


class AIConfig:
    """Immutable provider and task configuration loaded from an INI file."""

    def __init__(
        self,
        providers: dict[str, AIProviderConfig],
        tasks: dict[str, AITaskConfig],
        prompts: dict[str, AIPromptConfig],
    ) -> None:
        self._providers: Mapping[str, AIProviderConfig] = MappingProxyType(
            providers.copy()
        )
        self._tasks: Mapping[str, AITaskConfig] = MappingProxyType(tasks.copy())
        self._prompts: Mapping[str, AIPromptConfig] = MappingProxyType(
            prompts.copy()
        )

    @property
    def task_keys(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    @property
    def prompt_keys(self) -> tuple[str, ...]:
        return tuple(self._prompts)

    @classmethod
    def load(cls, path: Path | None = None) -> "AIConfig":
        config_path = Path(path) if path is not None else DEFAULT_AI_CONFIG_PATH
        parser = _read_config_parser(config_path)
        if parser is None:
            raise AIConfigError("Unable to read AI configuration file")

        for section in parser.sections():
            if not section.startswith(("provider:", "task:", "prompt:")):
                raise AIConfigError("AI configuration contains unknown section")

        provider_sections = _named_sections(parser, "provider")
        task_sections = _named_sections(parser, "task")
        prompt_sections = _named_sections(parser, "prompt")
        if not provider_sections:
            raise AIConfigError("AI configuration requires a provider section")
        if not task_sections:
            raise AIConfigError("AI configuration requires a task section")
        if not prompt_sections:
            raise AIConfigError("AI configuration requires a prompt section")

        providers = {
            name: _load_provider(parser, section, name)
            for section, name in provider_sections
        }
        prompts = {
            name: _load_prompt(parser, section, name)
            for section, name in prompt_sections
        }
        tasks = {
            name: _load_task(parser, section, name, providers, prompts)
            for section, name in task_sections
        }
        return cls(providers=providers, tasks=tasks, prompts=prompts)

    def get_task_config(self, task_key: str) -> AITaskConfig:
        task = self._tasks.get(task_key)
        if task is None:
            raise AIConfigError("Unknown AI task")
        return task

    def get_provider_config(self, provider: str) -> AIProviderConfig:
        provider_config = self._providers.get(provider)
        if provider_config is None:
            raise AIConfigError("Unknown AI provider")
        return provider_config

    def get_prompt_config(self, prompt_key: str) -> AIPromptConfig:
        prompt = self._prompts.get(prompt_key)
        if prompt is None:
            raise AIConfigError("Unknown AI prompt")
        return prompt


def _read_config_parser(config_path: Path) -> RawConfigParser | None:
    parser = RawConfigParser(
        interpolation=None,
        comment_prefixes=(";",),
        inline_comment_prefixes=None,
    )
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            parser.read_file(config_file)
    except (OSError, UnicodeError, ConfigParserError):
        return None
    return parser


def _named_sections(
    parser: RawConfigParser, prefix: str
) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    marker = f"{prefix}:"
    for section in parser.sections():
        if not section.startswith(marker):
            continue
        name = section[len(marker) :].strip()
        if not name:
            raise AIConfigError(f"AI {prefix} section name cannot be empty")
        sections.append((section, name))
    return sections


def _require_options(
    parser: RawConfigParser,
    section: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    present = set(parser.options(section))
    missing = required - present
    if missing:
        names = ", ".join(sorted(missing))
        raise AIConfigError(
            f"AI configuration section is missing required option(s): {names}"
        )
    unknown = present - required - (optional or set())
    if unknown:
        raise AIConfigError("AI configuration section has unknown option(s)")


def _load_provider(
    parser: RawConfigParser, section: str, name: str
) -> AIProviderConfig:
    if name not in SUPPORTED_PROVIDERS:
        raise AIConfigError("AI provider section uses unknown provider")
    _require_options(
        parser,
        section,
        {"api_url_env", "api_key_env"},
        {"api_key_optional"},
    )
    api_url_env = parser.get(section, "api_url_env").strip()
    api_key_env = parser.get(section, "api_key_env").strip()
    api_key_optional = _parse_bool_option(
        parser,
        section,
        "api_key_optional",
        fallback=False,
    )
    api_url = _read_env_reference(section, "api_url_env", api_url_env)
    api_key = _read_env_reference(
        section,
        "api_key_env",
        api_key_env,
        optional=api_key_optional,
    )
    parsed_url = urlparse(api_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise AIConfigError("AI provider URL is not a valid HTTP URL")
    return AIProviderConfig(name=name, api_url=api_url, api_key=api_key)


def _read_env_reference(
    section: str,
    option: str,
    env_name: str,
    *,
    optional: bool = False,
) -> str:
    if not ENV_NAME_PATTERN.fullmatch(env_name):
        raise AIConfigError("AI provider option must name an environment variable")
    value = os.environ.get(env_name, "").strip()
    if not value:
        if optional:
            return ""
        raise AIConfigError(
            f"Environment variable {env_name} required by [{section}] is not set"
        )
    return value


def _parse_bool_option(
    parser: RawConfigParser,
    section: str,
    option: str,
    *,
    fallback: bool,
) -> bool:
    if not parser.has_option(section, option):
        return fallback
    raw_value = parser.get(section, option).strip().lower()
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise AIConfigError(f"Option {option} must be true or false")


def _load_prompt(
    parser: RawConfigParser, section: str, name: str
) -> AIPromptConfig:
    present = set(parser.options(section))
    if "template" in present:
        _require_options(
            parser,
            section,
            {"template"},
            {"variables", "defaults", "encoding"},
        )
        system = ""
        user = parser.get(section, "template").strip()
        inferred = _extract_prompt_variables(user)
        variables = (
            _parse_prompt_variables(parser.get(section, "variables"))
            if "variables" in present
            else inferred
        )
    else:
        _require_options(
            parser,
            section,
            {"system", "user", "variables"},
            {"defaults", "encoding"},
        )
        system = parser.get(section, "system").strip()
        user = parser.get(section, "user").strip()
        variables = _parse_prompt_variables(parser.get(section, "variables"))

    encoding = parser.get(section, "encoding", fallback="plain").strip()
    system = _decode_prompt_text(system, encoding)
    user = _decode_prompt_text(user, encoding)

    if not system and not user:
        raise AIConfigError("AI prompt section cannot be empty")
    actual_variables = _extract_prompt_variables(system, user)
    if set(variables) != set(actual_variables):
        raise AIConfigError(
            "AI prompt variables do not match template placeholders"
        )
    defaults = _parse_prompt_defaults(
        parser.get(section, "defaults", fallback=""), variables
    )
    return AIPromptConfig(
        key=name,
        system=system,
        user=user,
        variables=variables,
        defaults=defaults,
    )


def _parse_prompt_variables(raw_variables: str) -> tuple[str, ...]:
    if not raw_variables.strip():
        return ()
    variables = tuple(
        variable.strip() for variable in raw_variables.split(",")
    )
    if (
        any(not variable.isidentifier() for variable in variables)
        or len(set(variables)) != len(variables)
    ):
        raise AIConfigError("AI prompt variables declaration is invalid")
    return variables


def _decode_prompt_text(text: str, encoding: str) -> str:
    if encoding == "plain":
        return text
    if encoding != "json":
        raise AIConfigError("AI prompt encoding is invalid")
    parse_failed = False
    try:
        decoded = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        parse_failed = True
    if parse_failed or not isinstance(decoded, str):
        raise AIConfigError("AI prompt encoded text is invalid")
    return decoded


def _extract_prompt_variables(*templates: str) -> tuple[str, ...]:
    variables: list[str] = []
    for template in templates:
        for match in PROMPT_VARIABLE_PATTERN.finditer(template):
            variable = match.group(1)
            if variable not in variables:
                variables.append(variable)
    return tuple(variables)


def _parse_prompt_defaults(
    raw_defaults: str, variables: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    if not raw_defaults.strip():
        return ()
    parse_failed = False
    try:
        parsed = json.loads(raw_defaults)
    except (TypeError, json.JSONDecodeError):
        parse_failed = True
    if (
        parse_failed
        or not isinstance(parsed, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in parsed.items()
        )
        or not set(parsed).issubset(variables)
    ):
        raise AIConfigError("AI prompt defaults declaration is invalid")
    return tuple(
        (variable, parsed[variable])
        for variable in variables
        if variable in parsed
    )


def _load_task(
    parser: RawConfigParser,
    section: str,
    key: str,
    providers: dict[str, AIProviderConfig],
    prompts: dict[str, AIPromptConfig],
) -> AITaskConfig:
    _require_options(
        parser,
        section,
        {
            "provider",
            "model",
            "prompt",
            "temperature",
            "max_tokens",
            "timeout_seconds",
            "retry_count",
            "retry_backoff_seconds",
        },
        {"response_format"},
    )
    provider = parser.get(section, "provider").strip()
    if provider not in SUPPORTED_PROVIDERS:
        raise AIConfigError("AI task uses unknown provider")
    expected_provider = TASK_PROVIDER_SCHEMA.get(key)
    if expected_provider is None:
        raise AIConfigError("AI task is not declared in the provider route schema")
    if provider != expected_provider:
        raise AIConfigError("AI task provider route does not match required schema")
    if provider not in providers:
        raise AIConfigError("AI task references a missing provider section")

    model = parser.get(section, "model").strip()
    _validate_model(provider, model)
    prompt_name = parser.get(section, "prompt").strip()
    prompt_config = prompts.get(prompt_name)
    if prompt_config is None:
        raise AIConfigError("AI task references a missing prompt section")

    temperature = _parse_float(parser, section, "temperature")
    if not 0 <= temperature <= 2:
        raise AIConfigError("Option temperature must be between 0 and 2")
    max_tokens = _parse_int(parser, section, "max_tokens")
    if max_tokens <= 0:
        raise AIConfigError("Option max_tokens must be greater than zero")
    timeout_seconds = _parse_float(parser, section, "timeout_seconds")
    if timeout_seconds != 300:
        raise AIConfigError("Option timeout_seconds must be exactly 300")
    retry_count = _parse_int(parser, section, "retry_count")
    if retry_count < 0:
        raise AIConfigError("Option retry_count cannot be negative")
    retry_backoff_seconds = _parse_float_tuple(
        parser, section, "retry_backoff_seconds"
    )
    if any(not isfinite(value) or value < 0 for value in retry_backoff_seconds):
        raise AIConfigError(
            "Option retry_backoff_seconds cannot contain negative values"
        )
    response_format = parser.get(section, "response_format", fallback="").strip() or None

    return AITaskConfig(
        key=key,
        provider=provider,
        model=model,
        prompt=prompt_config.user or prompt_config.system,
        prompt_key=prompt_name,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        retry_backoff_seconds=retry_backoff_seconds,
        response_format=response_format,
    )


def _validate_model(provider: str, model: str) -> None:
    if provider == "qwen" and model not in QWEN_MODELS:
        allowed = ", ".join(sorted(QWEN_MODELS))
        raise AIConfigError(
            f"AI task has an invalid Qwen model; allowed: {allowed}"
        )
    if provider == "deepseek" and model not in DEEPSEEK_MODELS:
        raise AIConfigError("AI task has an invalid DeepSeek model")


def _parse_int(parser: RawConfigParser, section: str, option: str) -> int:
    value = parser.get(section, option).strip()
    parsed: int | None = None
    try:
        parsed = int(value)
    except ValueError:
        pass
    if parsed is None:
        raise AIConfigError(f"Option {option} must be an integer")
    return parsed


def _parse_float(parser: RawConfigParser, section: str, option: str) -> float:
    value = parser.get(section, option).strip()
    parsed: float | None = None
    try:
        parsed = float(value)
    except ValueError:
        pass
    if parsed is None:
        raise AIConfigError(f"Option {option} must be a number")
    return parsed


def _parse_float_tuple(
    parser: RawConfigParser, section: str, option: str
) -> tuple[float, ...]:
    raw_values = parser.get(section, option).strip()
    if not raw_values:
        return ()
    parsed: tuple[float, ...] | None = None
    try:
        parsed = tuple(float(value.strip()) for value in raw_values.split(","))
    except ValueError:
        pass
    if parsed is None:
        raise AIConfigError(
            f"Option {option} must be a comma-separated number list"
        )
    return parsed


_ai_config: AIConfig | None = None
_ai_config_lock = Lock()


def load_ai_config(path: Path | None = None) -> AIConfig:
    """Load the AI config once per process and reuse it for all later calls."""
    global _ai_config
    if _ai_config is None:
        with _ai_config_lock:
            if _ai_config is None:
                _ai_config = AIConfig.load(path)
    return _ai_config


def reset_ai_config_for_tests() -> None:
    """Clear the process cache so tests can exercise independent config files."""
    global _ai_config
    with _ai_config_lock:
        _ai_config = None
