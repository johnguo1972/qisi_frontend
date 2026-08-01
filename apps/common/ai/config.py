"""Validated, process-scoped AI runtime configuration."""

from __future__ import annotations

import os
import re
from configparser import Error as ConfigParserError
from configparser import RawConfigParser
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from .exceptions import AIConfigError


DEFAULT_AI_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ai_config.cfg"
SUPPORTED_PROVIDERS = frozenset({"qwen", "deepseek"})
QWEN_MODELS = frozenset({"qwen3.7-flash", "qwen3.7-plus", "qwen3-vl-plus"})
DEEPSEEK_MODELS = frozenset({"deepseek-v4-pro"})
ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class AIProviderConfig:
    name: str
    api_url: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class AITaskConfig:
    key: str
    provider: str
    model: str
    prompt: str
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
    ) -> None:
        self._providers = providers.copy()
        self._tasks = tasks.copy()

    @property
    def task_keys(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    @classmethod
    def load(cls, path: Path | None = None) -> "AIConfig":
        config_path = Path(path) if path is not None else DEFAULT_AI_CONFIG_PATH
        parser = RawConfigParser(interpolation=None)
        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                parser.read_file(config_file)
        except (OSError, UnicodeError, ConfigParserError) as exc:
            raise AIConfigError(
                f"Unable to read AI configuration file {config_path}: {exc}"
            ) from exc

        for section in parser.sections():
            if not section.startswith(("provider:", "task:", "prompt:")):
                raise AIConfigError(
                    f"AI configuration contains unknown section [{section}]"
                )

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
        return cls(providers=providers, tasks=tasks)

    def get_task_config(self, task_key: str) -> AITaskConfig:
        try:
            return self._tasks[task_key]
        except KeyError as exc:
            raise AIConfigError(f"Unknown AI task: {task_key}") from exc

    def get_provider_config(self, provider: str) -> AIProviderConfig:
        try:
            return self._providers[provider]
        except KeyError as exc:
            raise AIConfigError(f"Unknown AI provider: {provider}") from exc


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
        raise AIConfigError(f"Section [{section}] is missing required option(s): {names}")
    unknown = present - required - (optional or set())
    if unknown:
        names = ", ".join(sorted(unknown))
        raise AIConfigError(f"Section [{section}] has unknown option(s): {names}")


def _load_provider(
    parser: RawConfigParser, section: str, name: str
) -> AIProviderConfig:
    if name not in SUPPORTED_PROVIDERS:
        raise AIConfigError(f"Section [{section}] uses unknown provider {name}")
    _require_options(parser, section, {"api_url_env", "api_key_env"})
    api_url_env = parser.get(section, "api_url_env").strip()
    api_key_env = parser.get(section, "api_key_env").strip()
    api_url = _read_env_reference(section, "api_url_env", api_url_env)
    api_key = _read_env_reference(section, "api_key_env", api_key_env)
    parsed_url = urlparse(api_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise AIConfigError(
            f"Environment variable {api_url_env} for [{section}] is not a valid HTTP URL"
        )
    return AIProviderConfig(name=name, api_url=api_url, api_key=api_key)


def _read_env_reference(section: str, option: str, env_name: str) -> str:
    if not ENV_NAME_PATTERN.fullmatch(env_name):
        raise AIConfigError(
            f"Option {option} in [{section}] must contain an environment variable name"
        )
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise AIConfigError(
            f"Environment variable {env_name} required by [{section}] is not set"
        )
    return value


def _load_prompt(parser: RawConfigParser, section: str, name: str) -> str:
    _require_options(parser, section, {"template"})
    template = parser.get(section, "template").strip()
    if not template:
        raise AIConfigError(f"Prompt section [{section}] has an empty template")
    return template


def _load_task(
    parser: RawConfigParser,
    section: str,
    key: str,
    providers: dict[str, AIProviderConfig],
    prompts: dict[str, str],
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
    if provider not in providers:
        if provider not in SUPPORTED_PROVIDERS:
            raise AIConfigError(f"Task [{section}] uses unknown provider {provider}")
        raise AIConfigError(
            f"Task [{section}] references missing provider section provider:{provider}"
        )

    model = parser.get(section, "model").strip()
    _validate_model(section, provider, model)
    prompt_name = parser.get(section, "prompt").strip()
    if prompt_name not in prompts:
        raise AIConfigError(
            f"Task [{section}] references missing prompt section prompt:{prompt_name}"
        )

    temperature = _parse_float(parser, section, "temperature")
    if not 0 <= temperature <= 2:
        raise AIConfigError(f"Option temperature in [{section}] must be between 0 and 2")
    max_tokens = _parse_int(parser, section, "max_tokens")
    if max_tokens <= 0:
        raise AIConfigError(f"Option max_tokens in [{section}] must be greater than zero")
    timeout_seconds = _parse_float(parser, section, "timeout_seconds")
    if timeout_seconds != 300:
        raise AIConfigError(f"Option timeout_seconds in [{section}] must be exactly 300")
    retry_count = _parse_int(parser, section, "retry_count")
    if retry_count < 0:
        raise AIConfigError(f"Option retry_count in [{section}] cannot be negative")
    retry_backoff_seconds = _parse_float_tuple(
        parser, section, "retry_backoff_seconds"
    )
    if any(not isfinite(value) or value < 0 for value in retry_backoff_seconds):
        raise AIConfigError(
            f"Option retry_backoff_seconds in [{section}] cannot contain negative values"
        )
    response_format = parser.get(section, "response_format", fallback="").strip() or None

    return AITaskConfig(
        key=key,
        provider=provider,
        model=model,
        prompt=prompts[prompt_name],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        retry_backoff_seconds=retry_backoff_seconds,
        response_format=response_format,
    )


def _validate_model(section: str, provider: str, model: str) -> None:
    if provider == "qwen" and model not in QWEN_MODELS:
        allowed = ", ".join(sorted(QWEN_MODELS))
        raise AIConfigError(
            f"Task [{section}] has invalid Qwen model {model!r}; allowed: {allowed}"
        )
    if provider == "deepseek" and model not in DEEPSEEK_MODELS:
        raise AIConfigError(f"Task [{section}] has invalid DeepSeek model {model!r}")


def _parse_int(parser: RawConfigParser, section: str, option: str) -> int:
    value = parser.get(section, option).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise AIConfigError(
            f"Option {option} in [{section}] must be an integer"
        ) from exc


def _parse_float(parser: RawConfigParser, section: str, option: str) -> float:
    value = parser.get(section, option).strip()
    try:
        return float(value)
    except ValueError as exc:
        raise AIConfigError(f"Option {option} in [{section}] must be a number") from exc


def _parse_float_tuple(
    parser: RawConfigParser, section: str, option: str
) -> tuple[float, ...]:
    raw_values = parser.get(section, option).strip()
    if not raw_values:
        return ()
    try:
        return tuple(float(value.strip()) for value in raw_values.split(","))
    except ValueError as exc:
        raise AIConfigError(
            f"Option {option} in [{section}] must be a comma-separated number list"
        ) from exc


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
