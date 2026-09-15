"""Celery consumer for persistent PDF/DOCX course import tasks."""

from __future__ import annotations

import re
import hashlib
import shutil
from pathlib import Path
from zipfile import ZipFile

import fitz

from celery import shared_task
from django.conf import settings

from apps.common.ai.exceptions import AIResponseError
from apps.common.exceptions import AIRequestError
from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.document_import_service import document_source_fingerprint, extract_document
from apps.study.document_structure_ai import structure_candidate
from apps.parser.models import QuestionDocumentSourceFingerprint
from apps.study.ingestion import finish_ingestion_batch
from apps.study.structured_ingestion import ingest_structured_questions


LOCAL_PATH = re.compile(r'(?:(?:[A-Za-z]:)?[\\/][^\s,;:]+)+')


def _redacted_error(error) -> str:
    return LOCAL_PATH.sub('[path hidden]', str(error))[:200] or 'document import processing failed'


def _set_stage(task, stage, progress, *, error_summary=None, linked_count=None):
    task.stage = stage
    task.progress = progress
    fields = ['stage', 'progress', 'updated_at']
    if error_summary is not None:
        task.error_summary = error_summary[:1000]
        fields.append('error_summary')
    if linked_count is not None:
        task.linked_count = linked_count
        fields.append('linked_count')
    task.save(update_fields=fields)


def _asset_filename(reference, suffix):
    digest = hashlib.sha256(reference.encode('utf-8')).hexdigest()[:16]
    normalized_suffix = suffix.lower() if suffix and suffix.startswith('.') else '.bin'
    return f'document-{digest}{normalized_suffix}'


def _materialize_candidate_assets(source_path, candidate, asset_root):
    """Export only the candidate's declared PDF/DOCX internal images to source_root."""
    asset_files = {}
    references = {asset.reference for asset in candidate.asset_refs}
    if not references:
        return asset_files
    asset_root.mkdir(parents=True, exist_ok=True)
    if source_path.suffix.lower() == '.pdf':
        with fitz.open(source_path) as document:
            for reference in references:
                if not reference.startswith('pdf:'):
                    raise ValueError('invalid PDF asset reference')
                try:
                    xref = int(reference.split(':', 1)[1])
                    extracted = document.extract_image(xref)
                    content = extracted['image']
                except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                    raise OSError('unable to read PDF image asset') from exc
                filename = _asset_filename(reference, f".{extracted.get('ext', 'bin')}")
                (asset_root / filename).write_bytes(content)
                asset_files[reference] = filename
        return asset_files

    if source_path.suffix.lower() == '.docx':
        with ZipFile(source_path) as archive:
            for reference in references:
                member = reference.removeprefix('docx:').lstrip('/')
                if not reference.startswith('docx:') or not member.startswith('word/media/') or '..' in Path(member).parts:
                    raise ValueError('invalid DOCX asset reference')
                try:
                    content = archive.read(member)
                except KeyError as exc:
                    raise OSError('unable to read DOCX image asset') from exc
                filename = _asset_filename(reference, Path(member).suffix)
                (asset_root / filename).write_bytes(content)
                asset_files[reference] = filename
        return asset_files
    raise ValueError('unsupported document asset source')


@shared_task(bind=True, name='apps.study.document_import_tasks.process_document_import_task', max_retries=0)
def process_document_import_task(self, task_id):
    """Extract, structure and ingest a document while preserving partial progress."""
    del self
    task = QuestionDocumentImportTask.objects.select_related('batch__actor', 'course').get(pk=task_id)
    asset_root = None
    try:
        _set_stage(task, QuestionDocumentImportTask.Stage.EXTRACTING, 5)
        source_path = Path(task.source_file)
        if not source_path.is_absolute():
            source_path = Path(settings.MEDIA_ROOT) / source_path
        extracted = extract_document(source_path)
        asset_root = Path(settings.MEDIA_ROOT) / 'temp_document_assets' / str(task.id)
        _set_stage(task, QuestionDocumentImportTask.Stage.STRUCTURING, 20)

        valid = []
        failures = []
        total = len(extracted.fragments)
        for index, candidate in enumerate(extracted.fragments):
            try:
                source_fingerprint = document_source_fingerprint(candidate)
                existing = QuestionDocumentSourceFingerprint.objects.filter(
                    fingerprint=source_fingerprint,
                ).values_list('canonical_question_id', flat=True).first()
                if existing:
                    valid.append({
                        '_document_source_fingerprint': source_fingerprint,
                        '_source_document_question_no': candidate.question_no,
                        '_existing_canonical_question_id': str(existing),
                    })
                    _set_stage(task, QuestionDocumentImportTask.Stage.STRUCTURING, 20 + int(45 * (index + 1) / max(total, 1)))
                    continue
                asset_files = _materialize_candidate_assets(source_path, candidate, asset_root)
                structured = structure_candidate(candidate, asset_files=asset_files)
                structured = structured.to_ingestion_data() if hasattr(structured, 'to_ingestion_data') else dict(structured)
                structured['_document_source_fingerprint'] = source_fingerprint
                structured['_source_document_question_no'] = candidate.question_no
                valid.append(structured)
            except (AIResponseError, AIRequestError, ValueError, OSError) as exc:
                failures.append(_redacted_error(exc))
            _set_stage(task, QuestionDocumentImportTask.Stage.STRUCTURING, 20 + int(45 * (index + 1) / max(total, 1)))

        _set_stage(task, QuestionDocumentImportTask.Stage.IMPORTING, 70)
        result = ingest_structured_questions(
            questions=valid,
            paper_info={
                'title': f'Document import - {task.course.name}',
                'subject': task.course.subject,
                'grade': task.course.grade_level,
                'source_file_path': task.source_file,
            },
            actor=task.batch.actor,
            batch=task.batch,
            source_root=asset_root,
            course=task.course,
            tree_node=task.tree_node,
        )
        failed_count = result.failed + len(failures)
        finish_ingestion_batch(
            task.batch,
            total_read=total,
            created_count=result.imported,
            skipped_existing_count=result.skipped_existing,
            skipped_in_package_count=result.skipped_in_package,
            failed_count=failed_count,
        )
        summaries = failures + [item['error'] for item in result.errors]
        completed = result.imported + result.skipped_existing + result.skipped_in_package
        stage = (
            QuestionDocumentImportTask.Stage.SUCCESS if not failed_count else
            QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS if completed else
            QuestionDocumentImportTask.Stage.FAILED
        )
        _set_stage(task, stage, 100, error_summary='; '.join(summaries), linked_count=result.linked_count)
        return {'task_id': str(task.id), 'stage': stage, **result.as_dict(batch=task.batch, course=task.course)}
    except Exception as exc:
        finish_ingestion_batch(
            task.batch, total_read=task.batch.total_read, created_count=task.batch.created_count,
            skipped_existing_count=task.batch.skipped_existing_count,
            skipped_in_package_count=task.batch.skipped_in_package_count,
            failed_count=max(1, task.batch.failed_count),
        )
        _set_stage(task, QuestionDocumentImportTask.Stage.FAILED, 100, error_summary=_redacted_error(exc))
        raise
    finally:
        if asset_root is not None:
            shutil.rmtree(asset_root, ignore_errors=True)
