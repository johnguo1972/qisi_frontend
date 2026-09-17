"""Classroom-practice wrong-book statistics service.

This adapter keeps classroom behavior separate from the legacy teacher matrix
workflow while reusing its matrix scope, optimistic-lock and audit models.
"""
from __future__ import annotations

import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime
from xml.etree import ElementTree

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.courses.models import CourseQuestionLink, CourseTree
from apps.institutions.models import ClassStudent
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt
from apps.wrongbook.models import WrongBookItem

from .models import (
    LearningMission,
    MissionLevel,
    MissionQuestionRel,
    TeacherWrongBookCell,
    TeacherWrongBookImportBatch,
    TeacherWrongBookMatrix,
    TeacherWrongBookMatrixQuestion,
)
from .wrongbook_matrix import (
    MatrixError,
    _audit,
    _question_snapshot,
    can_manage_matrix,
    get_or_create_matrix,
)


MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_SHEETS = 100
MAX_IMPORT_ROWS = 5000
MAX_IMPORT_COLUMNS = 500
VALID_CELL_STATUSES = ('marked', 'generated', 'locked')


def _text(value) -> str:
    value = unicodedata.normalize('NFKC', str(value or ''))
    return re.sub(r'\s+', ' ', value).strip()


def _question_no(value) -> str:
    value = _text(value)
    if value.endswith('.0'):
        value = value[:-2]
    return value


def is_classroom_practice(mission: LearningMission) -> bool:
    return bool(
        mission.status == 'published'
        and mission.source_context in ('course_practice', 'course_offline_wrongbook')
        and mission.course_id
    )


def _active_assignments(mission):
    rows = list(mission.class_assignments.filter(status='active').select_related('class_obj'))
    return rows or ([mission] if mission.class_obj_id else [])


def resolve_class_id(mission, class_id=None):
    assignments = _active_assignments(mission)
    ids = [str(row.class_obj_id) for row in assignments]
    if class_id:
        class_id = str(class_id)
        if class_id not in ids:
            raise MatrixError('班级不属于该课堂练习', 'CLASS_NOT_IN_SCOPE', 404)
        return class_id
    if len(ids) == 1:
        return ids[0]
    if len(ids) > 1:
        # The statistics page exposes the assignment scope as a dropdown.
        # Use the first published class for the initial request, then let the
        # client switch by sending an explicit class_id.
        return ids[0]
    raise MatrixError('课堂练习未分配班级', 'SCOPE_INVALID', 409)


@transaction.atomic
def ensure_classroom_provenance(mission: LearningMission):
    """Persist node and node-local question snapshots for legacy missions."""
    if not mission.course_id:
        raise MatrixError('课堂练习缺少课程来源', 'SCOPE_INVALID', 409)

    levels = list(mission.levels.order_by('level_no', 'id'))
    relations = list(
        MissionQuestionRel.objects.filter(mission=mission)
        .select_related('level')
        .order_by('level__level_no', 'sort_no', 'id')
    )
    if not levels or not relations:
        raise MatrixError('课堂练习没有完整的节点或题目快照', 'SCOPE_INVALID', 409)

    persisted_ids = [str(value) for value in (mission.source_node_ids or []) if str(value or '').strip()]
    node_map = {
        str(node.id): node
        for node in CourseTree.objects.filter(course_id=mission.course_id, id__in=persisted_ids)
    }
    link_map = defaultdict(list)
    for row in CourseQuestionLink.objects.filter(
        course_id=mission.course_id,
        is_deleted=False,
        question_id__in=[rel.question_id for rel in relations],
    ).select_related('tree_node'):
        if row.tree_node_id:
            link_map[str(row.question_id)].append(row)

    level_node = {}
    for index, level in enumerate(levels):
        node_id = str(level.source_node_id) if level.source_node_id else ''
        if not node_id and index < len(persisted_ids):
            node_id = persisted_ids[index]
        if not node_id:
            candidates = {
                str(link.tree_node_id)
                for rel in relations
                if rel.level_id == level.id
                for link in link_map.get(str(rel.question_id), [])
            }
            if len(candidates) == 1:
                node_id = next(iter(candidates))
        if not node_id or (node_id not in node_map and not level.node_name_snapshot):
            raise MatrixError(
                f'关卡 {level.level_no} 无法确定课程节点来源', 'SCOPE_INVALID', 409,
            )
        node = node_map.get(node_id)
        if node:
            snapshot_name = level.node_name_snapshot or node.name
            snapshot_sort = level.node_sort_no_snapshot or index + 1
            level_node[level.id] = (node_id, snapshot_name, snapshot_sort)
            updates = {
                'source_node_id': level.source_node_id or node.id,
                'node_name_snapshot': snapshot_name,
                'node_sort_no_snapshot': snapshot_sort,
            }
        else:
            level_node[level.id] = (node_id, level.node_name_snapshot, level.node_sort_no_snapshot or index + 1)
            updates = {
                'source_node_id': node_id,
                'node_name_snapshot': level.node_name_snapshot,
                'node_sort_no_snapshot': level.node_sort_no_snapshot or index + 1,
            }
        if any(getattr(level, key) != value for key, value in updates.items()):
            for key, value in updates.items():
                setattr(level, key, value)
            level.save(update_fields=[*updates.keys()])

    by_level = defaultdict(list)
    for rel in relations:
        by_level[rel.level_id].append(rel)
    for level_id, level_relations in by_level.items():
        node_id, node_name, _ = level_node[level_id]
        for position, rel in enumerate(level_relations, 1):
            source_node_id = rel.source_node_id or node_id
            if str(source_node_id) != str(node_id):
                raise MatrixError('题目节点来源与关卡不一致', 'SCOPE_INVALID', 409)
            updates = {
                'source_node_id': node_id,
                'source_node_name_snapshot': rel.source_node_name_snapshot or node_name,
                'node_question_no': rel.node_question_no or str(position),
            }
            if any(getattr(rel, key) != value for key, value in updates.items()):
                for key, value in updates.items():
                    setattr(rel, key, value)
                rel.save(update_fields=[*updates.keys()])
    return mission


def prepare_classroom_matrix(mission_id, teacher, class_id=None):
    try:
        mission = LearningMission.objects.select_related('course', 'class_obj').get(pk=mission_id)
    except LearningMission.DoesNotExist:
        raise MatrixError('课堂练习不存在', 'NOT_FOUND', 404)
    if not can_manage_matrix(mission, teacher):
        raise MatrixError('无权管理该课堂练习', 'FORBIDDEN', 403)
    if not is_classroom_practice(mission):
        raise MatrixError('当前任务不是已发布课堂练习', 'SCOPE_INVALID', 409)
    # The offline resource carrier intentionally has no classroom questions.
    # It exists only to own imported wrong-drill sources and mappings.
    if mission.source_context == 'course_practice':
        ensure_classroom_provenance(mission)
    selected_class_id = resolve_class_id(mission, class_id)
    matrix = get_or_create_matrix(mission, teacher, selected_class_id)
    if mission.source_context == 'course_offline_wrongbook':
        _ensure_offline_classroom_questions(mission, matrix)
    return mission, matrix, selected_class_id


@transaction.atomic
def _ensure_offline_classroom_questions(mission, matrix):
    """Populate the statistics scope from imported classroom practice questions.

    Offline wrong-drill carriers have no MissionQuestionRel rows.  Reuse the
    current course's active classroom question links as the canonical scope.
    """
    links = list(CourseQuestionLink.objects.filter(
        course_id=mission.course_id, is_deleted=False,
    ).select_related('question', 'tree_node').order_by('created_at', 'id'))
    existing = {str(row.source_question_id): row for row in matrix.questions.all()}
    changed = False
    for index, link in enumerate(links, 1):
        qid = str(link.question_id)
        number = _question_no(link.source_document_question_no or link.question.question_no or index)
        values = {
            'source_relation': None,
            'source_node_id': link.tree_node_id,
            'node_name_snapshot': link.tree_node.name if link.tree_node_id else '',
            'node_sort_no': link.tree_node.sort_order if link.tree_node_id else 0,
            'node_question_no': number,
            'question_no_snapshot': number,
            'sort_no': index,
            'question_snapshot': _question_snapshot(link.question),
            'status': 'active',
        }
        row = existing.get(qid)
        if row is None:
            TeacherWrongBookMatrixQuestion.objects.create(
                matrix=matrix, source_question_id=link.question_id, **values,
            )
            changed = True
        elif row.status != 'active' or row.question_snapshot != values['question_snapshot']:
            for field, value in values.items(): setattr(row, field, value)
            row.save(update_fields=[*values.keys()])
            changed = True
    if changed:
        matrix.status = 'saved'
        matrix.save(update_fields=['status', 'updated_at'])
    return changed


def sync_classroom_online_for_student(mission_id, student_id):
    """Refresh classroom matrices after a student submits an online answer.

    The answer APIs deliberately treat this refresh as a best-effort side
    effect.  The statistics GET endpoint always performs the same sync, so a
    transient refresh failure cannot make answer submission fail or lose data.
    """
    try:
        mission = LearningMission.objects.get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return
    if not is_classroom_practice(mission):
        return
    for assignment in _active_assignments(mission):
        _, matrix, _ = prepare_classroom_matrix(
            mission.id, mission.creator_teacher_id, assignment.class_obj_id,
        )
        sync_classroom_online_wrongbook(mission, matrix)


def _scope(matrix):
    students = list(matrix.students.filter(status='active').order_by('sort_no', 'student_name_snapshot'))
    questions = list(matrix.questions.filter(status='active').order_by('node_sort_no', 'sort_no', 'id'))
    if not students or not questions:
        return students, questions
    offline = getattr(getattr(matrix, 'source_mission', None), 'source_context', '') == 'course_offline_wrongbook'
    if not offline and any(not question.source_node_id for question in questions):
        raise MatrixError('题目缺少节点快照', 'SCOPE_INVALID', 409)
    return students, questions


def _student_online_map(mission, students, question_ids):
    student_ids = [student.student_id for student in students]
    rows = AnswerAttempt.objects.filter(
        mission_id=mission.id,
        student_user_id__in=student_ids,
        question_id__in=question_ids,
    ).exclude(submit_source='draft')
    data = defaultdict(int)
    for row in rows:
        data[str(row.student_user_id_id)] += 1
    return data


@transaction.atomic
def sync_classroom_online_wrongbook(mission, matrix):
    students, questions = _scope(matrix)
    question_ids = [question.source_question_id for question in questions]
    student_ids = [student.student_id for student in students]
    wrong_attempts = AnswerAttempt.objects.filter(
        mission_id=mission.id,
        student_user_id__in=student_ids,
        question_id__in=question_ids,
        is_subjective_pending=False,
        is_correct=False,
    ).exclude(submit_source='draft')
    wrong_pairs = {(str(row.student_user_id_id), str(row.question_id)) for row in wrong_attempts}
    relation_by_question = {str(row.source_question_id): row.source_relation for row in questions}
    existing = {
        (str(cell.student_id), str(cell.source_question_id)): cell
        for cell in TeacherWrongBookCell.objects.select_for_update().filter(matrix=matrix)
    }
    changed = False
    now = timezone.now()
    for student_id, question_id in wrong_pairs:
        cell = existing.get((student_id, question_id))
        if cell and cell.mark_source in ('manual', 'import'):
            continue
        wrong_item, _ = WrongBookItem.objects.get_or_create(
            student_user_id_id=student_id,
            question_id=question_id,
        )
        relation = relation_by_question.get(question_id)
        if cell is None:
            cell = TeacherWrongBookCell.objects.create(
                matrix=matrix,
                student_id=student_id,
                source_question_id=question_id,
                source_relation=relation,
                wrong_book_item=wrong_item,
                status='marked',
                mark_source='online',
                marked_at=now,
            )
            existing[(student_id, question_id)] = cell
            changed = True
        elif cell.mark_source == 'online' and cell.status == 'marked':
            continue
        elif cell.mark_source == 'online' and cell.status not in ('generated', 'locked'):
            cell.status = 'marked'
            cell.wrong_book_item = wrong_item
            cell.cancelled_at = None
            cell.marked_at = now
            cell.save(update_fields=['status', 'wrong_book_item', 'cancelled_at', 'marked_at', 'updated_at'])
            changed = True

    # With the "ever wrong" contract, a later correct attempt does not clear a
    # cell. Only invalidated/deleted answer history can be reconciled here.
    if changed:
        matrix.version += 1
        matrix.status = 'saved'
        matrix.marked_count = matrix.cells.filter(status__in=VALID_CELL_STATUSES).count()
        matrix.save(update_fields=['version', 'status', 'marked_count', 'updated_at'])
    return matrix


def classroom_statistics_payload(mission, matrix):
    matrix = sync_classroom_online_wrongbook(mission, matrix)
    _ensure_offline_default_cells(mission, matrix)
    students, questions = _scope(matrix)
    question_ids = [str(question.source_question_id) for question in questions]
    online_map = _student_online_map(mission, students, question_ids)
    cells = list(TeacherWrongBookCell.objects.filter(matrix=matrix))
    cell_map = {(str(cell.student_id), str(cell.source_question_id)): cell for cell in cells}
    active_question_ids = set(question_ids)
    active_student_ids = {str(student.student_id) for student in students}
    nodes = {}
    for question in questions:
        node_id = str(question.source_node_id)
        node = nodes.setdefault(node_id, {
            'node_id': node_id,
            'node_name': question.node_name_snapshot,
            'sort_no': question.node_sort_no,
            'question_count': 0,
        })
        node['question_count'] += 1

    question_stats = {}
    for question in questions:
        wrong_count = sum(
            1 for student in students
            if (cell := cell_map.get((str(student.student_id), str(question.source_question_id))))
            and cell.status in VALID_CELL_STATUSES
        )
        question_stats[str(question.source_question_id)] = wrong_count

    student_rows = []
    for student in students:
        student_id = str(student.student_id)
        row_cells = []
        wrong_count = 0
        for question in questions:
            cell = cell_map.get((student_id, str(question.source_question_id)))
            wrong = bool(cell and cell.status in VALID_CELL_STATUSES)
            wrong_count += int(wrong)
            row_cells.append({
                'cell_id': str(cell.id) if cell else None,
                'student_id': student_id,
                'source_question_id': str(question.source_question_id),
                'node_id': str(question.source_node_id),
                'node_question_no': question.node_question_no or question.question_no_snapshot,
                'wrong': wrong,
                'status': cell.status if cell else 'normal',
                'mark_source': cell.mark_source if cell else None,
            })
        student_rows.append({
            'student_id': student_id,
            'student_name': student.student_name_snapshot,
            'student_no': student.student_no_snapshot,
            'class_id': str(student.class_obj_id),
            'data_source': 'online' if online_map.get(student_id) else 'offline',
            'wrong_count': wrong_count,
            'wrong_rate': round(wrong_count / len(questions) * 100, 2) if questions else 0,
            'cells': row_cells,
        })

    total_wrong = sum(row['wrong_count'] for row in student_rows)
    latest_import = matrix.import_batches.first()
    class_options = [
        {
            'class_id': str(assignment.class_obj_id),
            'class_name': assignment.class_obj.class_name,
        }
        for assignment in _active_assignments(mission)
    ]
    return {
        'mission_id': str(mission.id),
        'course_id': str(mission.course_id),
        'class_id': str(matrix.class_obj_id) if matrix.class_obj_id else None,
        'class_options': class_options,
        'mission_name': mission.mission_name,
        'version': matrix.version,
        'status': matrix.status,
        'mode': 'online' if student_rows and all(row['data_source'] == 'online' for row in student_rows) else 'offline',
        'has_online_answers': bool(online_map),
        'online_answer_count': sum(online_map.values()),
        'summary': {
            'total_practice_count': len(active_question_ids),
            'student_count': len(active_student_ids),
            'accumulated_wrong_count': total_wrong,
            'average_wrong_count': round(total_wrong / len(student_rows), 2) if student_rows else 0,
        },
        'nodes': sorted(nodes.values(), key=lambda item: (item['sort_no'], item['node_id'])),
        'questions': [{
            'question_id': str(question.source_question_id),
            'question_no': question.node_question_no or question.question_no_snapshot,
            'node_question_no': question.node_question_no or question.question_no_snapshot,
            'sort_no': question.sort_no,
            'node_id': str(question.source_node_id),
            'node_name': question.node_name_snapshot,
            'wrong_count': question_stats[str(question.source_question_id)],
            'wrong_rate': round(question_stats[str(question.source_question_id)] / len(students) * 100, 2) if students else 0,
            'snapshot': question.question_snapshot,
        } for question in questions],
        'students': student_rows,
        'latest_import': import_batch_payload(latest_import),
        'wrong_drill_sources': _wrong_drill_sources_payload(mission, matrix),
    }


@transaction.atomic
def _ensure_offline_default_cells(mission, matrix):
    """Mark every mapped classroom question for each student when no real
    student statistics exist.  The existing ``import`` source value is used
    because mark_source choices are intentionally backward compatible.
    """
    if mission.source_context != 'course_offline_wrongbook':
        return
    from .classroom_wrong_drill_service import ClassroomWrongDrillSourceSet
    source_set = ClassroomWrongDrillSourceSet.objects.filter(
        source_mission=mission, status='ready',
    ).order_by('-updated_at').first()
    if source_set is None:
        return
    question_ids = list(source_set.number_mappings.filter(
        status='active', workbook_question_id__isnull=False,
    ).values_list('workbook_question_id', flat=True).distinct())
    if not question_ids:
        return
    students = list(matrix.students.filter(status='active').values_list('student_id', flat=True))
    if not students:
        return
    existing = set(TeacherWrongBookCell.objects.filter(
        matrix=matrix, student_id__in=students, source_question_id__in=question_ids,
    ).values_list('student_id', 'source_question_id'))
    created = 0
    for student_id in students:
        for question_id in question_ids:
            if (student_id, question_id) in existing:
                continue
            wrong_item, _ = WrongBookItem.objects.get_or_create(
                student_user_id_id=student_id, question_id=question_id,
            )
            TeacherWrongBookCell.objects.create(
                matrix=matrix, student_id=student_id, source_question_id=question_id,
                wrong_book_item=wrong_item, status='marked', mark_source='import',
                marked_at=timezone.now(),
            )
            created += 1
    if created:
        matrix.version += 1
        matrix.status = 'saved'
        matrix.marked_count = matrix.cells.filter(status__in=VALID_CELL_STATUSES).count()
        matrix.save(update_fields=['version', 'status', 'marked_count', 'updated_at'])


def _wrong_drill_sources_payload(mission, matrix):
    """Expose isolated source status and latest package actions to the page."""
    from .models import ClassroomWrongDrillBatch
    from .classroom_wrong_drill_service import source_sets_payload
    sources = source_sets_payload(mission)
    latest = ClassroomWrongDrillBatch.objects.filter(matrix=matrix).order_by('-created_at').first()
    packages = []
    if latest:
        packages = [{
            'package_id': str(package.id), 'student_id': str(package.student_id),
            'student_name': package.student.display_name, 'file_name': package.file_name,
            'pdf_file_path': package.pdf_file_path,
            'pdf_download_url': f"{settings.MEDIA_URL.rstrip('/')}/{package.pdf_file_path.lstrip('/')}",
            'mission_id': str(package.mission_id),
            'question_count': package.question_count, 'status': package.status,
            'items': [{
                'wrong_question_no': item.wrong_question_no,
                'drill_question_no': item.drill_question_no,
                'stem_preview': str((item.source_question.question_snapshot or {}).get('stem', ''))[:120],
                'status': item.status,
            } for item in package.items.select_related('source_question').order_by('sort_no')],
        } for package in latest.packages.select_related('student').all()]
    return {'sources': sources, 'latest_batch_id': str(latest.id) if latest else None, 'packages': packages}


def import_batch_payload(batch):
    if batch is None:
        return None
    return {
        'import_batch_id': str(batch.id),
        'status': batch.status,
        'file_name': batch.file_name,
        'sheet_count': batch.sheet_count,
        'total_cells': batch.total_cells,
        'imported_count': batch.imported_count,
        'skipped_count': batch.skipped_count,
        'cancelled_count': batch.cancelled_count,
        'failed_count': batch.failed_count,
        'errors': batch.errors or [],
        'created_at': batch.created_at,
        'completed_at': batch.completed_at,
    }


def _set_cell(matrix, teacher, student_id, question, wrong, mark_source):
    now = timezone.now()
    cell = TeacherWrongBookCell.objects.select_for_update().filter(
        matrix=matrix, student_id=student_id, source_question_id=question.source_question_id,
    ).first()
    if wrong:
        if cell and cell.status in ('generated', 'locked'):
            raise MatrixError('已生成或锁定的错题不能修改', 'CELL_LOCKED', 409)
        wrong_item, _ = WrongBookItem.objects.get_or_create(
            student_user_id_id=student_id, question_id=question.source_question_id,
        )
        if cell is None:
            cell = TeacherWrongBookCell.objects.create(
                matrix=matrix,
                student_id=student_id,
                source_question_id=question.source_question_id,
                source_relation=question.source_relation,
                wrong_book_item=wrong_item,
                status='marked',
                mark_source=mark_source,
                marked_by=teacher,
                marked_at=now,
            )
        else:
            cell.status = 'marked'
            cell.mark_source = mark_source
            cell.wrong_book_item = wrong_item
            cell.source_relation = question.source_relation
            cell.marked_by = teacher
            cell.marked_at = now
            cell.cancelled_at = None
            cell.save(update_fields=['status', 'mark_source', 'wrong_book_item', 'source_relation', 'marked_by', 'marked_at', 'cancelled_at', 'updated_at'])
        return 'imported' if mark_source == 'import' else 'saved'
    if cell is None:
        return 'skipped'
    if cell.status in ('generated', 'locked') or cell.mark_source == 'online':
        raise MatrixError('线上、已生成或锁定的错题不能修改', 'ONLINE_DATA_READ_ONLY' if cell.mark_source == 'online' else 'CELL_LOCKED', 409)
    if cell.status != 'cancelled':
        cell.status = 'cancelled'
        cell.cancelled_at = now
        cell.save(update_fields=['status', 'cancelled_at', 'updated_at'])
        return 'cancelled'
    return 'skipped'


@transaction.atomic
def save_classroom_manual_marks(mission, matrix, teacher, changes, version):
    matrix = TeacherWrongBookMatrix.objects.select_for_update().get(pk=matrix.id)
    if int(version) != matrix.version:
        raise MatrixError('矩阵版本已变化，请刷新后重试', 'VERSION_CONFLICT', 409, {'current_version': matrix.version})
    students, questions = _scope(matrix)
    student_map = {str(row.student_id): row for row in students}
    question_map = {str(row.source_question_id): row for row in questions}
    online_map = _student_online_map(mission, students, question_map.keys())
    saved = []
    for change in changes:
        student_id = str(change.get('student_id') or '')
        question_id = str(change.get('source_question_id') or '')
        if student_id not in student_map or question_id not in question_map:
            raise MatrixError('单元格不在当前课堂范围内', 'SCOPE_INVALID', 409)
        if online_map.get(student_id):
            raise MatrixError('该学生已有线上答题，人工统计已锁定', 'ONLINE_DATA_READ_ONLY', 409)
        result = _set_cell(matrix, teacher, student_id, question_map[question_id], bool(change.get('wrong')), 'manual')
        saved.append({'student_id': student_id, 'source_question_id': question_id, 'wrong': bool(change.get('wrong'))})
        _audit(matrix, teacher, 'mark_saved' if result == 'saved' else 'mark_cancelled', payload={
            'source': 'manual', 'student_id': student_id, 'question_id': question_id,
        })
    matrix.version += 1
    matrix.status = 'saved'
    matrix.marked_count = matrix.cells.filter(status__in=VALID_CELL_STATUSES).count()
    matrix.save(update_fields=['version', 'status', 'marked_count', 'updated_at'])
    return saved


def _error(sheet, row, column, code, message):
    return {'sheet': sheet, 'row': row, 'column': column, 'reason_code': code, 'message': message}


def parse_classroom_workbook(matrix, workbook):
    from apps.common.xlsx_reader import read_xlsx_sheets

    if getattr(workbook, 'size', 0) > MAX_IMPORT_BYTES:
        raise MatrixError('文件不能超过 10MB', 'FILE_TOO_LARGE', 400)
    file_name = str(getattr(workbook, 'name', '') or '').lower()
    if not file_name.endswith('.xlsx'):
        raise MatrixError('只支持 .xlsx 文件', 'IMPORT_INVALID', 400)
    try:
        sheets = read_xlsx_sheets(workbook)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, UnicodeError, ElementTree.ParseError) as exc:
        raise MatrixError('Excel 文件格式错误', 'IMPORT_INVALID', 400, {
            'errors': [_error('', 0, '', 'INVALID_XLSX', str(exc)[:200])],
        })
    if len(sheets) > MAX_IMPORT_SHEETS or any(
        len(sheet.rows) > MAX_IMPORT_ROWS or any(len(row) > MAX_IMPORT_COLUMNS for row in sheet.rows)
        for sheet in sheets
    ):
        raise MatrixError('Excel 工作表数据量超出限制', 'IMPORT_INVALID', 400)
    students, questions = _scope(matrix)
    nodes = defaultdict(list)
    question_by_node_no = defaultdict(dict)
    for question in questions:
        node_id = str(question.source_node_id)
        nodes[node_id].append(question)
        number = _question_no(question.node_question_no or question.question_no_snapshot)
        if number in question_by_node_no[node_id]:
            raise MatrixError('同一节点存在重复题号', 'SCOPE_INVALID', 409)
        question_by_node_no[node_id][number] = question
    node_by_name = {}
    for question in questions:
        key = _text(question.node_name_snapshot)
        if key in node_by_name and node_by_name[key] != str(question.source_node_id):
            raise MatrixError('节点名称不唯一，无法导入', 'SCOPE_INVALID', 409)
        node_by_name[key] = str(question.source_node_id)

    student_by_name = defaultdict(list)
    for student in students:
        student_by_name[_text(student.student_name_snapshot)].append(student)
    online_map = _student_online_map(matrix.source_mission, students, [q.source_question_id for q in questions])
    marks = set()
    seen_students_by_sheet = defaultdict(set)
    uploaded_nodes = set()
    total_cells = 0
    errors = []
    for sheet in sheets:
        if sheet.title == 'Sheet1' and sheet.rows and _text(sheet.rows[0][0] if sheet.rows[0] else '') in ('班级名称', '班级'):
            continue
        if len(sheet.rows) < 2:
            errors.append(_error(sheet.title, 1, 'A', 'INVALID_HEADER', '节点工作表缺少表头'))
            continue
        node_id = node_by_name.get(_text(sheet.title))
        if not node_id:
            errors.append(_error(sheet.title, 1, 'A', 'NODE_NOT_FOUND', '工作表不是当前课堂练习节点'))
            continue
        uploaded_nodes.add(node_id)
        headers = sheet.rows[1]
        if not headers or _text(headers[0]) != '姓名':
            errors.append(_error(sheet.title, 2, 'A', 'INVALID_HEADER', 'A2 必须为姓名'))
            continue
        header_map = {}
        for index, value in enumerate(headers[1:], 2):
            number = _question_no(value)
            if not number:
                continue
            if number in header_map:
                errors.append(_error(sheet.title, 2, str(index), 'DUPLICATE_QUESTION_NO', '题号重复'))
            header_map[number] = index
            if number not in question_by_node_no[node_id]:
                errors.append(_error(sheet.title, 2, str(index), 'QUESTION_NOT_FOUND', '题号不属于该节点'))
        for row_index, row in enumerate(sheet.rows[2:], 3):
            name = _text(row[0] if row else '')
            if not name:
                errors.append(_error(sheet.title, row_index, 'A', 'STUDENT_NOT_FOUND', '学生姓名不能为空'))
                continue
            matches = student_by_name.get(name, [])
            if len(matches) != 1:
                errors.append(_error(sheet.title, row_index, 'A', 'AMBIGUOUS_STUDENT' if matches else 'STUDENT_NOT_FOUND', '学生不存在或姓名不唯一'))
                continue
            student = matches[0]
            if str(student.student_id) in seen_students_by_sheet[sheet.title]:
                errors.append(_error(sheet.title, row_index, 'A', 'DUPLICATE_STUDENT', '同一工作表学生重复'))
                continue
            seen_students_by_sheet[sheet.title].add(str(student.student_id))
            if online_map.get(str(student.student_id)):
                errors.append(_error(sheet.title, row_index, 'A', 'ONLINE_DATA_READ_ONLY', '该学生已有线上答题'))
                continue
            for number, column_index in header_map.items():
                value = _text(row[column_index - 1] if column_index - 1 < len(row) else '')
                if value == '':
                    continue
                total_cells += 1
                if value not in ('1', '1.0'):
                    errors.append(_error(sheet.title, row_index, str(column_index), 'INVALID_MARK_VALUE', '单元格只能为 1 或空白'))
                    continue
                marks.add((str(student.student_id), str(question_by_node_no[node_id][number].source_question_id)))

    if not uploaded_nodes:
        errors.append(_error('', 0, '', 'NODE_NOT_FOUND', '至少需要一个匹配当前节点的统计工作表'))
    if errors:
        raise MatrixError('Excel 校验失败', 'IMPORT_INVALID', 400, {'errors': errors})
    return sheets, students, questions, uploaded_nodes, marks, total_cells


def import_classroom_workbook(mission, matrix, teacher, workbook, version, replace_scope='offline_students_in_uploaded_nodes'):
    if replace_scope != 'offline_students_in_uploaded_nodes':
        raise MatrixError('不支持的导入覆盖范围', 'INVALID_REQUEST', 400)
    if int(version) != matrix.version:
        raise MatrixError('矩阵版本已变化，请刷新后重试', 'VERSION_CONFLICT', 409, {'current_version': matrix.version})
    batch = TeacherWrongBookImportBatch.objects.create(
        matrix=matrix,
        uploaded_by=teacher,
        file_name=str(getattr(workbook, 'name', ''))[:255],
        replace_scope=replace_scope,
    )
    try:
        parsed = parse_classroom_workbook(matrix, workbook)
        sheets, students, questions, uploaded_nodes, marks, total_cells = parsed
        with transaction.atomic():
            matrix = TeacherWrongBookMatrix.objects.select_for_update().get(pk=matrix.id)
            if int(version) != matrix.version:
                raise MatrixError('矩阵版本已变化，请刷新后重试', 'VERSION_CONFLICT', 409, {'current_version': matrix.version})
            online_map = _student_online_map(mission, students, [q.source_question_id for q in questions])
            question_by_node = defaultdict(list)
            for question in questions:
                question_by_node[str(question.source_node_id)].append(question)
            imported_count = skipped_count = cancelled_count = 0
            for student in students:
                student_id = str(student.student_id)
                if online_map.get(student_id):
                    continue
                for node_id in uploaded_nodes:
                    for question in question_by_node[node_id]:
                        key = (student_id, str(question.source_question_id))
                        if key in marks:
                            result = _set_cell(matrix, teacher, student_id, question, True, 'import')
                            imported_count += result == 'imported'
                            skipped_count += result == 'skipped'
                        else:
                            result = _set_cell(matrix, teacher, student_id, question, False, 'import')
                            cancelled_count += result == 'cancelled'
                            skipped_count += result == 'skipped'
            changed = imported_count + cancelled_count > 0
            if changed:
                matrix.version += 1
                matrix.status = 'saved'
                matrix.marked_count = matrix.cells.filter(status__in=VALID_CELL_STATUSES).count()
                matrix.save(update_fields=['version', 'status', 'marked_count', 'updated_at'])
            _audit(matrix, teacher, 'import_succeeded', payload={
                'import_batch_id': str(batch.id), 'replace_scope': replace_scope,
                'imported_count': imported_count, 'cancelled_count': cancelled_count,
            })
            batch.status = 'succeeded'
            batch.sheet_count = sum(1 for sheet in sheets if sheet.title != 'Sheet1')
            batch.total_cells = total_cells
            batch.imported_count = imported_count
            batch.skipped_count = skipped_count
            batch.cancelled_count = cancelled_count
            batch.completed_at = timezone.now()
            batch.save(update_fields=['status', 'sheet_count', 'total_cells', 'imported_count', 'skipped_count', 'cancelled_count', 'completed_at'])
        return batch, matrix
    except MatrixError as exc:
        batch.status = 'failed'
        batch.failed_count = len((exc.data or {}).get('errors', [])) or 1
        batch.errors = (exc.data or {}).get('errors', [{
            'reason_code': exc.code, 'message': str(exc), 'sheet': '', 'row': 0, 'column': '',
        }])
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'failed_count', 'errors', 'completed_at'])
        _audit(matrix, teacher, 'import_failed', payload={
            'import_batch_id': str(batch.id), 'replace_scope': replace_scope,
            'error_code': exc.code, 'failed_count': batch.failed_count,
        })
        raise
