"""Validated rendering for process-scoped AI prompts."""

from __future__ import annotations

import re

from .config import (
    AIConfig,
    AIPromptConfig,
    PROMPT_VARIABLE_PATTERN,
    load_ai_config,
)
from .exceptions import AIConfigError, AIPromptError


class PromptRegistry:
    """Render prompts already validated by :class:`AIConfig`."""

    def __init__(self, config: AIConfig | None = None) -> None:
        self._config = config if config is not None else load_ai_config()

    @property
    def task_keys(self) -> tuple[str, ...]:
        return self._config.task_keys

    def get_variables(self, task_key: str) -> tuple[str, ...]:
        return self._get_prompt(task_key).variables

    def render(self, task_key: str, **variables: object) -> tuple[str, str]:
        prompt = self._get_prompt(task_key)
        expected = set(prompt.variables)
        supplied = set(variables)
        missing = expected - supplied
        if missing:
            raise AIPromptError(
                "Missing prompt variable(s): " + _safe_variable_names(missing)
            )
        unknown = supplied - expected
        if unknown:
            raise AIPromptError(
                "Unknown prompt variable(s): " + _safe_variable_names(unknown)
            )

        rendered = {name: str(value) for name, value in variables.items()}
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
            task = self._config.get_task_config(task_key)
            return self._config.get_prompt_config(task.prompt_key)
        except AIConfigError:
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
