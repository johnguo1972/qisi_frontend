"""Read and validate the controlled topic catalog for AI probe stages."""

from __future__ import annotations

from collections.abc import Iterable

from apps.knowledge.models import KnowledgePoint, KnowledgeTopic, KnowledgeTopicModule


class ControlledCatalogSelectionError(ValueError):
    """Raised when an AI response escapes its supplied controlled candidates."""


def _topic_payload(topic: KnowledgeTopic) -> dict[str, object]:
    return {
        "id": str(topic.id),
        "name": topic.name,
        "subject": topic.subject,
        "stage": topic.stage,
        "path_ids": topic.path_ids,
    }


def root_topic_candidates() -> list[dict[str, object]]:
    """Return the selectable first-level themes across enabled subject scopes."""
    return [
        _topic_payload(topic)
        for topic in KnowledgeTopic.objects.filter(
            parent__isnull=True,
            is_enabled=True,
        )
    ]


def child_topic_candidates(topic_id: str) -> list[dict[str, object]]:
    """Return selectable enabled child topics for an already selected topic."""
    return [
        _topic_payload(topic)
        for topic in KnowledgeTopic.objects.filter(
            parent_id=str(topic_id),
            is_enabled=True,
        )
    ]


def leaf_knowledge_candidates(topic_id: str) -> list[dict[str, str]]:
    """Return standard module candidates linked to one selected leaf topic."""
    topic = KnowledgeTopic.objects.filter(
        id=str(topic_id),
        is_enabled=True,
    ).first()
    if topic is None:
        return []
    links = list(
        KnowledgeTopicModule.objects.filter(
            topic_id=str(topic_id),
            is_enabled=True,
        ).order_by("sort_order", "id")
    )
    if not links:
        return []
    modules = [link.module for link in links]
    points_by_module = {}
    for point in KnowledgePoint.objects.filter(
        subject=topic.subject,
        stage=topic.stage,
        chapter=topic.name,
        module__in=modules,
    ).order_by("id"):
        points_by_module.setdefault(point.module, point)
    return [
        {
            "id": module,
            "module": module,
            "chapter": points_by_module[module].chapter,
            "full_label": points_by_module[module].full_label,
        }
        for module in modules
        if module in points_by_module
    ]


def validate_selected_ids(
    candidate_ids: Iterable[str],
    selected_ids: Iterable[str],
    maximum: int = 5,
) -> list[str]:
    """Validate ordered AI-selected IDs against the exact prompt candidate set."""
    candidates = {str(item) for item in candidate_ids if str(item).strip()}
    selected = [str(item).strip() for item in selected_ids if str(item).strip()]
    if not 1 <= len(selected) <= maximum:
        raise ControlledCatalogSelectionError(
            f"selected knowledge module count must be between 1 and {maximum}"
        )
    if len(selected) != len(set(selected)):
        raise ControlledCatalogSelectionError("selected knowledge modules must be unique")
    outside = [item for item in selected if item not in candidates]
    if outside:
        raise ControlledCatalogSelectionError(
            f"selected knowledge modules outside supplied candidates: {outside}"
        )
    return selected
