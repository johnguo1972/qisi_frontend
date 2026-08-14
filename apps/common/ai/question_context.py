"""Immutable, provider-neutral question context for answer generation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
import hashlib
import json

from .components.base import QuestionInput, to_plain_data


def _plain_value(value: object) -> object:
    """Return only JSON-compatible values; never retain ORM objects/managers."""
    value = to_plain_data(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain_value(item) for item in value]
    if getattr(value, "_meta", None) is not None:
        return ""
    if callable(getattr(value, "all", None)):
        return []
    return str(value)


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _field(question: object, *names: str, default: object = "") -> object:
    for name in names:
        value = getattr(question, name, None)
        if value is not None:
            return value
    return default


def _option_value(option: object, *names: str, default: object = "") -> object:
    if isinstance(option, Mapping):
        for name in names:
            value = option.get(name)
            if value is not None:
                return value
        return default
    return _field(option, *names, default=default)


def _option_rows(options: object) -> Iterable[object]:
    if options is None:
        return ()
    source = options
    all_method = getattr(source, "all", None)
    if callable(all_method):
        source = all_method()
    order_by = getattr(source, "order_by", None)
    if callable(order_by):
        source = order_by("sort_order", "id")
    if isinstance(source, Mapping):
        return (
            {"label": label, "content": content}
            for label, content in source.items()
        )
    if isinstance(source, (str, bytes)):
        return ()
    try:
        return iter(source)
    except TypeError:
        return ()


def _ordered_options(options: object) -> list[dict[str, str]]:
    rows: list[tuple[int, int, int, dict[str, str]]] = []
    for index, option in enumerate(_option_rows(options)):
        label = _text(_option_value(option, "option_label", "label")).strip()
        content = _text(_option_value(option, "content", "text")).strip()
        if not label and not content:
            continue
        normalized_label = label.upper()
        logical_order = ord(normalized_label[0]) - ord("A") if normalized_label else 99
        if logical_order < 0 or logical_order > 25:
            logical_order = 99
        try:
            sort_order = int(_option_value(option, "sort_order", default=index))
        except (TypeError, ValueError):
            sort_order = index
        rows.append(
            (logical_order, sort_order, index, {"label": label, "content": content})
        )
    rows.sort(key=lambda item: item[:3])
    return [item[3] for item in rows]


class QuestionContextBuilder:
    """Create immutable component input from question-model values only."""

    @staticmethod
    def build(
        question: object,
        *,
        image_urls=(),
        normalized_text: str = "",
        vision_result: object = None,
        knowledge_refs: object = "",
        target_mode: str = "",
    ) -> QuestionInput:
        return QuestionInput(
            stem=_text(_field(question, "stem")),
            options=_ordered_options(_field(question, "options", default=())),
            answer=_text(_field(question, "answer")),
            solution=_text(_field(question, "solution", "explanation")),
            image_urls=tuple(_text(url) for url in image_urls if url),
            metadata={
                "reference_analysis": _text(
                    _field(question, "analysis", "explanation")
                ),
                "question_type": _text(
                    _field(question, "question_type", "question_style")
                ),
                "subject": _text(_field(question, "subject")),
                "difficulty": _plain_value(_field(question, "difficulty")),
                "material": _text(_field(question, "material")),
                "tables": _plain_value(_field(question, "tables", default=[])),
                "subquestions": _plain_value(
                    _field(question, "subquestions", default=[])
                ),
                "normalized_text": _text(normalized_text),
                "vision_result": _plain_value(
                    {} if vision_result is None else vision_result
                ),
                "knowledge_refs": _plain_value(knowledge_refs),
                "target_mode": _text(target_mode),
            },
        )


def question_context_payload(
    question_input: QuestionInput, *, include_qwen_result: bool = False
) -> dict[str, object]:
    """Return the complete JSON-safe context shared by solvers and verifiers."""
    metadata = question_input.metadata
    payload = {
        "stem": _text(question_input.stem),
        "options": _ordered_options(question_input.options),
        "reference_answer": _text(question_input.answer),
        "reference_analysis": _text(
            metadata.get("reference_analysis", metadata.get("analysis", ""))
        ),
        "reference_solution": _text(question_input.solution),
        "question_type": _text(metadata.get("question_type", "")),
        "subject": _text(metadata.get("subject", "")),
        "difficulty": _plain_value(metadata.get("difficulty", "")),
        "material": _text(metadata.get("material", "")),
        "tables": _plain_value(metadata.get("tables", [])),
        "subquestions": _plain_value(metadata.get("subquestions", [])),
        "image_urls": _plain_value(question_input.image_urls),
        "normalized_text": _text(metadata.get("normalized_text", "")),
        "vision_result": _plain_value(metadata.get("vision_result", {})),
        "knowledge_refs": _plain_value(metadata.get("knowledge_refs", "")),
    }
    if include_qwen_result:
        payload["qwen_result"] = _plain_value(metadata.get("qwen_result", {}))
    return payload


def question_context_hash(question_input: QuestionInput) -> str:
    """Return a stable answer-verification identity for immutable question facts."""
    canonical = json.dumps(
        question_context_payload(question_input),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
