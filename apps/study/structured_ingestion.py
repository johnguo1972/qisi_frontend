"""One auditable ingestion path for normalized JSON and document questions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from apps.parser.models import QuestionContentFingerprint, QuestionDocumentSourceFingerprint
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


def _backfill_existing_assets(legacy, question, qdata, assets_dir):
    """Attach document assets absent from a deduplicated canonical question."""
    if assets_dir is None or not question.paper_id:
        return
    for image_type, field_name in (("illustration", "illustrations"), ("formula", "formula_assets")):
        for sort_order, asset in enumerate(qdata.get(field_name, []) or []):
            filename = os.path.basename(str(asset.get("file", "")))
            if not filename:
                continue
            if legacy.QuestionImage.objects.filter(
                question=question,
                image_type=image_type,
                original_file_path__endswith=f"_{filename}",
            ).exists():
                continue
            legacy._import_asset_image(
                asset, question, question.paper, assets_dir, image_type, sort_order,
            )


def ingest_structured_questions(
    *, questions, paper_info, actor, batch, source_root, course, tree_node,
    document_import_task=None,
):
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
    source_document_question_nos = {}
    source_references_by_content_fingerprint = {}
    resolved_source_references = []

    def resolve_source_references(content_fingerprint, canonical_question_id):
        """Bind every physical source position for one normalized question."""
        for source_reference in source_references_by_content_fingerprint.pop(content_fingerprint, []):
            if source_reference:
                resolved_source_references.append({
                    **source_reference,
                    'canonical_question_id': str(canonical_question_id),
                })

    for index, incoming in enumerate(questions):
        raw_question = _question_data(incoming)
        existing_canonical_question_id = raw_question.pop('_existing_canonical_question_id', None)
        document_fingerprint = raw_question.pop('_document_source_fingerprint', None)
        source_document_question_no = raw_question.pop('_source_document_question_no', None)
        source_reference = raw_question.pop('_source_document_reference', None)
        if existing_canonical_question_id:
            result.skipped_existing += 1
            course_question_ids.add(existing_canonical_question_id)
            source_document_question_nos.setdefault(str(existing_canonical_question_id), source_document_question_no)
            if source_reference:
                resolved_source_references.append({
                    **source_reference,
                    'canonical_question_id': str(existing_canonical_question_id),
                })
            continue
        try:
            qdata, fingerprint = _preflight_with_asset_retry(legacy, raw_question, assets_dir)
        except Exception as exc:
            result.failed += 1
            result.errors.append(legacy._question_error(raw_question, index, exc))
            continue
        if source_reference:
            source_references_by_content_fingerprint.setdefault(fingerprint, []).append(source_reference)
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
                _backfill_existing_assets(legacy, registry.canonical_question, qdata, assets_dir)
                course_question_ids.add(registry.canonical_question_id)
                source_document_question_nos.setdefault(str(registry.canonical_question_id), source_document_question_no)
                resolve_source_references(fingerprint, registry.canonical_question_id)
            if document_fingerprint and registry.canonical_question_id:
                QuestionDocumentSourceFingerprint.objects.update_or_create(
                    fingerprint=document_fingerprint,
                    defaults={'canonical_question_id': registry.canonical_question_id},
                )
            legacy._append_duplicate_detail(
                result.details, source_index=index, category='existing', fingerprint=fingerprint,
                registry=registry,
            )
            continue
        prepared.append((qdata, fingerprint, index, source_document_question_no, document_fingerprint))

    paper = None
    for qdata, fingerprint, index, source_document_question_no, document_fingerprint in prepared:
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
                            _backfill_existing_assets(legacy, registry.canonical_question, qdata, assets_dir)
                            course_question_ids.add(registry.canonical_question_id)
                            source_document_question_nos.setdefault(str(registry.canonical_question_id), source_document_question_no)
                            resolve_source_references(fingerprint, registry.canonical_question_id)
                        if document_fingerprint and registry.canonical_question_id:
                            QuestionDocumentSourceFingerprint.objects.update_or_create(
                                fingerprint=document_fingerprint,
                                defaults={'canonical_question_id': registry.canonical_question_id},
                            )
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
                if document_fingerprint:
                    QuestionDocumentSourceFingerprint.objects.update_or_create(
                        fingerprint=document_fingerprint,
                        defaults={'canonical_question': question},
                    )
                result.imported += 1
                if course:
                    course_question_ids.add(question.id)
                    source_document_question_nos.setdefault(str(question.id), source_document_question_no)
                    resolve_source_references(fingerprint, question.id)
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
            source_document_question_nos=source_document_question_nos,
        )
        result.tree_node_id = str(linked_tree_node.id) if linked_tree_node else None
        if document_import_task and resolved_source_references:
            from apps.courses.models import CourseQuestionDocumentReference, CourseQuestionLink

            links_by_question_id = {
                str(link.question_id): link
                for link in CourseQuestionLink.objects.filter(
                    course=course,
                    question_id__in={item['canonical_question_id'] for item in resolved_source_references},
                )
            }
            for item in resolved_source_references:
                link = links_by_question_id.get(item['canonical_question_id'])
                if not link:
                    continue
                CourseQuestionDocumentReference.objects.update_or_create(
                    document_import_task=document_import_task,
                    source_position=item['position'],
                    defaults={
                        'course_question_link': link,
                        'source_fingerprint': item['fingerprint'],
                        'source_question_no': item.get('question_no', ''),
                        'source_page_start': item.get('page_start'),
                        'source_page_end': item.get('page_end'),
                        'source_section_path': item.get('section_path', ''),
                        'source_locator': item['locator'],
                    },
                )

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
