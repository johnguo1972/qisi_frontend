"""Import the maintained topic catalog used by the controlled AI probe."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha1
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import KnowledgePoint, KnowledgeTopic, KnowledgeTopicModule


class Command(BaseCommand):
    help = "Import the versioned controlled knowledge-topic catalog."

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="Path to the catalog JSON file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print the import summary without writing data.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        catalog = self._load_catalog(path)
        topics = self._validate_topics(catalog)
        known_modules = self._known_standard_modules()
        self._validate_explicit_modules(topics, known_modules)
        summary = self._build_summary(catalog, topics, known_modules)

        if options["dry_run"]:
            self.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            return

        with transaction.atomic():
            self._write_catalog(catalog, topics, known_modules)

        self.stdout.write(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    @staticmethod
    def _load_catalog(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise CommandError(f"catalog file does not exist: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"catalog file is not valid JSON: {error}") from error
        if not isinstance(value, dict):
            raise CommandError("catalog root must be an object")
        return value

    @staticmethod
    def _validate_topics(catalog: dict[str, Any]) -> list[dict[str, Any]]:
        version = catalog.get("catalog_version")
        raw_topics = catalog.get("topics")
        if not isinstance(version, str) or not version.strip():
            raise CommandError("catalog_version is required")
        if not isinstance(raw_topics, list) or not raw_topics:
            raise CommandError("topics must be a non-empty list")

        valid_subjects = {value for value, _label in KnowledgePoint.SUBJECT_CHOICES}
        valid_stages = {value for value, _label in KnowledgePoint.STAGE_CHOICES}
        seen_ids: set[str] = set()
        topics: list[dict[str, Any]] = []
        for raw in raw_topics:
            if not isinstance(raw, dict):
                raise CommandError("each topic must be an object")
            topic_id = raw.get("id")
            subject = raw.get("subject")
            stage = raw.get("stage")
            name = raw.get("name")
            if not all(isinstance(item, str) and item.strip() for item in (topic_id, subject, stage, name)):
                raise CommandError("topic id, subject, stage and name are required")
            if topic_id in seen_ids:
                raise CommandError(f"duplicate topic id: {topic_id}")
            if subject not in valid_subjects or stage not in valid_stages:
                raise CommandError(f"invalid topic scope: {topic_id}")
            parent_id = raw.get("parent_id")
            if parent_id is not None and not isinstance(parent_id, str):
                raise CommandError(f"invalid parent_id: {topic_id}")
            modules = raw.get("modules", [])
            keywords = raw.get("chapter_keywords", [])
            if not isinstance(modules, list) or not all(isinstance(item, str) for item in modules):
                raise CommandError(f"invalid modules: {topic_id}")
            if not isinstance(keywords, list) or not all(isinstance(item, str) and item.strip() for item in keywords):
                raise CommandError(f"invalid chapter_keywords: {topic_id}")
            seen_ids.add(topic_id)
            topics.append({
                "id": topic_id,
                "subject": subject,
                "stage": stage,
                "parent_id": parent_id,
                "name": name,
                "sort_order": int(raw.get("sort_order", 0)),
                "is_enabled": bool(raw.get("is_enabled", True)),
                "modules": [str(item) for item in modules],
                "chapter_keywords": keywords,
                "catch_all": bool(raw.get("catch_all", False)),
            })
        parent_ids = {topic["parent_id"] for topic in topics if topic["parent_id"]}
        unknown_parent_ids = parent_ids - seen_ids
        if unknown_parent_ids:
            raise CommandError(f"unknown parent topic ids: {sorted(unknown_parent_ids)}")
        return topics

    @staticmethod
    def _known_standard_modules() -> set[str]:
        return {
            str(module)
            for module in KnowledgePoint.objects.values_list("module", flat=True).distinct()
        }

    @staticmethod
    def _validate_explicit_modules(topics: list[dict[str, Any]], known_modules: set[str]) -> None:
        requested = {
            module
            for topic in topics
            for module in topic["modules"]
        }
        unknown = sorted(requested - known_modules)
        if unknown:
            raise CommandError(
                "unknown standard knowledge point modules: " + ", ".join(unknown)
            )

    def _build_summary(
        self,
        catalog: dict[str, Any],
        topics: list[dict[str, Any]],
        known_modules: set[str],
    ) -> dict[str, Any]:
        matched = self._dynamic_topic_modules(topics)
        linked_modules = {
            *(
                module
                for topic in topics
                for module in topic["modules"]
            ),
            *(module for modules in matched.values() for module in modules),
        }
        return {
            "catalog_version": catalog["catalog_version"],
            "topics": len(topics),
            "chapter_leaf_topics": len(matched),
            "modules": len(linked_modules),
            "uncovered_modules": len(known_modules - linked_modules),
            "invalid_ids": [],
        }

    def _dynamic_topic_modules(self, topics: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
        """Map each standard module to exactly one configured chapter leaf."""
        rules: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for topic in topics:
            if topic["chapter_keywords"] or topic["catch_all"]:
                rules[(topic["subject"], topic["stage"])].append(topic)

        grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        grouped_modules: dict[tuple[str, str], set[str]] = defaultdict(set)
        for point in KnowledgePoint.objects.values("subject", "stage", "chapter", "module"):
            scope = (point["subject"], point["stage"])
            candidates = rules.get(scope, [])
            chapter = str(point["chapter"] or "")
            ranked_rules = []
            for rule in candidates:
                matches = [
                    (len(keyword), -chapter.index(keyword))
                    for keyword in rule["chapter_keywords"]
                    if keyword in chapter
                ]
                if not matches:
                    continue
                longest_and_earliest = max(matches)
                total_specificity = sum(length for length, _position in matches)
                ranked_rules.append(
                    (
                        (*longest_and_earliest, total_specificity, -rule["sort_order"]),
                        rule,
                    )
                )
            matched_rule = (
                max(ranked_rules, key=lambda item: item[0])[1]
                if ranked_rules
                else None
            )
            if matched_rule is None:
                matched_rule = next((rule for rule in candidates if rule["catch_all"]), None)
            if matched_rule is None:
                continue
            grouped_modules[(matched_rule["id"], chapter)].add(str(point["module"]))
        return {
            key: sorted(modules)
            for key, modules in grouped_modules.items()
        }

    @staticmethod
    def _chapter_leaf_id(topic_id: str, chapter: str) -> str:
        digest = sha1(chapter.encode("utf-8")).hexdigest()[:12]
        return f"{topic_id}--chapter-{digest}"

    def _write_catalog(
        self,
        catalog: dict[str, Any],
        topics: list[dict[str, Any]],
        known_modules: set[str],
    ) -> None:
        by_id = {topic["id"]: topic for topic in topics}
        written: dict[str, KnowledgeTopic] = {}

        def write_topic(topic_id: str) -> KnowledgeTopic:
            if topic_id in written:
                return written[topic_id]
            data = by_id[topic_id]
            parent = write_topic(data["parent_id"]) if data["parent_id"] else None
            topic, _created = KnowledgeTopic.objects.update_or_create(
                id=data["id"],
                defaults={
                    "subject": data["subject"],
                    "stage": data["stage"],
                    "parent": parent,
                    "name": data["name"],
                    "sort_order": data["sort_order"],
                    "is_enabled": data["is_enabled"],
                    "catalog_version": catalog["catalog_version"],
                },
            )
            written[topic_id] = topic
            self._replace_modules(topic, data["modules"])
            return topic

        for topic in topics:
            write_topic(topic["id"])

        dynamic_modules = self._dynamic_topic_modules(topics)
        desired_leaf_ids = set()
        for (root_id, chapter), modules in dynamic_modules.items():
            root = written[root_id]
            leaf_id = self._chapter_leaf_id(root_id, chapter)
            desired_leaf_ids.add(leaf_id)
            leaf, _created = KnowledgeTopic.objects.update_or_create(
                id=leaf_id,
                defaults={
                    "subject": root.subject,
                    "stage": root.stage,
                    "parent": root,
                    "name": chapter,
                    "sort_order": 0,
                    "is_enabled": root.is_enabled,
                    "catalog_version": catalog["catalog_version"],
                },
            )
            self._replace_modules(leaf, modules)

        owned_parent_ids = {
            topic["id"]
            for topic in topics
            if topic["chapter_keywords"] or topic["catch_all"]
        }
        protected_ids = set(by_id) | desired_leaf_ids
        KnowledgeTopic.objects.filter(parent_id__in=owned_parent_ids).exclude(
            id__in=protected_ids
        ).delete()

    @staticmethod
    def _replace_modules(topic: KnowledgeTopic, modules: list[str]) -> None:
        KnowledgeTopicModule.objects.filter(topic=topic).delete()
        KnowledgeTopicModule.objects.bulk_create([
            KnowledgeTopicModule(
                topic=topic,
                module=module,
                sort_order=index,
            )
            for index, module in enumerate(dict.fromkeys(modules))
        ])
