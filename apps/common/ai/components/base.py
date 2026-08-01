"""Database-free primitives for question-oriented AI components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Protocol

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.ai.types import AIResult


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


def to_plain_data(value: object) -> object:
    """Convert frozen collection values into JSON-compatible containers."""
    if isinstance(value, Mapping):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [to_plain_data(item) for item in value]
    if isinstance(value, frozenset):
        return [to_plain_data(item) for item in value]
    return value


@dataclass(frozen=True)
class QuestionInput:
    stem: str
    options: dict | list | None = None
    answer: str = ""
    solution: str = ""
    image_urls: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _freeze(self.options))
        object.__setattr__(self, "image_urls", tuple(self.image_urls))
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))


class AICompleter(Protocol):
    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None = None,
    ) -> AIResult: ...


class QuestionAIComponent(ABC):
    """Render, execute, and parse one fixed configured AI task."""

    task_key: ClassVar[str]

    def __init__(
        self,
        ai_client: AICompleter,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._ai_client = ai_client
        self._prompt_registry = prompt_registry or PromptRegistry()

    def run(self, question: QuestionInput) -> dict:
        system, user = self._prompt_registry.render(
            self.task_key, **self.prompt_variables(question)
        )
        trace_id = question.metadata.get("trace_id")
        result = self._ai_client.complete(
            self.task_key,
            system=system,
            user=user,
            images=question.image_urls,
            trace_id=str(trace_id) if trace_id is not None else None,
        )
        parsed = ResponseParser.parse_json(result.content)
        if not isinstance(parsed, dict):
            raise AIResponseError("AI question component response must be an object")
        return self.normalize(dict(parsed))

    @abstractmethod
    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        """Return exactly the configured variables for this task."""

    def normalize(self, result: dict) -> dict:
        return result


class QuestionComponentFactory:
    """Create components sharing one client and prompt registry."""

    def __init__(
        self,
        ai_client: AICompleter | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._ai_client = ai_client or AIClient()
        self._prompt_registry = prompt_registry or PromptRegistry()

    def __call__(self, component_type: type[QuestionAIComponent]):
        return component_type(self._ai_client, self._prompt_registry)
