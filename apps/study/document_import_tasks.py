"""Celery consumer for persistent PDF/DOCX course import tasks."""

from __future__ import annotations

import re
import hashlib
import shutil
from pathlib import Path
from zipfile import ZipFile
from types import SimpleNamespace

import fitz

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.ai.exceptions import AIResponseError
from apps.common.exceptions import AIRequestError
from apps.study.document_import_models import QuestionDocumentImportItem, QuestionDocumentImportTask
from apps.study.document_import_service import (
    DocumentAssetRef, ExtractedQuestionFragment, document_source_fingerprint, extract_document,
)
from apps.study.document_structure_ai import structure_candidate
from apps.study.ingestion import finish_ingestion_batch
from apps.study.structured_ingestion import ingest_structured_questions


LOCAL_PATH = re.compile(r'(?:(?:[A-Za-z]:)?[\\/][^\s,;:]+)+')


def _redacted_error(error) -> str:
    return LOCAL_PATH.sub('[path hidden]', str(error))[:200] or 'document import processing failed'


def _friendly_error_label(error) -> str:
    """Return a short, safe label suitable for the import-history popup."""
    message = str(error or '')
    if re.search(r'timed out|timeout|超时', message, re.IGNORECASE):
        return 'AI响应超时'
    if re.search(r'not valid json|invalid json|json|schema|格式错误|response content is missing|结构化', message, re.IGNORECASE):
        return 'AI返回格式错误'
    if re.search(r'credential|api[_ -]?key|配置', message, re.IGNORECASE):
        return 'AI配置错误'
    if isinstance(error, OSError) or re.search(r'asset|image|图片|资源', message, re.IGNORECASE):
        return '题目资源处理失败'
    return '题目处理失败'


def _question_error(question_no, error) -> str:
    label = _friendly_error_label(error)
    question = str(question_no or '').strip()
    return f'第{question}题：{label}' if question and question != '未知' else label


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


def _source_document_reference(candidate, position):
    """Persist a collision-safe locator, not just the printed question label."""
    page_start, page_end = candidate.page_range
    paragraph_index = candidate.source_paragraph_index
    section_path = (candidate.section_path or '').strip()[:500]
    position_part = f'paragraph-{paragraph_index}' if paragraph_index else f'fragment-{position}'
    path = section_path or ('pdf' if paragraph_index is None else 'document-body')
    locator = f'{path}/{position_part}/pages-{page_start}-{page_end}/question-{candidate.question_no}'
    return {
        'fingerprint': document_source_fingerprint(candidate),
        'position': position,
        'question_no': str(candidate.question_no),
        'page_start': page_start,
        'page_end': page_end,
        'section_path': section_path,
        'locator': locator[:700],
    }


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


def _run_document_import_sync(task_id):
    """Extract, structure and ingest a document while preserving partial progress."""
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
                source_reference = _source_document_reference(candidate, index + 1)
                asset_files = _materialize_candidate_assets(source_path, candidate, asset_root)
                structured = structure_candidate(candidate, asset_files=asset_files)
                structured = structured.to_ingestion_data() if hasattr(structured, 'to_ingestion_data') else dict(structured)
                structured['_document_source_fingerprint'] = source_reference['fingerprint']
                structured['_source_document_question_no'] = candidate.question_no
                structured['_source_document_reference'] = source_reference
                valid.append(structured)
            except (AIResponseError, AIRequestError, ValueError, OSError) as exc:
                failures.append(_question_error(candidate.question_no, exc))
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
            # The wrong-drill source must remain isolated from the classroom
            # workbook/course links. Ordinary imports keep the old linkage.
            course=task.course if task.import_purpose != 'wrongbook_drill' else None,
            tree_node=task.tree_node if task.import_purpose != 'wrongbook_drill' else None,
            document_import_task=task,
        )
        if task.import_purpose == 'wrongbook_drill' and task.wrong_drill_source_set_id:
            from apps.missions.classroom_wrong_drill_service import finalize_source_import
            finalize_source_import(task.wrong_drill_source_set_id, valid, result)
        failed_count = result.failed + len(failures)
        finish_ingestion_batch(
            task.batch,
            total_read=total,
            created_count=result.imported,
            skipped_existing_count=result.skipped_existing,
            skipped_in_package_count=result.skipped_in_package,
            failed_count=failed_count,
        )
        summaries = failures + [_question_error(item.get('question_no'), item.get('error')) for item in result.errors]
        completed = result.imported + result.skipped_existing + result.skipped_in_package
        stage = (
            QuestionDocumentImportTask.Stage.SUCCESS if not failed_count else
            QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS if completed else
            QuestionDocumentImportTask.Stage.FAILED
        )
        _set_stage(task, stage, 100, error_summary='; '.join(summaries), linked_count=result.linked_count)
        return {'task_id': str(task.id), 'stage': stage, **result.as_dict(batch=task.batch, course=task.course)}
    except Exception as exc:
        if task.import_purpose == 'wrongbook_drill' and task.wrong_drill_source_set_id:
            from apps.missions.models import ClassroomWrongDrillSourceSet
            ClassroomWrongDrillSourceSet.objects.filter(pk=task.wrong_drill_source_set_id).update(
                status='failed', error_summary=_redacted_error(exc), updated_at=timezone.now(),
            )
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


def _document_asset_root(task):
    return Path(settings.MEDIA_ROOT) / 'temp_document_assets' / str(task.id)


def _document_source_path(task):
    source_path = Path(task.source_file)
    return source_path if source_path.is_absolute() else Path(settings.MEDIA_ROOT) / source_path


def _document_file_fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_to_json(candidate):
    return {
        'question_no': str(candidate.question_no),
        'text': candidate.text,
        'tables': candidate.tables,
        'page_start': candidate.page_range[0],
        'page_end': candidate.page_range[1],
        'source_paragraph_index': candidate.source_paragraph_index,
        'section_path': candidate.section_path,
        'asset_refs': [
            {
                'reference': asset.reference,
                'page_no': asset.page_no,
                'bbox': list(asset.bbox) if asset.bbox is not None else None,
            }
            for asset in candidate.asset_refs
        ],
    }


def _candidate_from_json(payload):
    return ExtractedQuestionFragment(
        question_no=str(payload.get('question_no', '')).strip(),
        text=str(payload.get('text', '')),
        tables=payload.get('tables') or [],
        page_range=(int(payload.get('page_start', 1)), int(payload.get('page_end', 1))),
        source_paragraph_index=payload.get('source_paragraph_index'),
        section_path=str(payload.get('section_path', '') or ''),
        asset_refs=[
            DocumentAssetRef(
                reference=str(item.get('reference', '')),
                page_no=item.get('page_no'),
                bbox=tuple(item['bbox']) if item.get('bbox') is not None else None,
            )
            for item in payload.get('asset_refs', [])
            if item.get('reference')
        ],
    )


def _document_paper_info(task):
    return {
        'title': f'Document import - {task.course.name}',
        'subject': task.course.subject,
        'grade': task.course.grade_level,
        'source_file_path': task.source_file,
    }


def _touch_document_task(task, *, stage=None, progress=None):
    if stage is not None:
        task.stage = stage
    if progress is not None:
        task.progress = progress
    task.last_heartbeat_at = timezone.now()
    fields = ['last_heartbeat_at', 'updated_at']
    if stage is not None:
        fields.append('stage')
    if progress is not None:
        fields.append('progress')
    task.save(update_fields=fields)


def _prepare_document_import(task):
    """Persist candidates before dispatching any cross-process work."""
    source_path = _document_source_path(task)
    extracted = extract_document(source_path)
    asset_root = _document_asset_root(task)
    asset_root.mkdir(parents=True, exist_ok=True)
    task.document_fingerprint = _document_file_fingerprint(source_path)
    task.candidate_count = len(extracted.fragments)
    _touch_document_task(task, stage=QuestionDocumentImportTask.Stage.STRUCTURING, progress=20)

    for index, candidate in enumerate(extracted.fragments, start=1):
        source_reference = _source_document_reference(candidate, index)
        asset_files = _materialize_candidate_assets(source_path, candidate, asset_root)
        defaults = {
            'question_no': str(candidate.question_no),
            'source_fingerprint': source_reference['fingerprint'],
            'candidate_json': _candidate_to_json(candidate),
            'asset_files_json': asset_files,
        }
        item, created = QuestionDocumentImportItem.objects.get_or_create(
            document_import_task=task,
            source_position=index,
            defaults=defaults,
        )
        if not created:
            # A resumed task keeps completed results, while refreshing only the
            # immutable source payload if the extraction algorithm produced it.
            changed = []
            for field, value in defaults.items():
                if getattr(item, field) != value and item.status not in {
                    QuestionDocumentImportItem.Status.RUNNING,
                    QuestionDocumentImportItem.Status.SUCCESS,
                }:
                    setattr(item, field, value)
                    changed.append(field)
            if changed:
                item.save(update_fields=changed + ['updated_at'])
        if index % 10 == 0 or index == len(extracted.fragments):
            _touch_document_task(
                task,
                stage=QuestionDocumentImportTask.Stage.STRUCTURING,
                progress=20 + int(5 * index / max(len(extracted.fragments), 1)),
            )

    if not task.batch.paper_id:
        from apps.study import json_import_views as legacy
        paper = legacy._create_json_import_paper(
            _document_paper_info(task), task.batch.actor, task.source_file,
        )
        task.batch.paper = paper
        task.batch.save(update_fields=['paper'])
    task.save(update_fields=['document_fingerprint', 'candidate_count', 'updated_at'])


def _schedule_document_finalizer(task_id, countdown=5):
    try:
        finalize_document_import_task.apply_async(args=(str(task_id),), countdown=countdown)
    except Exception:
        # The recovery beat will schedule it again. A broker outage must not
        # turn a successfully persisted question into a failed import.
        return False
    return True


def _dispatch_pending_document_items(task_id):
    """Dispatch a bounded window and leave the rest durably pending."""
    window = max(1, int(getattr(settings, 'DOCUMENT_IMPORT_DISPATCH_WINDOW', 24)))
    active_statuses = (
        QuestionDocumentImportItem.Status.DISPATCHED,
        QuestionDocumentImportItem.Status.RUNNING,
    )
    active_count = QuestionDocumentImportItem.objects.filter(
        document_import_task_id=task_id, status__in=active_statuses,
    ).count()
    available = max(0, window - active_count)
    if not available:
        return 0
    pending = list(
        QuestionDocumentImportItem.objects.filter(
            document_import_task_id=task_id,
            status=QuestionDocumentImportItem.Status.PENDING,
        ).order_by('source_position').values_list('id', flat=True)[:available]
    )
    dispatched = 0
    for item_id in pending:
        updated = QuestionDocumentImportItem.objects.filter(
            pk=item_id, status=QuestionDocumentImportItem.Status.PENDING,
        ).update(
            status=QuestionDocumentImportItem.Status.DISPATCHED,
            worker_heartbeat_at=timezone.now(),
            updated_at=timezone.now(),
        )
        if not updated:
            continue
        try:
            result = process_document_import_item_task.apply_async(args=(str(item_id),))
        except Exception:
            QuestionDocumentImportItem.objects.filter(
                pk=item_id, status=QuestionDocumentImportItem.Status.DISPATCHED,
            ).update(status=QuestionDocumentImportItem.Status.PENDING, updated_at=timezone.now())
            continue
        QuestionDocumentImportItem.objects.filter(pk=item_id).update(
            celery_task_id=str(getattr(result, 'id', '') or ''), updated_at=timezone.now(),
        )
        dispatched += 1
    return dispatched


def _safe_item_failure(error):
    return _friendly_error_label(error), _redacted_error(error)


def _retryable_document_error(error):
    if isinstance(error, AIRequestError):
        return bool(re.search(
            r'timed out|timeout|tempor|capacity|provider request',
            str(error), re.IGNORECASE,
        ))
    return 'fingerprint' in str(error).lower() and 'reserved' in str(error).lower()


def _schedule_item_retry(item, error, *, ingest=False):
    max_attempts = max(0, int(getattr(settings, 'DOCUMENT_IMPORT_MAX_RETRIES', 2)))
    if item.retry_count >= max_attempts:
        return False
    item.retry_count += 1
    item.status = QuestionDocumentImportItem.Status.RETRYING
    if ingest:
        item.ingest_status = QuestionDocumentImportItem.IngestStatus.FAILED
        item.ingest_error_code, item.ingest_error_message_safe = _safe_item_failure(error)
    else:
        item.error_code, item.error_message_safe = _safe_item_failure(error)
    item.save(update_fields=[
        'retry_count', 'status', 'ingest_status', 'error_code', 'error_message_safe',
        'ingest_error_code', 'ingest_error_message_safe', 'updated_at',
    ])
    delay = min(60, 2 ** min(item.retry_count - 1, 5))
    try:
        result = process_document_import_item_task.apply_async(
            args=(str(item.id),), countdown=delay,
        )
    except Exception:
        # Never leave an item in RETRYING when the broker is unavailable.
        item.status = (
            QuestionDocumentImportItem.Status.SUCCESS
            if ingest and item.structured_result_json
            else QuestionDocumentImportItem.Status.FAILED
        )
        item.completed_at = timezone.now()
        item.save(update_fields=['status', 'completed_at', 'updated_at'])
        return False
    QuestionDocumentImportItem.objects.filter(pk=item.id).update(
        celery_task_id=str(getattr(result, 'id', '') or ''), updated_at=timezone.now(),
    )
    return True


def _ingest_document_item(item, task):
    structured = dict(item.structured_result_json or {})
    source_reference = structured.get('_source_document_reference')
    if source_reference is None:
        candidate = item.candidate_json or {}
        source_reference = _source_document_reference(
            _candidate_from_json(candidate), item.source_position,
        )
        structured['_document_source_fingerprint'] = item.source_fingerprint
        structured['_source_document_question_no'] = item.question_no
        structured['_source_document_reference'] = source_reference
    task.batch.refresh_from_db(fields=['paper_id'])
    if not task.batch.paper_id:
        raise RuntimeError('document import paper is missing')
    result = ingest_structured_questions(
        questions=[structured],
        paper_info=_document_paper_info(task),
        actor=task.batch.actor,
        batch=task.batch,
        source_root=_document_asset_root(task),
        course=task.course if task.import_purpose != 'wrongbook_drill' else None,
        tree_node=task.tree_node if task.import_purpose != 'wrongbook_drill' else None,
        document_import_task=task,
        paper=task.batch.paper,
        finalize_batch=False,
    )
    if result.failed:
        raise RuntimeError((result.errors[0] if result.errors else {}).get('error', 'question ingestion failed'))
    existing_canonical_question_ids = [
        detail['existing_canonical_question_id']
        for detail in result.details
        if detail.get('existing_canonical_question_id')
    ]
    return {
        'imported': result.imported,
        'skipped_existing': result.skipped_existing,
        'skipped_in_package': result.skipped_in_package,
        'failed': result.failed,
        'linked_count': result.linked_count,
        'paper_id': result.paper_id,
        'existing_canonical_question_ids': existing_canonical_question_ids,
        'errors': result.errors[:5],
        'details': result.details[:5],
    }


@shared_task(bind=True, name='apps.study.document_import_tasks.process_document_import_task', max_retries=0)
def process_document_import_task(self, task_id):
    """Prepare a durable document import and dispatch bounded question tasks."""
    if getattr(self.request, 'called_directly', False):
        return _run_document_import_sync(task_id)
    task = None
    try:
        # The lock makes duplicate delivery of the parent task idempotent,
        # including the one-paper creation step.
        with transaction.atomic():
            task = QuestionDocumentImportTask.objects.select_for_update().select_related(
                'batch__actor', 'course',
            ).get(pk=task_id)
            if task.stage in {
                QuestionDocumentImportTask.Stage.SUCCESS,
                QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS,
                QuestionDocumentImportTask.Stage.FAILED,
            }:
                return {'task_id': str(task.id), 'stage': task.stage}
            _prepare_document_import(task)
        _touch_document_task(task, stage=QuestionDocumentImportTask.Stage.IMPORTING, progress=30)
        _dispatch_pending_document_items(task.id)
        _schedule_document_finalizer(task.id, countdown=2)
        return {'task_id': str(task.id), 'stage': task.stage, 'candidate_count': task.candidate_count}
    except Exception as exc:
        if task is not None and task.import_purpose == 'wrongbook_drill' and task.wrong_drill_source_set_id:
            from apps.missions.models import ClassroomWrongDrillSourceSet
            ClassroomWrongDrillSourceSet.objects.filter(pk=task.wrong_drill_source_set_id).update(
                status='failed', error_summary=_redacted_error(exc), updated_at=timezone.now(),
            )
        if task is not None:
            finish_ingestion_batch(
                task.batch,
                total_read=task.candidate_count,
                created_count=0,
                skipped_existing_count=0,
                skipped_in_package_count=0,
                failed_count=max(1, task.candidate_count),
            )
            _set_stage(task, QuestionDocumentImportTask.Stage.FAILED, 100, error_summary=_redacted_error(exc))
            shutil.rmtree(_document_asset_root(task), ignore_errors=True)
        raise


@shared_task(bind=True, name='apps.study.document_import_tasks.process_document_import_item_task', max_retries=0)
def process_document_import_item_task(self, item_id):
    """Structure and ingest one candidate; a retry never repeats successful AI."""
    del self
    with transaction.atomic():
        item = QuestionDocumentImportItem.objects.select_for_update().select_related(
            'document_import_task__batch__actor', 'document_import_task__course',
        ).get(pk=item_id)
        if (
            item.status == QuestionDocumentImportItem.Status.SUCCESS
            and item.ingest_status == QuestionDocumentImportItem.IngestStatus.INGESTED
        ):
            return {'item_id': str(item.id), 'status': item.status}
        item.status = QuestionDocumentImportItem.Status.RUNNING
        item.started_at = item.started_at or timezone.now()
        item.worker_heartbeat_at = timezone.now()
        item.save(update_fields=['status', 'started_at', 'worker_heartbeat_at', 'updated_at'])

    task = item.document_import_task
    try:
        if not item.structured_result_json:
            candidate = _candidate_from_json(item.candidate_json)
            asset_files = item.asset_files_json or {}
            structured = structure_candidate(candidate, asset_files=asset_files) if asset_files else structure_candidate(candidate)
            structured = structured.to_ingestion_data() if hasattr(structured, 'to_ingestion_data') else dict(structured)
            source_reference = _source_document_reference(candidate, item.source_position)
            structured['_document_source_fingerprint'] = item.source_fingerprint or source_reference['fingerprint']
            structured['_source_document_question_no'] = candidate.question_no
            structured['_source_document_reference'] = source_reference
            item.structured_result_json = structured
            item.status = QuestionDocumentImportItem.Status.SUCCESS
            item.ingest_status = QuestionDocumentImportItem.IngestStatus.PENDING
            item.worker_heartbeat_at = timezone.now()
            item.save(update_fields=['structured_result_json', 'status', 'ingest_status', 'worker_heartbeat_at', 'updated_at'])

        item.ingest_status = QuestionDocumentImportItem.IngestStatus.INGESTING
        item.save(update_fields=['ingest_status', 'updated_at'])
        ingest_result = _ingest_document_item(item, task)
        item.ingest_result_json = ingest_result
        item.ingest_status = QuestionDocumentImportItem.IngestStatus.INGESTED
        item.status = QuestionDocumentImportItem.Status.SUCCESS
        item.completed_at = timezone.now()
        item.worker_heartbeat_at = item.completed_at
        item.save(update_fields=[
            'ingest_result_json', 'ingest_status', 'status', 'completed_at',
            'worker_heartbeat_at', 'updated_at',
        ])
    except (AIResponseError, AIRequestError, ValueError, OSError) as exc:
        if _retryable_document_error(exc) and _schedule_item_retry(item, exc):
            if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                _schedule_document_finalizer(task.id)
            return {'item_id': str(item.id), 'status': item.status, 'retrying': True}
        item.status = QuestionDocumentImportItem.Status.FAILED
        item.error_code, item.error_message_safe = _safe_item_failure(exc)
        item.completed_at = timezone.now()
        item.worker_heartbeat_at = item.completed_at
        item.save(update_fields=['status', 'error_code', 'error_message_safe', 'completed_at', 'worker_heartbeat_at', 'updated_at'])
    except Exception as exc:
        if item.structured_result_json and _schedule_item_retry(item, exc, ingest=True):
            if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                _schedule_document_finalizer(task.id)
            return {'item_id': str(item.id), 'status': item.status, 'retrying': True}
        item.status = QuestionDocumentImportItem.Status.SUCCESS if item.structured_result_json else QuestionDocumentImportItem.Status.FAILED
        item.ingest_status = QuestionDocumentImportItem.IngestStatus.FAILED
        item.ingest_error_code, item.ingest_error_message_safe = _safe_item_failure(exc)
        item.completed_at = timezone.now()
        item.save(update_fields=[
            'status', 'ingest_status', 'ingest_error_code', 'ingest_error_message_safe',
            'completed_at', 'updated_at',
        ])
    finally:
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            _schedule_document_finalizer(task.id)
    return {'item_id': str(item.id), 'status': item.status, 'ingest_status': item.ingest_status}


def _finalize_document_import(task_id):
    """Aggregate durable item outcomes and complete the document import once."""
    task = QuestionDocumentImportTask.objects.select_related('batch__actor', 'course').get(pk=task_id)
    if task.stage in {
        QuestionDocumentImportTask.Stage.SUCCESS,
        QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS,
        QuestionDocumentImportTask.Stage.FAILED,
    }:
        return {'task_id': str(task.id), 'stage': task.stage}

    items = list(task.items.order_by('source_position'))
    unfinished = any(
        item.status in {
            QuestionDocumentImportItem.Status.PENDING,
            QuestionDocumentImportItem.Status.DISPATCHED,
            QuestionDocumentImportItem.Status.RUNNING,
            QuestionDocumentImportItem.Status.RETRYING,
        }
        or (
            item.status == QuestionDocumentImportItem.Status.SUCCESS
            and item.ingest_status not in {
                QuestionDocumentImportItem.IngestStatus.INGESTED,
                QuestionDocumentImportItem.IngestStatus.FAILED,
            }
        )
        for item in items
    )
    if unfinished or len(items) < task.candidate_count:
        _touch_document_task(task, stage=QuestionDocumentImportTask.Stage.IMPORTING)
        return {'task_id': str(task.id), 'stage': task.stage, 'waiting': True}

    imported = skipped_existing = skipped_in_package = failed = linked_count = 0
    valid_questions = []
    summaries = []
    for item in items:
        if item.status == QuestionDocumentImportItem.Status.SUCCESS and item.ingest_status == QuestionDocumentImportItem.IngestStatus.INGESTED:
            result = item.ingest_result_json or {}
            imported += int(result.get('imported', 0) or 0)
            skipped_existing += int(result.get('skipped_existing', 0) or 0)
            skipped_in_package += int(result.get('skipped_in_package', 0) or 0)
            linked_count += int(result.get('linked_count', 0) or 0)
            if task.import_purpose == 'wrongbook_drill' and item.structured_result_json:
                question = dict(item.structured_result_json)
                existing_ids = result.get('existing_canonical_question_ids') or []
                if existing_ids:
                    question['_existing_canonical_question_id'] = existing_ids[0]
                valid_questions.append(question)
        else:
            failed += 1
            message = item.error_message_safe or item.ingest_error_message_safe or '题目处理失败'
            summaries.append(_question_error(item.question_no, message))

    if task.import_purpose == 'wrongbook_drill' and task.wrong_drill_source_set_id:
        from apps.missions.classroom_wrong_drill_service import finalize_source_import
        finalize_source_import(
            task.wrong_drill_source_set_id,
            valid_questions,
            SimpleNamespace(paper_id=str(task.batch.paper_id) if task.batch.paper_id else None),
        )

    if task.batch.paper_id:
        from apps.parser.models import ExamPaper
        ExamPaper.objects.filter(pk=task.batch.paper_id).update(total_questions=imported)
    finish_ingestion_batch(
        task.batch,
        total_read=len(items),
        created_count=imported,
        skipped_existing_count=skipped_existing,
        skipped_in_package_count=skipped_in_package,
        failed_count=failed,
    )
    completed = imported + skipped_existing + skipped_in_package
    final_stage = (
        QuestionDocumentImportTask.Stage.SUCCESS if not failed else
        QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS if completed else
        QuestionDocumentImportTask.Stage.FAILED
    )
    task.success_count = completed
    task.failed_question_count = failed
    task.linked_count = linked_count
    task.error_summary = '; '.join(summaries)[:1000]
    task.stage = final_stage
    task.progress = 100
    task.last_heartbeat_at = timezone.now()
    task.save(update_fields=[
        'success_count', 'failed_question_count', 'linked_count', 'error_summary',
        'stage', 'progress', 'last_heartbeat_at', 'updated_at',
    ])
    return {
        'task_id': str(task.id), 'stage': final_stage, 'imported': imported,
        'skipped_existing': skipped_existing, 'skipped_in_package': skipped_in_package,
        'failed': failed,
    }


@shared_task(bind=True, name='apps.study.document_import_tasks.finalize_document_import_task', max_retries=0)
def finalize_document_import_task(self, task_id):
    """Serialize final aggregation so retries cannot duplicate side effects."""
    del self
    _dispatch_pending_document_items(task_id)
    with transaction.atomic():
        task = QuestionDocumentImportTask.objects.select_for_update().get(pk=task_id)
        if task.stage in {
            QuestionDocumentImportTask.Stage.SUCCESS,
            QuestionDocumentImportTask.Stage.PARTIAL_SUCCESS,
            QuestionDocumentImportTask.Stage.FAILED,
        }:
            return {'task_id': str(task.id), 'stage': task.stage}
        result = _finalize_document_import(task_id)
    if result.get('waiting'):
        _schedule_document_finalizer(task_id, countdown=5)
    else:
        shutil.rmtree(_document_asset_root(task), ignore_errors=True)
    return result


@shared_task(name='apps.study.document_import_tasks.recover_document_import_tasks')
def recover_document_import_tasks():
    """Recover parent/item messages lost during worker or broker failures."""
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(
        seconds=int(getattr(settings, 'DOCUMENT_IMPORT_ITEM_LEASE_SECONDS', 900)),
    )
    active_stages = {
        QuestionDocumentImportTask.Stage.QUEUED,
        QuestionDocumentImportTask.Stage.EXTRACTING,
        QuestionDocumentImportTask.Stage.STRUCTURING,
        QuestionDocumentImportTask.Stage.IMPORTING,
    }
    recovered = 0
    task_ids = list(QuestionDocumentImportTask.objects.filter(
        stage__in=active_stages,
    ).values_list('id', flat=True)[:200])
    for task_id in task_ids:
        stale_items = QuestionDocumentImportItem.objects.filter(
            document_import_task_id=task_id,
            worker_heartbeat_at__lt=cutoff,
        ).filter(
            Q(status__in=(
                QuestionDocumentImportItem.Status.DISPATCHED,
                QuestionDocumentImportItem.Status.RUNNING,
            ))
            | Q(
                status=QuestionDocumentImportItem.Status.SUCCESS,
                ingest_status__in=(
                    QuestionDocumentImportItem.IngestStatus.PENDING,
                    QuestionDocumentImportItem.IngestStatus.INGESTING,
                ),
            )
        )
        for item in stale_items:
            item.status = QuestionDocumentImportItem.Status.PENDING
            item.ingest_status = QuestionDocumentImportItem.IngestStatus.PENDING
            item.worker_heartbeat_at = timezone.now()
            item.save(update_fields=['status', 'ingest_status', 'worker_heartbeat_at', 'updated_at'])
            recovered += 1
        try:
            task = QuestionDocumentImportTask.objects.get(pk=task_id)
            if task.candidate_count:
                _dispatch_pending_document_items(task.id)
                _schedule_document_finalizer(task.id, countdown=1)
            else:
                process_document_import_task.apply_async(args=(str(task.id),))
        except QuestionDocumentImportTask.DoesNotExist:
            continue
    return {'recovered_items': recovered, 'checked_tasks': len(task_ids)}
