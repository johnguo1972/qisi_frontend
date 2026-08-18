"""Validated rendering for process-scoped AI prompts."""

from __future__ import annotations

import re

from .config import (
    AIConfig,
    AIPromptConfig,
    PROMPT_VARIABLE_PATTERN,
    load_ai_config,
)
from .exceptions import AIPromptError


class PromptRegistry:
    """Render prompts already validated by :class:`AIConfig`."""

    def __init__(self, config: AIConfig | None = None) -> None:
        source = config if config is not None else load_ai_config()
        self._tasks = {
            key: source.get_task_config(key) for key in source.task_keys
        }
        self._prompts = {
            key: source.get_prompt_config(key) for key in source.prompt_keys
        }
        source = None

    @property
    def task_keys(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    def get_variables(self, task_key: str) -> tuple[str, ...]:
        return self._get_prompt(task_key).variables

    def get_retry_count(self, task_key: str) -> int:
        try:
            return self._tasks[task_key].retry_count
        except KeyError:
            raise AIPromptError("Unknown AI task") from None

    def render(self, task_key: str, **variables: object) -> tuple[str, str]:
        prompt = self._get_prompt(task_key)
        expected = set(prompt.variables)
        supplied = set(variables)
        unknown = supplied - expected
        if unknown:
            raise AIPromptError(
                "Unknown prompt variable(s): " + _safe_variable_names(unknown)
            )

        defaults = dict(prompt.defaults)
        rendered = {}
        missing = set()
        context_defaults = {
            "question_context_json",
        }
        for name in expected:
            is_provided = name in variables
            value = variables[name] if is_provided else None
            if (not is_provided and name in defaults and name in context_defaults):
                value = defaults[name]
            if is_provided and name in defaults and (
                value is None
                or value == ""
                or (
                    isinstance(value, (list, tuple, dict))
                    and len(value) == 0
                )
            ):
                value = defaults[name]
            if value is None:
                missing.add(name)
                continue
            rendered[name] = str(value)
        if missing:
            raise AIPromptError(
                "Missing prompt variable(s): " + _safe_variable_names(missing)
            )
        system = _render_template(prompt.system, rendered)
        user = _render_template(prompt.user, rendered)
        unresolved = {
            match.group(1)
            for text in (system, user)
            for match in PROMPT_VARIABLE_PATTERN.finditer(text)
            if match.group(1) in expected
        }
        if unresolved:
            raise AIPromptError(
                "Unresolved prompt variable(s): "
                + _safe_variable_names(unresolved)
            )
        return system, user

    def _get_prompt(self, task_key: str) -> AIPromptConfig:
        try:
            task = self._tasks[task_key]
            return self._prompts[task.prompt_key]
        except KeyError:
            raise AIPromptError("Unknown AI task") from None


def _render_template(template: str, variables: dict[str, str]) -> str:
    return PROMPT_VARIABLE_PATTERN.sub(
        lambda match: variables[match.group(1)], template
    )


def _safe_variable_names(names: set[str]) -> str:
    safe_names = [
        name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name) else "<invalid>"
        for name in sorted(names)
    ]
    return ", ".join(safe_names)
