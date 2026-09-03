"""Phase 4 teacher wrong-book matrix workflow.

The matrix is intentionally sparse: a row exists only after a teacher marks a
student/question cell.  Student and question membership is snapshotted so a
later change to the source mission cannot silently change a generation batch.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.common.media import media_url
from apps.institutions.models import ClassStudent, ClassTeacher
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from apps.practice.recommendation import QuestionBankWrongbookCandidateProvider, question_display
from apps.study.models import StudentMissionProgress, AnswerAttempt
from apps.wrongbook.models import WrongBookItem

from .models import (
    LearningMission, MissionClassAssignment, MissionQuestionRel,
    RelatedQuestionRecommendation, RelatedQuestionRecommendationCall,
    TeacherWrongBookCell, TeacherWrongBookMatrix, TeacherWrongBookMatrixAudit,
    TeacherWrongBookMatrixQuestion, TeacherWrongBookMatrixStudent,
    WrongBookGenerationBatch, WrongBookGenerationItem,
)
from .services import ensure_flat_assignment_level, ordered_mission_question_rels, question_no_sort_key
from .snapshots import snapshot_payload


class MatrixError(Exception):
    def __init__(self, message, code='invalid', http_status=400, data=None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.data = data or {}


def _sid(value):
    return str(value)


def _audit(matrix, actor, action, trace_id='', batch=None, payload=None):
    return TeacherWrongBookMatrixAudit.objects.create(
        matrix=matrix, actor=actor, action=action, version=matrix.version,
        batch=batch, payload=payload or {}, trace_id=trace_id,
    )


def can_manage_matrix(mission, teacher):
    if str(mission.creator_teacher_id_id) == str(teacher.id):
        return True
    class_ids = list(mission.class_assignments.filter(status='active').values_list('class_obj_id', flat=True))
    if mission.class_obj_id:
        class_ids.append(mission.class_obj_id)
    if ClassTeacher.objects.filter(teacher=teacher, class_obj_id__in=class_ids).exists():
        return True
    if mission.course_id:
        from apps.courses.models import CourseCollaborator
        return CourseCollaborator.objects.filter(
            course_id=mission.course_id, user=teacher, role='editor', status='active',
        ).exists()
    return False


def get_source_mission(mission_id, teacher):
    try:
        mission = LearningMission.objects.select_related('course', 'class_obj').get(pk=mission_id)
    except LearningMission.DoesNotExist:
        raise MatrixError('来源作业不存在', 'not_found', 404)
    if not can_manage_matrix(mission, teacher):
        raise MatrixError('无权管理该作业的学情矩阵', 'forbidden', 403)
    if mission.status != 'published':
        raise MatrixError('只有已发布作业可以建立学情矩阵', 'conflict', 409)
    return mission


def _assignments(mission):
    rows = list(mission.class_assignments.filter(status='active').select_related('class_obj'))
    if rows:
        return rows
    return [mission] if mission.class_obj_id else []


def _students_for_assignment(mission, assignment):
    targets = {_sid(value) for value in (mission.target_student_ids or [])}
    class_id = assignment.class_obj_id
    class_targets = {_sid(value) for value in (getattr(assignment, 'target_student_ids', None) or [])}
    query = ClassStudent.objects.filter(class_obj_id=class_id, status='active')
    effective = class_targets or targets
    if effective:
        query = query.filter(student_id__in=effective)
    return list(query.select_related('student', 'class_obj').order_by('student__display_name', 'student__student_no'))


def _question_snapshot(question):
    image_items = [
        {'id': _sid(image.id), 'file_path': image.file_path, 'url': media_url(image.file_path),
         'image_type': image.image_type, 'placement': image.placement,
         'sort_order': image.sort_order, 'display_width': image.display_width}
        for image in question.images.all().order_by('sort_order')
        if image.file_path and image.image_type != 'formula'
    ]
    options = [
        {'label': option.option_label, 'content': option.content}
        for option in question.options.all().order_by('sort_order')
    ]
    return {
        'id': _sid(question.id), 'question_no': question.question_no,
        'question_type': question.question_type, 'subject': question.subject,
        'stem': question.stem, 'stem_html': question.stem_html,
        'answer': question.answer, 'analysis': question.analysis, 'solution': question.solution,
        'subquestions': question.subquestions or [], 'tables': question.tables or [],
        'knowledge_points': question.knowledge_points,
        'difficulty': float(question.difficulty) if question.difficulty is not None else None,
        'options_html': options, 'image_items': image_items,
    }


def _source_question_rows(mission):
    rels = ordered_mission_question_rels(mission)
    questions = ExamQuestion.objects.filter(id__in=[r.question_id for r in rels]).prefetch_related('images', 'options')
    qmap = {str(q.id): q for q in questions}
    return [(rel, qmap.get(str(rel.question_id))) for rel in rels]


def _normalize_matrix_question_order(matrix):
    """Keep persisted matrix columns aligned with the source mission order.

    Matrix questions are snapshots.  Older matrices may therefore still have
    the order that was stored before natural question-number sorting was
    introduced.  Re-indexing the snapshot rows here fixes those matrices
    without changing cell ownership: cells continue to use source_question_id.
    """
    ordered_relations = ordered_mission_question_rels(matrix.source_mission)
    relation_order = {
        str(relation.question_id): position
        for position, relation in enumerate(ordered_relations, start=1)
    }
    questions = list(matrix.questions.filter(status='active'))
    questions.sort(key=lambda row: (
        relation_order.get(str(row.source_question_id), 10 ** 9),
        question_no_sort_key(row.question_no_snapshot),
        row.sort_no,
        str(row.id),
    ))
    changed = []
    for sort_no, row in enumerate(questions, start=1):
        if row.sort_no != sort_no:
            row.sort_no = sort_no
            changed.append(row)
    if changed:
        TeacherWrongBookMatrixQuestion.objects.bulk_update(changed, ['sort_no'])
    return questions


@transaction.atomic
def get_or_create_matrix(mission, teacher, class_id=None, refresh=False):
    matrix, created = TeacherWrongBookMatrix.objects.select_for_update().get_or_create(
        source_mission=mission,
        defaults={'creator_teacher': teacher, 'class_obj_id': class_id or mission.class_obj_id},
    )
    if matrix.creator_teacher_id != teacher.id and not can_manage_matrix(mission, teacher):
        raise MatrixError('无权管理该矩阵', 'forbidden', 403)
    if class_id:
        assignments = [a for a in _assignments(mission) if _sid(a.class_obj_id) == _sid(class_id)]
        if not assignments:
            raise MatrixError('班级不属于该作业', 'not_found', 404)
    if refresh:
        if matrix.generation_batches.exists():
            raise MatrixError('矩阵已有生成历史，不能刷新范围', 'conflict', 409)
        old_version = matrix.version
        _sync_scope(matrix, teacher, force=True)
        _normalize_matrix_question_order(matrix)
        matrix.version = old_version + 1
        matrix.save(update_fields=['version', 'status', 'updated_at'])
        _audit(matrix, teacher, 'scope_refreshed', payload={'from_version': old_version})
        return matrix
    _sync_scope(matrix, teacher, force=refresh or created)
    _normalize_matrix_question_order(matrix)
    return matrix


def _sync_scope(matrix, teacher, force=False):
    mission = matrix.source_mission
    assignments = _assignments(mission)
    if matrix.class_obj_id:
        assignments = [a for a in assignments if _sid(a.class_obj_id) == _sid(matrix.class_obj_id)]
    expected_students = {}
    for assignment in assignments:
        for member in _students_for_assignment(mission, assignment):
            key = (_sid(member.student_id), _sid(member.class_obj_id))
            expected_students[key] = (member, assignment)
    existing = {(str(row.student_id), str(row.class_obj_id)): row for row in matrix.students.all()}
    changed = False
    for key, (member, assignment) in expected_students.items():
        row = existing.get(key)
        values = {
            'class_obj_id': member.class_obj_id,
            'source_assignment_id': getattr(assignment, 'id', None),
            'student_name_snapshot': member.student.display_name,
            'student_no_snapshot': member.student.student_no or '',
            'class_name_snapshot': member.class_obj.class_name,
            'status': 'active',
        }
        if row is None:
            row = TeacherWrongBookMatrixStudent.objects.create(
                matrix=matrix, student=member.student, sort_no=len(existing), **values,
            )
            existing[key] = row
            changed = True
        elif row.status != 'active' or any(getattr(row, field) != value for field, value in values.items()):
            for field, value in values.items():
                setattr(row, field, value)
            row.save(update_fields=[*values.keys()])
            changed = True
    for key, row in existing.items():
        if key not in expected_students and row.status != 'removed':
            row.status = 'removed'
            row.save(update_fields=['status'])
            changed = True

    expected_questions = {}
    for rel, question in _source_question_rows(mission):
        if question is not None:
            expected_questions[str(rel.question_id)] = (rel, question)
    if not force and (matrix.students.exists() or matrix.questions.exists()):
        current_students = {
            (str(row.student_id), str(row.class_obj_id))
            for row in matrix.students.filter(status='active')
        }
        current_questions = {
            str(row.source_question_id)
            for row in matrix.questions.filter(status='active')
        }
        if current_students != set(expected_students) or current_questions != set(expected_questions):
            if matrix.status not in ('generating', 'closed', 'scope_changed'):
                matrix.status = 'scope_changed'
                matrix.save(update_fields=['status', 'updated_at'])
            return True
    existing_q = {str(row.source_question_id): row for row in matrix.questions.all()}
    for question_id, (rel, question) in expected_questions.items():
        snapshot = _question_snapshot(question)
        row = existing_q.get(question_id)
        values = {
            'source_relation': rel, 'question_no_snapshot': question.question_no,
            'sort_no': rel.sort_no, 'question_snapshot': snapshot, 'status': 'active',
        }
        if row is None:
            TeacherWrongBookMatrixQuestion.objects.create(
                matrix=matrix, source_question_id=question.id, **values,
            )
            changed = True
        elif force and (row.status != 'active' or row.question_snapshot != snapshot):
            for field, value in values.items():
                setattr(row, field, value)
            row.save(update_fields=[*values.keys()])
            changed = True
    for key, row in existing_q.items():
        if key not in expected_questions and row.status != 'removed':
            row.status = 'removed'
            row.save(update_fields=['status'])
            changed = True
    if changed and matrix.status not in ('generating', 'closed'):
        matrix.status = 'scope_changed' if not force else matrix.status
        matrix.save(update_fields=['status', 'updated_at'])
        if force:
            matrix.status = 'saved' if matrix.students.filter(status='active').exists() else 'draft'
            matrix.save(update_fields=['status', 'updated_at'])
    return changed


def matrix_payload(matrix, class_id=None):
    students = matrix.students.filter(status='active')
    if class_id:
        students = students.filter(class_obj_id=class_id)
    students = list(students.order_by('sort_no', 'student_name_snapshot'))
    # A student may be assigned to several source classes, but the matrix is
    # rendered as one student row. The selected class filter is applied above.
    unique_students = {}
    for student in students:
        unique_students.setdefault(str(student.student_id), student)
    students = list(unique_students.values())
    questions = _normalize_matrix_question_order(matrix)
    cells = TeacherWrongBookCell.objects.filter(matrix=matrix).select_related('wrong_book_item')
    if class_id:
        cells = cells.filter(student__student_classes__class_obj_id=class_id)
    cell_map = {(str(c.student_id), str(c.source_question_id)): c for c in cells}
    matrix_question_ids = {str(q.source_question_id) for q in questions}
    rows = []
    for student in students:
        row_cells = []
        for question in questions:
            cell = cell_map.get((str(student.student_id), str(question.source_question_id)))
            row_cells.append({
                'cell_id': str(cell.id) if cell else None,
                'student_id': str(student.student_id),
                'source_question_id': str(question.source_question_id),
                'wrong': bool(cell and cell.status in ('marked', 'generated', 'locked')),
                'status': cell.status if cell else 'normal',
                'wrong_book_item_id': str(cell.wrong_book_item_id) if cell else None,
            })
        rows.append({
            'student_id': str(student.student_id), 'student_name': student.student_name_snapshot,
            'student_no': student.student_no_snapshot, 'class_id': str(student.class_obj_id),
            'class_name': student.class_name_snapshot, 'cells': row_cells,
        })
    # Keep the counts aligned with the cells currently visible in the matrix.
    # A generated/locked cell is historical output and must not be counted as
    # a new item that can be submitted again.
    marked_count = cells.filter(status='marked').count()
    generated_count = cells.filter(status='generated').count()
    locked_count = cells.filter(status='locked').count()
    cancelled_count = cells.filter(status='cancelled').count()
    latest_batch = matrix.generation_batches.first()
    return {
        'matrix_id': str(matrix.id), 'source_mission_id': str(matrix.source_mission_id),
        'class_id': str(matrix.class_obj_id) if matrix.class_obj_id else None,
        'version': matrix.version, 'status': matrix.status,
        'marked_count': marked_count,
        'generated_count': generated_count,
        'locked_count': locked_count,
        'cancelled_count': cancelled_count,
        'has_generation_history': latest_batch is not None,
        'latest_batch': batch_payload(latest_batch) if latest_batch else None,
        'failed_count': matrix.failed_count, 'students': rows,
        'questions': [{
            'id': str(q.source_question_id), 'question_no': q.question_no_snapshot,
            'sort_no': q.sort_no, 'snapshot': q.question_snapshot,
        } for q in questions],
    }


@transaction.atomic
def save_marks(matrix, teacher, changes, version, trace_id=''):
    matrix = TeacherWrongBookMatrix.objects.select_for_update().get(pk=matrix.id)
    if matrix.status in ('closed', 'scope_changed'):
        raise MatrixError('矩阵范围已变化或已关闭，请先查看历史或刷新范围', 'conflict', 409)
    if int(version) != matrix.version:
        raise MatrixError('矩阵版本已变化，请刷新后重试', 'version_conflict', 409, {'current_version': matrix.version})
    valid_students = {(str(x.student_id), str(x.class_obj_id)) for x in matrix.students.filter(status='active')}
    valid_questions = {str(x.source_question_id): x for x in matrix.questions.filter(status='active')}
    now = timezone.now()
    saved = []
    for change in changes:
        student_id = _sid(change.get('student_id'))
        question_id = _sid(change.get('source_question_id') or change.get('question_id'))
        if not change.get('student_id') or question_id not in valid_questions:
            raise MatrixError('矩阵单元格不在当前快照范围内', 'scope_conflict', 409)
        if not any(item[0] == student_id for item in valid_students):
            raise MatrixError('学生不在当前矩阵范围内', 'scope_conflict', 409)
        marked = bool(change.get('wrong'))
        cell = TeacherWrongBookCell.objects.filter(
            matrix=matrix, student_id=student_id, source_question_id=question_id,
        ).first()
        if marked:
            relation = valid_questions[question_id].source_relation
            if relation.target_student_ids and student_id not in {_sid(x) for x in relation.target_student_ids}:
                relation = next((candidate for candidate in MissionQuestionRel.objects.filter(
                    mission=matrix.source_mission, question_id=question_id,
                ).order_by('sort_no', 'id') if not candidate.target_student_ids or student_id in {
                    _sid(x) for x in candidate.target_student_ids
                }), None)
                if relation is None:
                    raise MatrixError('来源题目不是该学生可见的作业题', 'source_relation_conflict', 409)
            wrong_item, _ = WrongBookItem.objects.get_or_create(
                student_user_id_id=student_id, question_id=question_id,
            )
            if cell is None:
                cell = TeacherWrongBookCell.objects.create(
                    matrix=matrix, student_id=student_id, source_question_id=question_id,
                    source_relation=relation,
                    wrong_book_item=wrong_item, status='marked', marked_by=teacher,
                    marked_at=now,
                )
            else:
                cell.status = 'marked'
                cell.wrong_book_item = wrong_item
                cell.source_relation = relation
                cell.marked_by = teacher
                cell.marked_at = now
                cell.cancelled_at = None
                cell.save(update_fields=['status', 'wrong_book_item', 'source_relation', 'marked_by', 'marked_at', 'cancelled_at', 'updated_at'])
            _audit(matrix, teacher, 'mark_saved', trace_id, payload={'student_id': student_id, 'question_id': question_id})
        elif cell is not None:
            cell.status = 'cancelled'
            cell.cancelled_at = now
            cell.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            _audit(matrix, teacher, 'mark_cancelled', trace_id, payload={'student_id': student_id, 'question_id': question_id})
        saved.append({'student_id': student_id, 'source_question_id': question_id, 'wrong': marked})
    matrix.version += 1
    matrix.status = 'saved'
    matrix.marked_count = matrix.cells.filter(status__in=('marked', 'generated', 'locked')).count()
    matrix.save(update_fields=['version', 'status', 'marked_count', 'updated_at'])
    return matrix, saved


def _source_deadline(source, generated_at):
    if source.end_at and source.end_at > generated_at:
        return source.end_at
    return generated_at + timedelta(days=7)


def _mission_name(source, suffix='', target_students=None):
    date_text = timezone.localtime(timezone.now()).strftime('%Y%m%d')
    student_ids = list(dict.fromkeys(_sid(student_id) for student_id in (target_students or [])))
    if not student_ids:
        return f'{source.mission_name}-错题练习-{date_text}{suffix}'
    users = {
        _sid(user.id): user
        for user in UserAccount.objects.filter(id__in=student_ids, status='active')
    }
    labels = [
        (users[student_id].display_name or users[student_id].login_name or users[student_id].mobile).strip()
        for student_id in student_ids
        if student_id in users
    ]
    if not labels:
        return f'{source.mission_name}-错题练习-{date_text}{suffix}'
    shown_labels = labels[:3]
    student_label = '、'.join(shown_labels)
    if len(labels) > len(shown_labels):
        student_label = f'{student_label}等{len(labels)}人'
    return f'{source.mission_name}-错题练习-{date_text}-{student_label}{suffix}'[:120]


def _create_progress_and_assignments(mission, source, students):
    source_assignments = _assignments(source)
    student_set = {_sid(x) for x in students}
    for assignment in source_assignments:
        members = {_sid(x.student_id) for x in _students_for_assignment(source, assignment)} & student_set
        if not members:
            continue
        MissionClassAssignment.objects.get_or_create(
            mission=mission, class_obj_id=assignment.class_obj_id,
            defaults={
                'start_at': mission.start_at, 'end_at': mission.end_at,
                'target_student_ids': sorted(members),
            },
        )
    for student_id in students:
        StudentMissionProgress.objects.get_or_create(
            mission=mission, student_user_id_id=student_id,
            defaults={'progress_status': 'not_started', 'progress_percent': 0},
        )


def _candidate_questions(item, limit):
    result = QuestionBankWrongbookCandidateProvider().recommend_for_wrong_item(
        student=item.student, wrong_item=item.source_wrong_book_item, limit=limit,
    )
    candidate_items = result.get('items', [])
    visible_ids = set(ExamQuestion.objects.filter(
        id__in=[candidate['id'] for candidate in candidate_items],
    ).filter(
        Q(paper__uploaded_by__isnull=True) | Q(paper__uploaded_by=item.batch.requested_by_id),
    ).values_list('id', flat=True))
    candidate_items = [candidate for candidate in candidate_items if candidate['id'] in {_sid(x) for x in visible_ids}]
    historical_ids = set(MissionQuestionRel.objects.filter(
        source_student_id=item.student_id, source_role='related_question',
    ).values_list('question_id', flat=True))
    candidate_items = [candidate for candidate in candidate_items if candidate['id'] not in {_sid(x) for x in historical_ids}]
    return candidate_items[:limit], result.get('meta', {})


def _create_published_mission(source, matrix, batch, selections, suffix='', include_original=True):
    """Create one per-batch mission; each relation carries its student target."""
    if not selections:
        return None
    generated_at = timezone.now()
    target_students = sorted({_sid(row['student_id']) for row in selections})
    parent_id = None
    if suffix:
        parent_id = LearningMission.objects.filter(
            source_generation_batch_id=batch.id, mission_kind='wrongbook_personal',
        ).order_by('created_at').values_list('id', flat=True).first()
    mission = LearningMission.objects.create(
        mission_name=_mission_name(source, suffix, target_students=target_students), goal_text='教师学情矩阵错题练习',
        creator_teacher_id=source.creator_teacher_id, start_at=generated_at,
        end_at=_source_deadline(source, generated_at), status='draft',
        assignment_mode='flat', mission_kind='wrongbook_personal', source_type='teacher_matrix',
        source_matrix_id=matrix.id, source_generation_batch_id=batch.id,
        parent_mission_id=parent_id,
        class_obj_id=source.class_obj_id, target_student_ids=target_students,
        course_id=source.course_id,
    )
    level = ensure_flat_assignment_level(mission)
    _create_progress_and_assignments(mission, source, target_students)
    sort_no = 0
    seen = set()
    for row in selections:
        student_id = _sid(row['student_id'])
        wrong_item_id = row.get('wrong_book_item_id')
        original_id = _sid(row['source_question_id'])
        original_snapshot = row.get('original_snapshot') or {}
        key = (student_id, original_id, _sid(wrong_item_id))
        if include_original and key not in seen and original_snapshot:
            MissionQuestionRel.objects.create(
                mission=mission, level=level, question_id=original_id, sort_no=sort_no,
                source_type='teacher_matrix', target_student_ids=[student_id],
                question_snapshot=original_snapshot, source_matrix_id=matrix.id,
                source_student_id=student_id, source_wrong_book_item_id=wrong_item_id,
                source_role='original_wrong', source_provider='rule',
            )
            seen.add(key)
            sort_no += 1
        for candidate in row.get('related', []):
            candidate_id = _sid(candidate['id'])
            relation_key = (student_id, candidate_id, _sid(wrong_item_id))
            if relation_key in seen:
                continue
            question = ExamQuestion.objects.filter(pk=candidate_id).prefetch_related('images', 'options').first()
            if question is None:
                continue
            MissionQuestionRel.objects.create(
                mission=mission, level=level, question_id=question.id, sort_no=sort_no,
                source_type='teacher_matrix', target_student_ids=[student_id],
                question_snapshot=_question_snapshot(question), source_matrix_id=matrix.id,
                source_student_id=student_id, source_wrong_book_item_id=wrong_item_id,
                source_role='related_question', source_provider=row.get('provider', 'rule'),
            )
            seen.add(relation_key)
            sort_no += 1
    if not MissionQuestionRel.objects.filter(mission=mission).exists():
        mission.delete()
        return None
    return mission


def publish_generated_mission(mission):
    from .pdf_service import ensure_mission_pdf
    ensure_mission_pdf(mission)
    mission.status = 'published'
    mission.save(update_fields=['status', 'updated_at'])
    return mission


def generate_batch(batch_id):
    batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
    matrix = batch.matrix
    source = matrix.source_mission
    batch.status = 'generating'
    batch.started_at = timezone.now()
    batch.save(update_fields=['status', 'started_at'])
    selections = []
    failed = 0
    items = list(batch.items.select_related('cell', 'student', 'source_wrong_book_item'))
    for item in items:
        try:
            error_stage = 'candidate'
            item.status = 'generating'
            item.save(update_fields=['status', 'updated_at'])
            qrow = matrix.questions.filter(source_question_id=item.source_question_id, status='active').first()
            if qrow is None:
                error_stage = 'snapshot'
                raise MatrixError('原题快照不存在', 'snapshot_failed')
            candidates, meta = _candidate_questions(item, batch.related_limit)
            item.related_question_ids = [str(x['id']) for x in candidates]
            item.selected_count = len(candidates)
            item.shortage_reason = meta.get('insufficient_reason') or ''
            item.result_json = {'meta': meta}
            item.status = 'generated'
            item.save(update_fields=['related_question_ids', 'selected_count', 'shortage_reason', 'result_json', 'status', 'updated_at'])
            selections.append({
                'student_id': item.student_id, 'source_question_id': item.source_question_id,
                'wrong_book_item_id': item.source_wrong_book_item_id,
                'original_snapshot': qrow.question_snapshot, 'related': candidates, 'provider': 'rule',
            })
        except Exception as exc:
            failed += 1
            item.status = 'failed'
            item.error_code = getattr(exc, 'code', 'generation_error')
            item.error_stage = error_stage
            item.error_message = str(exc)[:500]
            item.save(update_fields=['status', 'error_code', 'error_stage', 'error_message', 'updated_at'])
    mission = None
    try:
        batch.status = 'snapshotting'
        batch.save(update_fields=['status'])
        mission = _create_published_mission(source, matrix, batch, selections)
        if mission:
            publish_generated_mission(mission)
            WrongBookGenerationItem.objects.filter(batch=batch, status='generated').update(
                target_mission=mission, status='published',
            )
            TeacherWrongBookCell.objects.filter(
                matrix=matrix, id__in=[item.cell_id for item in items if item.status == 'generated'],
            ).update(status='generated', generated_batch_id=batch.id)
    except Exception as exc:
        failed += 1
        batch.error_json = {'code': 'publish_error', 'message': str(exc)[:500]}
        WrongBookGenerationItem.objects.filter(batch=batch, status='generated').update(
            status='publish_failed', error_code='publish_error', error_stage='publish', error_message=str(exc)[:500],
        )
    batch.generated_count = len(selections)
    batch.failed_count = failed
    batch.published_task_count = 1 if mission and mission.status == 'published' else 0
    batch.status = 'partially_failed' if failed else ('published' if mission else 'failed')
    batch.completed_at = timezone.now()
    batch.save(update_fields=['generated_count', 'failed_count', 'published_task_count', 'status', 'completed_at', 'error_json'])
    matrix.last_generation_batch_id = batch.id
    matrix.generated_count = matrix.cells.filter(status='generated').count()
    matrix.failed_count = failed
    matrix.status = 'partially_failed' if failed else ('generated' if mission else 'saved')
    matrix.save(update_fields=['last_generation_batch_id', 'generated_count', 'failed_count', 'status', 'updated_at'])
    return batch


@transaction.atomic
def request_generation(matrix, teacher, version, idempotency_key, cell_ids=None, related_limit=3, trace_id=''):
    if not idempotency_key:
        raise MatrixError('idempotency_key 必填', 'invalid')
    if int(version) != matrix.version:
        raise MatrixError('矩阵版本已变化，请刷新后重试', 'version_conflict', 409, {'current_version': matrix.version})
    if related_limit != 3:
        raise MatrixError('本阶段关联题数量固定为每名学生最多 3 道', 'invalid')
    if matrix.status in ('closed', 'scope_changed'):
        raise MatrixError('矩阵范围已变化或已关闭，请先查看历史或刷新范围', 'conflict', 409)
    if cell_ids:
        requested = [str(value) for value in cell_ids]
        selected = list(matrix.cells.filter(id__in=requested).select_related('student', 'wrong_book_item'))
        by_id = {str(cell.id): cell for cell in selected}
        invalid = [value for value in requested if value not in by_id or by_id[value].status != 'marked']
        if invalid:
            raise MatrixError('只能生成当前状态为 marked 的矩阵单元格', 'cell_conflict', 409, {'cell_ids': invalid})
        cells = [by_id[value] for value in dict.fromkeys(requested)]
    else:
        cells = list(matrix.cells.filter(status='marked').select_related('student', 'wrong_book_item'))
    requested_ids = sorted(str(cell.id) for cell in cells)
    batch = WrongBookGenerationBatch.objects.filter(matrix=matrix, idempotency_key=idempotency_key).first()
    if batch:
        if batch.request_version != int(version) or sorted(batch.request_cell_ids or []) != requested_ids:
            raise MatrixError('相同幂等键不能用于不同版本或不同单元格集合', 'idempotency_conflict', 409)
        return batch
    if not cells:
        raise MatrixError('没有可生成的已标记错题', 'no_marked_cells')
    batch = WrongBookGenerationBatch.objects.create(
        matrix=matrix, requested_by=teacher, request_version=matrix.version,
        request_cell_ids=sorted(str(cell.id) for cell in cells), related_limit=3,
        requested_count=len(cells), idempotency_key=idempotency_key,
    )
    WrongBookGenerationItem.objects.bulk_create([
        WrongBookGenerationItem(
            batch=batch, cell=cell, student_id=cell.student_id,
            source_question_id=cell.source_question_id,
            source_wrong_book_item_id=cell.wrong_book_item_id,
        ) for cell in cells
    ])
    matrix.status = 'generating'
    matrix.last_generation_batch_id = batch.id
    matrix.save(update_fields=['status', 'last_generation_batch_id', 'updated_at'])
    _audit(matrix, teacher, 'generation_requested', trace_id, batch=batch, payload={'cell_count': len(cells)})
    from .tasks import generate_wrongbook_batch_task
    transaction.on_commit(lambda: generate_wrongbook_batch_task.delay(str(batch.id)))
    return batch


def batch_payload(batch):
    final_mission_id = batch.final_mission_id
    # Legacy generation batches were created before final_mission_id was
    # persisted. Resolve the published mission by its stable batch marker so
    # the UI can still point teachers to an already generated exercise.
    if not final_mission_id:
        final_mission_id = LearningMission.objects.filter(
            source_generation_batch_id=batch.id, status='published',
        ).order_by('-created_at').values_list('id', flat=True).first()
    return {
        'id': str(batch.id), 'matrix_id': str(batch.matrix_id), 'status': batch.status,
        'request_version': batch.request_version, 'related_limit': batch.related_limit,
        'generation_mode': batch.generation_mode, 'candidate_limit': batch.candidate_limit,
        'selection_limit': batch.selection_limit, 'selection_required': batch.status == 'awaiting_selection',
        'final_mission_id': str(final_mission_id) if final_mission_id else None,
        'requested_count': batch.requested_count, 'generated_count': batch.generated_count,
        'failed_count': batch.failed_count, 'published_task_count': batch.published_task_count,
        'created_at': batch.created_at, 'completed_at': batch.completed_at, 'error': batch.error_json,
        'items': [{
            'id': str(i.id), 'cell_id': str(i.cell_id), 'student_id': str(i.student_id),
            'source_question_id': str(i.source_question_id), 'related_question_ids': i.related_question_ids,
            'selected_question_ids': i.selected_question_ids, 'selected_count': i.selected_count,
            'selection_required': i.selection_required, 'shortage_reason': i.shortage_reason,
            'status': i.status, 'target_mission_id': str(i.target_mission_id) if i.target_mission_id else None,
            'error_stage': i.error_stage, 'error_code': i.error_code, 'error_message': i.error_message,
        } for i in batch.items.all().order_by('created_at')],
    }


def batch_recommendations(batch, teacher, limit=10, trace_id='', allow_unpublished=False):
    if not allow_unpublished and (batch.status not in ('published', 'partially_failed') or not batch.published_task_count):
        raise MatrixError('基础错题练习尚未发布，暂不能请求推荐', 'conflict', 409)
    limit = int(limit)
    if limit < 1 or limit > 10:
        raise MatrixError('AI 推荐每道错题最多请求 10 道', 'invalid')
    call = RelatedQuestionRecommendationCall.objects.create(
        matrix=batch.matrix, source_batch=batch, provider='ai', model_name='strict-question-bank-fallback',
        prompt_version='phase4-v1', request_json={'limit': limit}, trace_id=trace_id,
    )
    existing = set()
    created = []
    for item in batch.items.select_related('student', 'source_wrong_book_item'):
        used = set(MissionQuestionRel.objects.filter(
            mission__source_generation_batch_id=batch.id, source_student_id=item.student_id,
            source_wrong_book_item_id=item.source_wrong_book_item_id,
        ).values_list('question_id', flat=True))
        candidates, _ = _candidate_questions(item, limit)
        for rank, candidate in enumerate(candidates):
            qid = candidate['id']
            if qid in used:
                continue
            rec, made = RelatedQuestionRecommendation.objects.get_or_create(
                matrix=batch.matrix, source_batch=batch, source_student_id=item.student_id,
                source_question_id=item.source_question_id, source_wrong_book_item_id=item.source_wrong_book_item_id,
                candidate_question_id=qid,
                defaults={
                    'provider': 'ai', 'model_name': 'strict-question-bank-fallback',
                    'prompt_version': 'phase4-v1', 'score': max(0, 1 - rank / 10),
                    'confidence': max(0, 1 - rank / 10), 'requested_by': teacher,
                    'result_json': {'candidate': candidate, 'fallback': True},
                },
            )
            if made:
                created.append(rec)
                existing.add((item.student_id, item.source_wrong_book_item_id, qid))
    call.returned_count = len(created)
    call.status = 'succeeded'
    call.save(update_fields=['returned_count', 'status'])
    _audit(batch.matrix, teacher, 'recommendation_requested', trace_id, batch=batch, payload={'count': len(created)})
    return list(RelatedQuestionRecommendation.objects.filter(source_batch=batch).order_by('source_student_id', '-score', 'id'))


@transaction.atomic
def confirm_recommendations(batch, teacher, recommendation_ids, idempotency_key='', trace_id=''):
    if idempotency_key:
        if batch.ai_confirmation_key and batch.ai_confirmation_key != idempotency_key:
            raise MatrixError('该批次已经使用了其他 AI 确认幂等键', 'conflict', 409)
        if batch.ai_confirmation_key == idempotency_key and batch.ai_supplement_mission_id:
            return LearningMission.objects.get(pk=batch.ai_supplement_mission_id)
    recs = list(RelatedQuestionRecommendation.objects.select_for_update().filter(
        source_batch=batch, id__in=recommendation_ids, status='suggested',
    ))
    if len(recs) != len(set(map(str, recommendation_ids))):
        raise MatrixError('存在不可确认的推荐记录', 'invalid')
    if not recs:
        raise MatrixError('recommendation_ids 不能为空', 'invalid')
    grouped = {}
    for rec in recs:
        grouped.setdefault((rec.source_student_id, rec.source_wrong_book_item_id), []).append(rec)
    for key, values in grouped.items():
        used_count = MissionQuestionRel.objects.filter(
            mission__source_generation_batch_id=batch.id, source_student_id=key[0], source_wrong_book_item_id=key[1],
            source_role='related_question',
        ).count()
        if used_count + len(values) > 3:
            raise MatrixError('每名学生每道错题最多保留 3 道关联题', 'slot_conflict', 409)
    selections = []
    for rec in recs:
        q = ExamQuestion.objects.filter(pk=rec.candidate_question_id).prefetch_related('images', 'options').first()
        if q is None:
            raise MatrixError('推荐题目已不存在', 'not_found', 404)
        item = batch.items.filter(student_id=rec.source_student_id, source_wrong_book_item_id=rec.source_wrong_book_item_id).first()
        qrow = batch.matrix.questions.filter(source_question_id=rec.source_question_id, status='active').first()
        if item is None or qrow is None:
            raise MatrixError('推荐来源快照不存在', 'conflict', 409)
        selections.append({
            'student_id': rec.source_student_id, 'source_question_id': rec.source_question_id,
            'wrong_book_item_id': rec.source_wrong_book_item_id, 'original_snapshot': qrow.question_snapshot,
            'related': [{'id': str(q.id), **question_display(q)}], 'provider': 'ai',
        })
    mission = _create_published_mission(
        batch.matrix.source_mission, batch.matrix, batch, selections,
        suffix='-AI补充', include_original=False,
    )
    if mission is None:
        raise MatrixError('无法生成 AI 补充任务', 'publish_error')
    publish_generated_mission(mission)
    if idempotency_key:
        batch.ai_confirmation_key = idempotency_key
        batch.ai_supplement_mission_id = mission.id
        batch.save(update_fields=['ai_confirmation_key', 'ai_supplement_mission_id'])
    for rec in recs:
        rec.status = 'teacher_selected'
        rec.confirmed_by = teacher
        rec.save(update_fields=['status', 'confirmed_by', 'updated_at'])
    _audit(batch.matrix, teacher, 'recommendation_confirmed', trace_id, batch=batch, payload={'count': len(recs), 'mission_id': str(mission.id)})
    return mission


def summary_payload(matrix, class_id=None):
    students = matrix.students.filter(status='active')
    if class_id:
        students = students.filter(class_obj_id=class_id)
    student_ids = list(students.values_list('student_id', flat=True))
    cells = matrix.cells.filter(student_id__in=student_ids).exclude(status='cancelled')
    counts = {str(row['student_id']): row['count'] for row in cells.values('student_id').annotate(count=Count('id'))}
    generated = {str(row['student_id']): row['count'] for row in cells.filter(status='generated').values('student_id').annotate(count=Count('id'))}
    question_counts = {str(row['source_question_id']): row['count'] for row in cells.values('source_question_id').annotate(count=Count('id'))}
    mission_ids = list(LearningMission.objects.filter(source_matrix_id=matrix.id).values_list('id', flat=True))
    attempts = list(AnswerAttempt.objects.filter(
        mission_id__in=mission_ids, student_user_id__in=student_ids,
    ).order_by('submitted_at'))
    latest = {}
    for attempt in attempts:
        latest[(str(attempt.student_user_id_id), str(attempt.question_id))] = attempt
    answer_stats = {}
    for (student_key, _), attempt in latest.items():
        row = answer_stats.setdefault(student_key, {'submitted_count': 0, 'correct_count': 0, 'pending_review_count': 0})
        row['submitted_count'] += 1
        if attempt.is_subjective_pending:
            row['pending_review_count'] += 1
        elif attempt.is_correct:
            row['correct_count'] += 1
    rows = []
    for student in students.order_by('sort_no'):
        rows.append({'student_id': str(student.student_id), 'student_name': student.student_name_snapshot,
                     'wrong_count': counts.get(str(student.student_id), 0),
                     'generated_count': generated.get(str(student.student_id), 0),
                     **answer_stats.get(str(student.student_id), {
                         'submitted_count': 0, 'correct_count': 0, 'pending_review_count': 0,
                     })})
    return {
        'matrix_id': str(matrix.id), 'version': matrix.version,
        'marked_count': cells.count(), 'marked_student_count': len({str(x) for x in cells.values_list('student_id', flat=True)}),
        'question_marked_counts': question_counts, 'students': rows,
    }


def student_history_payload(matrix, student_id):
    member = matrix.students.filter(status='active', student_id=student_id).first()
    if member is None:
        raise MatrixError('学生不在当前矩阵范围内', 'not_found', 404)
    cells = matrix.cells.filter(student_id=student_id).select_related('wrong_book_item').order_by('source_question_id')
    items = []
    for cell in cells:
        generation_items = list(cell.generation_items.select_related('batch', 'target_mission').order_by('-created_at'))
        attempts = []
        for generation in generation_items:
            if generation.target_mission_id:
                attempts.extend(AnswerAttempt.objects.filter(
                    mission_id=generation.target_mission_id, student_user_id=student_id,
                    question_id__in=[cell.source_question_id, *(generation.related_question_ids or [])],
                ).order_by('-submitted_at')[:20])
        items.append({
            'cell_id': str(cell.id), 'source_question_id': str(cell.source_question_id),
            'status': cell.status, 'wrong_book_item_id': str(cell.wrong_book_item_id),
            'batches': [{
                'batch_id': str(g.batch_id), 'status': g.status,
                'related_question_ids': g.related_question_ids,
                'mission_id': str(g.target_mission_id) if g.target_mission_id else None,
                'shortage_reason': g.shortage_reason,
            } for g in generation_items],
            'attempts': [{
                'question_id': str(a.question_id), 'is_correct': a.is_correct,
                'score': float(a.score), 'submitted_at': a.submitted_at,
            } for a in attempts],
        })
    return {
        'matrix_id': str(matrix.id), 'student_id': str(member.student_id),
        'student_name': member.student_name_snapshot, 'student_no': member.student_no_snapshot,
        'items': items,
    }
