"""Fixed classroom wrong-drill import, mapping and generation workflow.

This module is deliberately separate from the legacy AI/rule wrong-book
candidate workflow and from the classroom wrong-mark Excel importer.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.xlsx_reader import read_xlsx_sheets
from apps.courses.models import CourseQuestionLink
from apps.institutions.models import ClassStudent
from apps.parser.models import ExamQuestion
from apps.study.document_import_views import _save_upload
from apps.study.models import AnswerAttempt

from .models import (
    ClassroomWrongDrillBatch, ClassroomWrongDrillItem,
    ClassroomWrongDrillMappingImport, ClassroomWrongDrillNumberMapping,
    ClassroomWrongDrillPackage, ClassroomWrongDrillSourceQuestion,
    ClassroomWrongDrillSourceSet, LearningMission, MissionClassAssignment,
    MissionQuestionRel, MissionLevel, TeacherWrongBookCell,
    TeacherWrongBookMatrix,
)
from .services import ensure_flat_assignment_level
from .wrongbook_matrix import MatrixError, _question_snapshot


ACTIVE_CELL_STATUSES = ('marked', 'generated', 'locked')
MAX_MAPPING_BYTES = 10 * 1024 * 1024


def _lecture_label(value):
    text = str(value or '').strip()
    matched = re.search(r'第\s*(\d+)\s*讲', text)
    return f'第{matched.group(1)}讲' if matched else (text or '本讲')


def _norm(value):
    value = str(value or '').strip()
    if value.endswith('.0'):
        value = value[:-2]
    return re.sub(r'\s+', '', value)


def _is_mapping_number(value):
    """Whether a cell looks like a data value instead of an unknown header."""
    value = _norm(value)
    return bool(value) and (value in ('原题', 'original') or bool(re.fullmatch(r'\d+(?:\.\d+)?', value)))


def _resolve_path(relative_path):
    path = Path(relative_path)
    return path if path.is_absolute() else Path(settings.MEDIA_ROOT) / path


def save_mapping_upload(upload, *, source_set_id):
    if upload is None:
        return None
    if int(getattr(upload, 'size', 0) or 0) > MAX_MAPPING_BYTES:
        raise MatrixError('映射表文件不能超过 10MB', 'MAPPING_TOO_LARGE', 400)
    if not str(getattr(upload, 'name', '')).lower().endswith('.xlsx'):
        raise MatrixError('映射表仅支持 .xlsx 文件', 'MAPPING_FORMAT_INVALID', 400)
    relative = _save_upload(
        upload, course_id=source_set_id, document_type='xlsx',
        storage_prefix='wrong_drill_mapping_imports',
    )
    return relative


def _mapping_rows(mapping_import):
    path = _resolve_path(mapping_import.file_path)
    if not path.exists():
        raise MatrixError('映射表文件不存在', 'MAPPING_FILE_MISSING', 400)
    with path.open('rb') as stream:
        sheets = read_xlsx_sheets(stream)
    rows = []
    parsing = {'mode': 'header', 'sheets': []}
    for sheet in sheets:
        header_index = None
        header = {}
        for index, row in enumerate(sheet.rows):
            names = {_norm(value): position for position, value in enumerate(row)}
            # Column meaning is determined by its header, not by its position.
            # The current template puts the workbook/practice number first and
            # the wrong-drill number second; legacy templates with the reverse
            # order remain supported.
            wrong_col = next((names[key] for key in (
                '错题练习题号', '错题题号', '练习题号',
            ) if key in names), None)
            target_col = next((names[key] for key in (
                '练习题题号', '针对练习册题号', '练习册题号', '针对题号', '原题号',
            ) if key in names), None)
            if wrong_col is not None and target_col is not None:
                header_index, header = index, {'wrong': wrong_col, 'target': target_col}
                break
        if header_index is None:
            # Existing teacher spreadsheets use several different labels. When
            # labels are unknown, use the first two non-empty columns by
            # position instead of rejecting a valid two-column mapping sheet.
            candidate_index = next((
                index for index, row in enumerate(sheet.rows)
                if len(row) >= 2 and _norm(row[0]) and _norm(row[1])
            ), None)
            if candidate_index is None:
                continue
            candidate = sheet.rows[candidate_index]
            data_starts_at = candidate_index if (
                _is_mapping_number(candidate[0]) and _is_mapping_number(candidate[1])
            ) else candidate_index + 1
            header_index, header = data_starts_at - 1, {'wrong': 1, 'target': 0}
            parsing['mode'] = 'position'
            parsing['sheets'].append({
                'sheet': sheet.title,
                'header_row': candidate_index + 1,
                'data_starts_at_row': data_starts_at + 1,
            })
        for row_number, row in enumerate(sheet.rows[header_index + 1:], header_index + 2):
            wrong = _norm(row[header['wrong']] if header['wrong'] < len(row) else '')
            target = _norm(row[header['target']] if header['target'] < len(row) else '')
            if wrong or target:
                rows.append({'sheet': sheet.title, 'row': row_number, 'wrong': wrong, 'target': target})
    if not sheets:
        raise MatrixError('映射表没有工作表', 'MAPPING_EMPTY', 400)
    if not rows:
        raise MatrixError('映射表未找到“错题练习题号”和“针对练习册题号”列', 'MAPPING_HEADER_INVALID', 400)
    return rows, parsing


def _workbook_number_map(mission, node_id=None):
    relations = MissionQuestionRel.objects.filter(mission=mission).select_related('level')
    if node_id:
        relations = relations.filter(source_node_id=node_id)
    result = {}
    duplicates = set()
    question_ids = list(relations.values_list('question_id', flat=True))
    question_nos = {
        str(row.id): _norm(row.question_no)
        for row in ExamQuestion.objects.filter(id__in=question_ids)
    }
    for rel in relations.order_by('sort_no', 'id'):
        number = _norm(rel.node_question_no or question_nos.get(str(rel.question_id)))
        if not number:
            continue
        if number in result and str(result[number]) != str(rel.question_id):
            duplicates.add(number)
        else:
            result[number] = rel.question_id
    for number in duplicates:
        result.pop(number, None)
    # Offline carriers have no MissionQuestionRel. Resolve numbers from the
    # classroom's imported practice-question links instead.
    if not result and getattr(mission, 'course_id', None):
        links = CourseQuestionLink.objects.filter(
            course_id=mission.course_id, is_deleted=False,
        ).select_related('question', 'tree_node')
        if node_id:
            links = links.filter(tree_node_id=node_id)
        for link in links.order_by('created_at', 'id'):
            number = _norm(link.source_document_question_no or link.question.question_no)
            if not number:
                continue
            if number in result and str(result[number]) != str(link.question_id):
                duplicates.add(number)
            else:
                result[number] = link.question_id
        for number in duplicates:
            result.pop(number, None)
    return result, duplicates


@transaction.atomic
def finalize_source_import(source_set_id, valid_questions, result):
    """Bind imported canonical questions to the isolated source set."""
    source_set = ClassroomWrongDrillSourceSet.objects.select_for_update().get(pk=source_set_id)
    paper_question_map = {}
    if result.paper_id:
        paper_question_map = {
            _norm(q.question_no): q
            for q in ExamQuestion.objects.filter(paper_id=result.paper_id).prefetch_related('images', 'options')
        }
    source_set.questions.all().delete()
    missing = []
    for index, incoming in enumerate(valid_questions):
        number = _norm(incoming.get('_source_document_question_no') or incoming.get('question_no'))
        question_id = incoming.get('_existing_canonical_question_id')
        question = ExamQuestion.objects.filter(pk=question_id).prefetch_related('images', 'options').first() if question_id else paper_question_map.get(number)
        if question is None:
            missing.append(number or f'index-{index + 1}')
            continue
        ClassroomWrongDrillSourceQuestion.objects.create(
            source_set=source_set,
            question=question,
            wrong_question_no=number,
            question_snapshot=_question_snapshot(question),
            answer_snapshot=question.answer or '',
            analysis_snapshot=question.analysis or '',
            sort_no=index + 1,
        )
    source_set.error_summary = '无法绑定题库题目: ' + ','.join(missing[:20]) if missing else ''
    mapping_import = source_set.mapping_imports.filter(status='validating').order_by('-created_at').first()
    if mapping_import:
        try:
            import_number_mapping(source_set, mapping_import)
        except MatrixError as exc:
            mapping_import.status = 'failed'
            mapping_import.errors = [{'reason_code': exc.code, 'message': str(exc)}]
            mapping_import.completed_at = timezone.now()
            mapping_import.save(update_fields=['status', 'errors', 'completed_at'])
            source_set.status = 'pending_mapping'
            source_set.save(update_fields=['status', 'error_summary', 'updated_at'])
            return source_set
    else:
        source_set.status = 'pending_mapping'
        source_set.save(update_fields=['status', 'error_summary', 'updated_at'])
    return source_set


@transaction.atomic
def import_number_mapping(source_set, mapping_import):
    rows, parsing = _mapping_rows(mapping_import)
    # This transient attribute is returned by the upload endpoint so the UI
    # can tell the teacher when a non-standard sheet was parsed by position.
    mapping_import.mapping_parse = parsing
    source_questions = {q.wrong_question_no: q for q in source_set.questions.all()}
    workbook_map, duplicate_numbers = _workbook_number_map(
        source_set.source_mission, source_set.source_node_id,
    )
    mapping_import.total_rows = len(rows)
    errors = []
    active = []
    seen = set()
    for row in rows:
        wrong, target = row['wrong'], row['target']
        code = None
        if not wrong or not target:
            code = 'MISSING_NUMBER'
        elif target in ('原题', 'original'):
            code = 'ORIGINAL_QUESTION'
        elif wrong in seen:
            code = 'DUPLICATE_WRONG_NUMBER'
        elif wrong not in source_questions:
            code = 'WRONG_NUMBER_NOT_IN_DOCX'
        elif target in duplicate_numbers:
            code = 'AMBIGUOUS_WORKBOOK_NUMBER'
        elif target not in workbook_map and source_set.source_mission.source_context != 'course_offline_wrongbook':
            code = 'WORKBOOK_NUMBER_NOT_IN_CLASS'
        if code:
            errors.append({**row, 'reason_code': code})
            continue
        seen.add(wrong)
        active.append((row, source_questions[wrong], workbook_map.get(target)))
    source_set.number_mappings.all().delete()
    for index, (row, source_question, workbook_question_id) in enumerate(active, 1):
        ClassroomWrongDrillNumberMapping.objects.create(
            source_set=source_set,
            source_question=source_question,
            wrong_question_no=row['wrong'],
            workbook_question_no=row['target'],
            workbook_question_id=workbook_question_id,
            mapping_version=source_set.number_mapping_version + 1,
            sort_no=index,
        )
    mapping_import.imported_count = len(active)
    mapping_import.invalid_count = len(errors)
    mapping_import.errors = errors[:200]
    mapping_import.status = 'succeeded' if active else 'failed'
    mapping_import.completed_at = timezone.now()
    mapping_import.save(update_fields=['total_rows', 'imported_count', 'invalid_count', 'errors', 'status', 'completed_at'])
    source_set.number_mapping_version += 1
    source_set.status = 'ready' if active else 'pending_mapping'
    source_set.error_summary = '' if active else '没有可用的错题练习题映射'
    source_set.save(update_fields=['number_mapping_version', 'status', 'error_summary', 'updated_at'])
    return source_set


def source_sets_payload(mission):
    from apps.study.document_import_models import QuestionDocumentImportItem, QuestionDocumentImportTask

    result = []
    for source_set in mission.wrong_drill_source_sets.prefetch_related('questions', 'number_mappings').order_by('-created_at'):
        mapping_import = source_set.mapping_imports.order_by('-created_at').first()
        import_task = QuestionDocumentImportTask.objects.filter(
            wrong_drill_source_set_id=source_set.id,
        ).order_by('-created_at').first()
        import_status = None
        if import_task:
            import_status = {
                'task_id': str(import_task.id),
                'stage': import_task.stage,
                'progress': import_task.progress,
                'candidate_count': import_task.candidate_count,
                'success_count': import_task.items.filter(
                    status=QuestionDocumentImportItem.Status.SUCCESS,
                    ingest_status=QuestionDocumentImportItem.IngestStatus.INGESTED,
                ).count(),
                'failed_question_count': import_task.items.filter(
                    status=QuestionDocumentImportItem.Status.FAILED,
                ).count(),
                'error_summary': import_task.error_summary,
            }
        result.append({
            'source_set_id': str(source_set.id),
            'source_file_name': Path(source_set.source_file_path).name,
            'source_node_id': str(source_set.source_node_id) if source_set.source_node_id else None,
            'source_node_name': source_set.source_node_name,
            'status': source_set.status,
            'question_count': source_set.questions.count(),
            'mapping_count': source_set.number_mappings.filter(status='active').count(),
            'mapping_version': source_set.number_mapping_version,
            'error_summary': source_set.error_summary,
            'import_task': import_status,
            'mapping_import': {
                'file_name': mapping_import.file_name,
                'status': mapping_import.status,
                'total_rows': mapping_import.total_rows,
                'imported_count': mapping_import.imported_count,
                'invalid_count': mapping_import.invalid_count,
                'errors': mapping_import.errors[:200],
            } if mapping_import else None,
        })
    return result


def source_set_detail_payload(source_set):
    """Payload for the source-management pages; never exposes mutable ORM fields."""
    return {
        'source_set_id': str(source_set.id),
        'status': source_set.status,
        'source_file_name': Path(source_set.source_file_path).name,
        'questions': [{
            'question_id': str(item.question_id),
            'question_no': item.wrong_question_no,
            'sort_no': item.sort_no,
            'snapshot': item.question_snapshot or {},
            'answer': item.answer_snapshot,
            'analysis': item.analysis_snapshot,
        } for item in source_set.questions.order_by('sort_no', 'id')],
        'mappings': [{
            'mapping_id': str(item.id),
            'wrong_question_no': item.wrong_question_no,
            'workbook_question_no': item.workbook_question_no,
            'status': item.status,
            'reason': item.reason,
        } for item in source_set.number_mappings.order_by('sort_no', 'id')],
    }


@transaction.atomic
def save_manual_number_mappings(source_set, rows):
    """Replace one source set's mappings with teacher-edited table rows."""
    if not isinstance(rows, list):
        raise MatrixError('mappings 必须是数组', 'INVALID_REQUEST', 400)
    source_questions = {item.wrong_question_no: item for item in source_set.questions.all()}
    workbook_map, _ = _workbook_number_map(source_set.source_mission, source_set.source_node_id)
    normalized, seen = [], set()
    for index, row in enumerate(rows, 1):
        wrong = _norm((row or {}).get('wrong_question_no'))
        target = _norm((row or {}).get('workbook_question_no'))
        if not wrong or not target:
            raise MatrixError(f'第 {index} 行题号不能为空', 'MAPPING_INVALID', 400)
        if wrong in seen or wrong not in source_questions:
            raise MatrixError(f'错题练习题号 {wrong} 不存在或重复', 'MAPPING_INVALID', 400)
        seen.add(wrong)
        workbook_id = workbook_map.get(target)
        offline = source_set.source_mission.source_context == 'course_offline_wrongbook'
        normalized.append((wrong, target, workbook_id, 'active' if workbook_id or offline else 'unmatched', '' if workbook_id or offline else '未在课堂练习中找到题号'))
    source_set.number_mappings.all().delete()
    ClassroomWrongDrillNumberMapping.objects.bulk_create([
        ClassroomWrongDrillNumberMapping(
            source_set=source_set, source_question=source_questions[wrong], wrong_question_no=wrong,
            workbook_question_no=target, workbook_question_id=workbook_id, status=status,
            reason=reason, mapping_version=source_set.number_mapping_version + 1, sort_no=index,
        ) for index, (wrong, target, workbook_id, status, reason) in enumerate(normalized, 1)
    ])
    source_set.number_mapping_version += 1
    source_set.status = 'ready' if normalized else 'pending_mapping'
    source_set.error_summary = ''
    source_set.save(update_fields=['number_mapping_version', 'status', 'error_summary', 'updated_at'])
    return source_set


def wrong_drill_preflight(*, mission, matrix, source_set_id, student_ids=None):
    source_set = ClassroomWrongDrillSourceSet.objects.filter(
        pk=source_set_id, source_mission=mission,
    ).first()
    if source_set is None:
        raise MatrixError('错题练习题导入源不存在', 'SOURCE_NOT_FOUND', 404)
    members = {str(row.student_id) for row in matrix.students.filter(status='active')}
    selected = list(dict.fromkeys(str(value) for value in (student_ids or members)))
    if any(value not in members for value in selected):
        raise MatrixError('选择的学生不在当前课堂范围内', 'STUDENT_SCOPE_INVALID', 409)
    mappings = {}
    for row in source_set.number_mappings.filter(status='active').select_related('source_question'):
        mappings.setdefault(str(row.workbook_question_id), []).append(row)
    rows = []
    for student_id in selected:
        cells = TeacherWrongBookCell.objects.filter(
            matrix=matrix, student_id=student_id, status__in=ACTIVE_CELL_STATUSES,
        )
        for cell in cells:
            matched = mappings.get(str(cell.source_question_id), [])
            if not matched:
                rows.append({'student_id': student_id, 'source_question_id': str(cell.source_question_id), 'reason_code': 'NO_MAPPING'})
            else:
                rows.extend({'student_id': student_id, 'source_question_id': str(cell.source_question_id), 'drill_question_no': item.wrong_question_no} for item in matched)
    return {
        'source_set_id': str(source_set.id), 'student_count': len(selected),
        'wrong_count': len({(row['student_id'], row['source_question_id']) for row in rows}),
        'matched_count': sum(1 for row in rows if row.get('drill_question_no')),
        'estimated_drill_count': sum(1 for row in rows if row.get('drill_question_no')),
        'unmatched': [row for row in rows if row.get('reason_code') == 'NO_MAPPING'][:200],
        'source_status': source_set.status,
    }


def _filename(mission, source_set, student):
    def safe(value):
        return re.sub(r'[\\/:*?"<>|]+', '_', str(value or '')).strip(' ._')
    base_title = str(mission.mission_name or '')
    if base_title.endswith('-错题精练题'):
        base_title = base_title[:-len('-错题精练题')]
    return f'{safe(base_title)}-{safe(student.display_name or student.mobile)}--错题精练题.pdf'


def _mission_pdf_questions(package):
    rows = []
    for item in package.items.filter(status='generated').select_related('drill_question').order_by('sort_no'):
        q = item.drill_question
        snapshot = item.source_question.question_snapshot or {}
        data = dict(snapshot)
        data.update({
            'id': q.id, 'question_no': item.drill_question_no,
            'question_type': snapshot.get('question_type') or q.question_type,
            'stem': snapshot.get('stem') or q.stem,
            'stem_html': snapshot.get('stem_html') or q.stem_html,
            'answer': item.source_question.answer_snapshot,
            'analysis': item.source_question.analysis_snapshot,
            '_pdf_title': package.mission.mission_name,
        })
        rows.append(data)
    return rows


def _create_personal_mission(matrix, batch, package, student, items):
    source = matrix.source_mission
    section = _lecture_label(batch.source_set.source_node_name)
    mission_name = f'{source.mission_name}-讲义({section})-错题精练题'
    mission = LearningMission.objects.create(
        creator_teacher_id=source.creator_teacher_id,
        mission_name=mission_name,
        goal_text='针对课堂错题的错题精练题',
        status='published', assignment_mode='flat', mission_kind='wrongbook_personal',
        source_type='wrongbook_drill', source_context='wrongbook_drill',
        source_matrix_id=matrix.id, source_generation_batch_id=batch.id,
        source_set_id=batch.source_set_id, source_batch_id=batch.id,
        parent_mission_id=source.id, class_obj_id=matrix.class_obj_id,
        target_student_ids=[str(student.id)], course_id=source.course_id,
        start_at=source.start_at, end_at=source.end_at,
    )
    level = ensure_flat_assignment_level(mission)
    if matrix.class_obj_id:
        MissionClassAssignment.objects.create(
            mission=mission, class_obj_id=matrix.class_obj_id, status='active',
            start_at=source.start_at, end_at=source.end_at,
            target_student_ids=[str(student.id)],
        )
    from apps.study.models import StudentMissionProgress
    StudentMissionProgress.objects.get_or_create(
        mission=mission, student_user_id=student,
        defaults={'progress_status': 'not_started', 'progress_percent': 0},
    )
    for sort_no, item in enumerate(items, 1):
        MissionQuestionRel.objects.create(
            mission=mission, level=level, question_id=item.drill_question_id,
            sort_no=sort_no, source_type='wrongbook_drill', target_student_ids=[str(student.id)],
            question_snapshot=item.source_question.question_snapshot,
            source_matrix_id=matrix.id, source_student_id=student.id,
            source_set_id=batch.source_set_id, source_wrong_question_id=item.mapping.workbook_question_id,
            source_mapping_id=item.mapping_id, source_wrong_question_no=item.wrong_question_no,
            source_drill_question_no=item.drill_question_no, source_role='drill_question',
            source_provider='wrongbook_drill', source_node_id=batch.source_set.source_node_id,
        )
    return mission


@transaction.atomic
def generate_wrong_drill_batch(*, mission, matrix, teacher, source_set_id, student_ids=None, version=None, existing_batch_id=None):
    matrix = TeacherWrongBookMatrix.objects.select_for_update().get(pk=matrix.id)
    # Generation must use the same current online wrong-answer state as the
    # statistics page, even if the teacher clicks Generate immediately.
    from .classroom_wrongbook_service import sync_classroom_online_wrongbook
    sync_classroom_online_wrongbook(mission, matrix)
    matrix.refresh_from_db()
    if version is not None and int(version) != matrix.version:
        raise MatrixError('错题统计版本已变化，请刷新后重试', 'VERSION_CONFLICT', 409)
    source_set = ClassroomWrongDrillSourceSet.objects.filter(
        pk=source_set_id, source_mission=mission, status='ready',
    ).first()
    if source_set is None:
        raise MatrixError('错题练习题尚未完成导入或映射', 'SOURCE_NOT_READY', 409)
    members = {str(row.student_id): row for row in matrix.students.filter(status='active')}
    selected = [str(value) for value in (student_ids or members.keys())]
    if any(value not in members for value in selected):
        raise MatrixError('选择的学生不在当前课堂范围内', 'STUDENT_SCOPE_INVALID', 409)
    selected = list(dict.fromkeys(selected))
    if existing_batch_id:
        batch = ClassroomWrongDrillBatch.objects.select_for_update().get(
            pk=existing_batch_id, matrix=matrix, source_set=source_set,
        )
        batch.status = 'generating'
        batch.save(update_fields=['status'])
    else:
        latest = ClassroomWrongDrillBatch.objects.filter(
            matrix=matrix, source_set=source_set, request_version=matrix.version,
            status__in=('generated', 'partially_failed'),
        ).order_by('-created_at').first()
        if latest and set(latest.request_student_ids or []) == set(selected):
            return latest
        batch = ClassroomWrongDrillBatch.objects.create(
            matrix=matrix, source_set=source_set, requested_by=teacher,
            request_version=matrix.version, request_student_ids=selected,
            status='generating', requested_count=len(selected),
        )
    mapping_by_workbook = {}
    for row in source_set.number_mappings.filter(status='active').select_related('source_question'):
        mapping_by_workbook.setdefault(str(row.workbook_question_id), []).append(row)
    errors = []
    created_packages = []
    for student_id in selected:
        cells = TeacherWrongBookCell.objects.filter(
            matrix=matrix, student_id=student_id, status__in=ACTIVE_CELL_STATUSES,
        ).order_by('created_at')
        rows = []
        missing_answer_rows = []
        seen_drill = set()
        for cell in cells:
            for mapping in mapping_by_workbook.get(str(cell.source_question_id), []):
                if str(mapping.source_question_id) in seen_drill:
                    continue
                source_question = mapping.source_question
                if not source_question.answer_snapshot.strip():
                    errors.append({'student_id': student_id, 'wrong_question_no': mapping.workbook_question_no, 'reason_code': 'MISSING_ANSWER'})
                    missing_answer_rows.append((source_question, mapping))
                    continue
                rows.append((source_question, mapping))
                seen_drill.add(str(mapping.source_question_id))
        if not rows:
            errors.append({'student_id': student_id, 'reason_code': 'NO_MAPPED_DRILL'})
            continue
        # Keep historical packages/PDFs immutable, but expose only the latest
        # published personal assignment to the student home page.
        old_missions = LearningMission.objects.filter(
            parent_mission_id=mission.id, mission_kind='wrongbook_personal', status='published',
        )
        for old in old_missions:
            if str(student_id) in {str(value) for value in (old.target_student_ids or [])}:
                old.status = 'closed'
                old.save(update_fields=['status', 'updated_at'])
        personal_mission = _create_personal_mission(
            matrix, batch, None, members[student_id].student, [],
        )
        package = ClassroomWrongDrillPackage.objects.create(
            batch=batch, student_id=student_id, mission=personal_mission,
            student_name_snapshot=members[student_id].student_name_snapshot,
            class_name_snapshot=members[student_id].class_name_snapshot,
            source_statistics_version=matrix.version,
            number_mapping_version=source_set.number_mapping_version,
        )
        item_models = []
        for sort_no, (source_question, mapping) in enumerate(rows, 1):
            item_models.append(ClassroomWrongDrillItem.objects.create(
                package=package, source_question=source_question, mapping=mapping,
                drill_question_id=source_question.question_id,
                wrong_question_no=mapping.workbook_question_no,
                drill_question_no=source_question.wrong_question_no, sort_no=sort_no,
                relation_snapshot={
                    'source_wrong_question_id': str(mapping.workbook_question_id),
                    'source_wrong_question_no': mapping.workbook_question_no,
                    'drill_question_id': str(source_question.question_id),
                    'drill_question_no': source_question.wrong_question_no,
                    'source_set_id': str(source_set.id),
                    'number_mapping_version': source_set.number_mapping_version,
                },
            ))
        for source_question, mapping in missing_answer_rows:
            ClassroomWrongDrillItem.objects.create(
                package=package, source_question=source_question, mapping=mapping,
                drill_question_id=source_question.question_id,
                wrong_question_no=mapping.workbook_question_no,
                drill_question_no=source_question.wrong_question_no,
                status='missing_answer', reason='精练题缺少答案，未进入 PDF',
                answer_source='exam_question',
            )
        # Rebuild relations now that item IDs are available.
        # Create immutable mission relations now that item rows exist.
        _create_personal_mission_relations(package.mission, matrix, batch, student_id, item_models)
        from .wrong_drill_pdf_service import generate_wrong_drill_pdf
        package.file_name = _filename(personal_mission, source_set, members[student_id].student)
        package.pdf_file_path = generate_wrong_drill_pdf(package, _mission_pdf_questions(package))
        package.mission.pdf_file_path = package.pdf_file_path
        package.mission.save(update_fields=['pdf_file_path', 'updated_at'])
        package.question_count = len(item_models)
        package.status = 'generated'
        package.save(update_fields=['file_name', 'pdf_file_path', 'question_count', 'status', 'updated_at'])
        created_packages.append(package)
        TeacherWrongBookCell.objects.filter(matrix=matrix, student_id=student_id, status='marked').update(
            status='generated', generated_batch_id=batch.id,
        )
    batch.generated_count = len(created_packages)
    batch.failed_count = len(errors)
    batch.errors = errors[:200]
    batch.status = 'generated' if created_packages and not errors else ('partially_failed' if created_packages else 'failed')
    batch.completed_at = timezone.now()
    batch.save(update_fields=['generated_count', 'failed_count', 'errors', 'status', 'completed_at'])
    matrix.generated_count = matrix.cells.filter(status='generated').count()
    matrix.failed_count = len(errors)
    matrix.status = 'generated' if created_packages else 'partially_failed'
    matrix.last_generation_batch_id = batch.id
    matrix.save(update_fields=['generated_count', 'failed_count', 'status', 'last_generation_batch_id', 'updated_at'])
    return batch


@transaction.atomic
def queue_wrong_drill_batch(*, mission, matrix, teacher, source_set_id, student_ids=None, version=None):
    """Create a durable queued batch; PDF work is performed by Celery."""
    from .classroom_wrongbook_service import sync_classroom_online_wrongbook
    matrix = TeacherWrongBookMatrix.objects.select_for_update().get(pk=matrix.id)
    sync_classroom_online_wrongbook(mission, matrix)
    matrix.refresh_from_db()
    if version is not None and int(version) != matrix.version:
        raise MatrixError('错题统计版本已变化，请刷新后重试', 'VERSION_CONFLICT', 409)
    source_set = ClassroomWrongDrillSourceSet.objects.filter(
        pk=source_set_id, source_mission=mission, status='ready',
    ).first()
    if source_set is None:
        raise MatrixError('错题练习题尚未完成导入或映射', 'SOURCE_NOT_READY', 409)
    members = {str(row.student_id) for row in matrix.students.filter(status='active')}
    selected = list(dict.fromkeys(str(value) for value in (student_ids or members)))
    if any(value not in members for value in selected):
        raise MatrixError('选择的学生不在当前课堂范围内', 'STUDENT_SCOPE_INVALID', 409)
    latest = ClassroomWrongDrillBatch.objects.filter(
        matrix=matrix, source_set=source_set, request_version=matrix.version,
        status__in=('queued', 'generating', 'generated', 'partially_failed'),
    ).order_by('-created_at').first()
    if latest and set(latest.request_student_ids or []) == set(selected):
        return latest
    batch = ClassroomWrongDrillBatch.objects.create(
        matrix=matrix, source_set=source_set, requested_by=teacher,
        request_version=matrix.version, request_student_ids=selected,
        status='queued', requested_count=len(selected),
    )
    from .tasks import generate_wrong_drill_batch_task
    transaction.on_commit(lambda: generate_wrong_drill_batch_task.delay(str(batch.id)))
    return batch


def _create_personal_mission_relations(mission, matrix, batch, student_id, items):
    level = mission.levels.order_by('level_no').first()
    for sort_no, item in enumerate(items, 1):
        MissionQuestionRel.objects.create(
            mission=mission, level=level, question_id=item.drill_question_id,
            sort_no=sort_no, source_type='wrongbook_drill', target_student_ids=[str(student_id)],
            question_snapshot=item.source_question.question_snapshot,
            source_matrix_id=matrix.id, source_student_id=student_id,
            source_set_id=batch.source_set_id, source_wrong_question_id=item.mapping.workbook_question_id,
            source_mapping_id=item.mapping_id, source_wrong_question_no=item.wrong_question_no,
            source_drill_question_no=item.drill_question_no, source_role='drill_question',
            source_provider='wrongbook_drill', source_node_id=batch.source_set.source_node_id,
        )
