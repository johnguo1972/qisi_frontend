"""One auditable ingestion path for normalized JSON and document questions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from apps.parser.models import QuestionContentFingerprint
from apps.parser.question_identity import reserve_content_fingerprint
from apps.study.ingestion import finish_ingestion_batch


@dataclass
class IngestionResult:
    total_read: int = 0
    imported: int = 0
    skipped_existing: int = 0
    skipped_in_package: int = 0
    failed: int = 0
    paper_id: str | None = None
    paper_title: str | None = None
    linked_count: int = 0
    tree_node_id: str | None = None
    errors: list[dict] = field(default_factory=list)
    details: list[dict] = field(default_factory=list)

    def as_dict(self, *, batch, course=None) -> dict:
        return {
            'paper_id': self.paper_id,
            'paper_title': self.paper_title,
            'ingestion_batch_id': str(batch.id),
            'total_read': self.total_read,
            'imported': self.imported,
            'skipped_existing': self.skipped_existing,
            'skipped_in_package': self.skipped_in_package,
            'failed': self.failed,
            'errors': self.failed,
            'error_details': self.errors[:20],
            'details': self.details[:20],
            'course_id': str(course.id) if course else None,
            'tree_node_id': self.tree_node_id,
            'linked_count': self.linked_count,
        }


def _question_data(question):
    if hasattr(question, 'to_ingestion_data'):
        return question.to_ingestion_data()
    return dict(question)


def _preflight_with_asset_retry(legacy, raw_question, assets_dir):
    """Retry one transient filesystem read before recording the candidate failure."""
    for attempt in range(2):
        try:
            return legacy._preflight_question(raw_question, assets_dir)
        except OSError:
            if attempt:
                raise


def ingest_structured_questions(*, questions, paper_info, actor, batch, source_root, course, tree_node):
    """Create canonical questions once and always link resolved questions to a course.

    The legacy JSON import helpers remain the source of truth for formula/media
    handling while this function owns deduplication, counters, paper lifecycle,
    and course links for every structured source.
    """
    # Import lazily: json_import_views delegates here, so importing it at module
    # load time would create a circular import during URL registration.
    from apps.study import json_import_views as legacy

    assets_dir = Path(source_root) if source_root is not None else None
    result = IngestionResult(total_read=len(questions))
    prepared = []
    fingerprints_in_package = set()
    course_question_ids = set()

    for index, incoming in enumerate(questions):
        raw_question = _question_data(incoming)
        try:
            qdata, fingerprint = _preflight_with_asset_retry(legacy, raw_question, assets_dir)
        except Exception as exc:
            result.failed += 1
            result.errors.append(legacy._question_error(raw_question, index, exc))
            continue
        if fingerprint in fingerprints_in_package:
            result.skipped_in_package += 1
            legacy._append_duplicate_detail(
                result.details, source_index=index, category='in_package', fingerprint=fingerprint,
            )
            continue
        fingerprints_in_package.add(fingerprint)
        try:
            registry = legacy._active_fingerprint_or_raise(fingerprint)
        except legacy.FingerprintReservationPendingError as exc:
            result.failed += 1
            result.errors.append(legacy._question_error(raw_question, index, exc))
            continue
        if registry:
            result.skipped_existing += 1
            if course and registry.canonical_question_id:
                course_question_ids.add(registry.canonical_question_id)
            legacy._append_duplicate_detail(
                result.details, source_index=index, category='existing', fingerprint=fingerprint,
                registry=registry,
            )
            continue
        prepared.append((qdata, fingerprint, index))

    paper = None
    for qdata, fingerprint, index in prepared:
        created_paper = False
        created_media_paths = []
        try:
            with transaction.atomic():
                registry, reserved = reserve_content_fingerprint(fingerprint)
                if not reserved:
                    registry = legacy._active_fingerprint_or_raise(fingerprint)
                    if registry:
                        result.skipped_existing += 1
                        if course and registry.canonical_question_id:
                            course_question_ids.add(registry.canonical_question_id)
                        legacy._append_duplicate_detail(
                            result.details, source_index=index, category='existing', fingerprint=fingerprint,
                            registry=registry,
                        )
                        continue
                    raise legacy.FingerprintReservationPendingError(
                        'Fingerprint reservation did not resolve to an active question'
                    )
                if paper is None:
                    paper = legacy._create_json_import_paper(
                        paper_info, actor, paper_info.get('source_file_path', ''),
                    )
                    batch.paper = paper
                    batch.save(update_fields=['paper'])
                    created_paper = True
                question = legacy._import_single_question(
                    qdata, paper, assets_dir, assets_dir, created_media_paths=created_media_paths,
                )
                # Keep the JSON import seam stable for its existing activation
                # failure/cleanup regression while all callers share this flow.
                legacy.activate_content_fingerprint(registry, question)
                result.imported += 1
                if course:
                    course_question_ids.add(question.id)
        except Exception as exc:
            legacy._cleanup_media_paths(created_media_paths)
            if created_paper:
                paper = None
            result.failed += 1
            result.errors.append(legacy._question_error(qdata, index, exc))

    legacy._complete_duplicate_details(result.details)
    if course:
        course_question_ids.update(
            detail['existing_canonical_question_id']
            for detail in result.details
            if detail.get('existing_canonical_question_id')
        )
        linked_tree_node, result.linked_count = legacy._link_questions_to_course(
            course=course, tree_node=tree_node, question_ids=course_question_ids,
        )
        result.tree_node_id = str(linked_tree_node.id) if linked_tree_node else None

    if paper:
        paper.total_questions = result.imported
        paper.save(update_fields=['total_questions'])
        result.paper_id = str(paper.id)
        result.paper_title = paper.title
    finish_ingestion_batch(
        batch,
        total_read=result.total_read,
        created_count=result.imported,
        skipped_existing_count=result.skipped_existing,
        skipped_in_package_count=result.skipped_in_package,
        failed_count=result.failed,
    )
    return result
