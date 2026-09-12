"""Assignment-level learning statistics for a teacher's class overview."""

from collections import defaultdict

from django.db import DatabaseError, connection

from apps.common.subject_codes import normalize_subject_code
from apps.missions.models import LearningMission
from apps.missions.services import ordered_mission_question_rels
from apps.missions.snapshots import apply_snapshot_to_question, snapshot_payload
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt
from apps.knowledge.models import KnowledgePoint

from .models import ClassStudent


def _rate(numerator, denominator):
    return round(numerator * 100 / denominator, 2) if denominator else 0


def _student_status(answered_count, question_count, pending_count):
    if not answered_count:
        return '未开始'
    if answered_count < question_count:
        return '进行中'
    return '已提交' if pending_count else '已批改'


def _mission_student_ids(mission, class_student_ids, assignment=None):
    """Resolve the students who should be included for one class assignment."""
    candidates = {str(value) for value in class_student_ids}
    targets = set()
    if assignment is not None:
        targets = {str(value) for value in (assignment.target_student_ids or [])}
    if not targets:
        targets = {str(value) for value in (mission.target_student_ids or [])}
    return candidates & targets if targets else candidates


def _load_question_rows(mission):
    """Load unique required questions in the canonical mission order."""
    relations = [
        relation
        for relation in ordered_mission_question_rels(mission)
        if relation.is_required
    ]
    question_ids = list(dict.fromkeys(str(relation.question_id) for relation in relations))
    question_map = {
        str(question.id): question
        for question in ExamQuestion.objects.filter(id__in=question_ids).prefetch_related('images', 'options')
    }
    relation_map = {}
    targets_by_question = {}
    for relation in relations:
        question_id = str(relation.question_id)
        if question_id not in question_map:
            continue
        relation_map.setdefault(question_id, relation)
        targets = {str(value) for value in (relation.target_student_ids or [])}
        if question_id not in targets_by_question:
            targets_by_question[question_id] = targets or None
        elif not targets:
            targets_by_question[question_id] = None
        elif targets_by_question[question_id] is not None:
            targets_by_question[question_id].update(targets)

    return [
        {
            'id': question_id,
            'display_no': display_no,
            'question_no': str(
                snapshot_payload(question, relation_map[question_id]).get('question_no') or ''
            ),
            'assigned_student_ids': sorted(targets_by_question.get(question_id) or []),
        }
        for display_no, question_id in enumerate(relation_map, start=1)
        for question in [question_map[question_id]]
    ]


def _assignment_for_class(mission, class_id):
    return mission.class_assignments.filter(
        class_obj_id=class_id, status='active',
    ).first()


def build_class_learning_stats(class_obj):
    """Build class overview data grouped by assignment.

    The returned students field keeps the old aggregate contract. The new
    missions field contains assignment-level and student-level statistics.
    Every answer count uses only the latest non-draft attempt per
    student/mission/question.
    """
    class_students = list(
        ClassStudent.objects.filter(class_obj=class_obj, status='active')
        .select_related('student')
    )
    class_student_ids = [str(item.student_id) for item in class_students]
    class_student_id_set = set(class_student_ids)

    mission_ids = list(
        LearningMission.objects.filter(class_obj_id=class_obj.id)
        .values_list('id', flat=True)
    )
    assignment_mission_ids = list(
        LearningMission.objects.filter(
            class_assignments__class_obj_id=class_obj.id,
            class_assignments__status='active',
        ).values_list('id', flat=True)
    )
    all_mission_ids = list(dict.fromkeys(mission_ids + assignment_mission_ids))
    missions = list(
        LearningMission.objects.filter(id__in=all_mission_ids)
        .order_by('-created_at', '-id')
    )

    mission_context = {}
    all_question_ids = set()
    for mission in missions:
        assignment = _assignment_for_class(mission, class_obj.id)
        student_ids = _mission_student_ids(mission, class_student_id_set, assignment)
        questions = _load_question_rows(mission)
        question_ids = [row['id'] for row in questions]
        all_question_ids.update(question_ids)
        applicable_by_question = {}
        applicable_question_count = defaultdict(int)
        for question in questions:
            targets = set(question['assigned_student_ids'])
            applicable_students = student_ids & targets if targets else student_ids
            applicable_by_question[question['id']] = applicable_students
            for student_id in applicable_students:
                applicable_question_count[student_id] += 1
        mission_context[str(mission.id)] = {
            'mission': mission,
            'student_ids': student_ids,
            'questions': questions,
            'applicable_by_question': applicable_by_question,
            'applicable_question_count': applicable_question_count,
        }

    attempts = AnswerAttempt.objects.filter(
        mission_id__in=[str(mission.id) for mission in missions],
        student_user_id__in=class_student_id_set,
        question_id__in=all_question_ids,
    ).exclude(submit_source='draft').order_by(
        'mission_id', 'student_user_id', 'question_id',
        '-submitted_at', '-attempt_no',
    )
    latest = {}
    for attempt in attempts:
        key = (
            str(attempt.mission_id),
            str(attempt.student_user_id_id),
            str(attempt.question_id),
        )
        latest.setdefault(key, attempt)

    mission_rows = []
    per_student = {
        student_id: {
            'mission_count': 0,
            'completed_count': 0,
            'attempt_count': 0,
            'correct_count': 0,
            'wrong_count': 0,
            'pending_count': 0,
        }
        for student_id in class_student_ids
    }
    total_expected = total_answered = total_completed = 0
    total_correct = total_wrong = total_pending = 0

    for context in mission_context.values():
        mission = context['mission']
        student_ids = context['student_ids']
        questions = context['questions']
        mission_student_rows = []
        mission_correct = mission_wrong = mission_pending = mission_answered = 0
        completed_count = mission_expected = 0

        for class_student in class_students:
            student_id = str(class_student.student_id)
            if student_id not in student_ids:
                continue
            question_count = context['applicable_question_count'].get(student_id, 0)
            mission_expected += question_count
            answered_count = correct_count = wrong_count = pending_count = 0
            for question in questions:
                question_id = question['id']
                if student_id not in context['applicable_by_question'][question_id]:
                    continue
                attempt = latest.get((str(mission.id), student_id, question_id))
                if attempt is None:
                    continue
                answered_count += 1
                if attempt.is_subjective_pending:
                    pending_count += 1
                elif attempt.is_correct:
                    correct_count += 1
                else:
                    wrong_count += 1

            completed = bool(question_count and answered_count >= question_count)
            mission_student_rows.append({
                'student_id': student_id,
                'student_name': class_student.student.display_name or class_student.student.mobile,
                'mobile': class_student.student.mobile,
                'question_count': question_count,
                'answered_count': answered_count,
                'completion_rate': _rate(answered_count, question_count),
                'correct_count': correct_count,
                'wrong_count': wrong_count,
                'pending_count': pending_count,
                'accuracy': _rate(correct_count, correct_count + wrong_count),
                'status': _student_status(answered_count, question_count, pending_count),
            })

            aggregate = per_student[student_id]
            aggregate['mission_count'] += 1
            aggregate['completed_count'] += int(completed)
            aggregate['attempt_count'] += answered_count
            aggregate['correct_count'] += correct_count
            aggregate['wrong_count'] += wrong_count
            aggregate['pending_count'] += pending_count
            total_expected += question_count
            total_answered += answered_count
            total_correct += correct_count
            total_wrong += wrong_count
            total_pending += pending_count
            mission_answered += answered_count
            mission_correct += correct_count
            mission_wrong += wrong_count
            mission_pending += pending_count
            completed_count += int(completed)

        assigned_count = len(student_ids)
        mission_rows.append({
            'mission_id': str(mission.id),
            'mission_name': mission.mission_name,
            'mission_no': mission.mission_no,
            'status': mission.status,
            'created_at': mission.created_at.isoformat() if mission.created_at else None,
            'start_at': mission.start_at.isoformat() if mission.start_at else None,
            'end_at': mission.end_at.isoformat() if mission.end_at else None,
            'question_count': len(questions),
            'student_count': assigned_count,
            'expected_answer_count': mission_expected,
            'completed_count': completed_count,
            'completion_rate': _rate(completed_count, assigned_count),
            'answer_count': mission_answered,
            'correct_count': mission_correct,
            'wrong_count': mission_wrong,
            'pending_count': mission_pending,
            'accuracy': _rate(mission_correct, mission_correct + mission_wrong),
            'students': mission_student_rows,
        })
        total_completed += completed_count

    students = []
    for class_student in class_students:
        student_id = str(class_student.student_id)
        aggregate = per_student[student_id]
        students.append({
            'student_id': student_id,
            'student_name': class_student.student.display_name or class_student.student.mobile,
            'mobile': class_student.student.mobile,
            'mission_count': aggregate['mission_count'],
            'completed_count': aggregate['completed_count'],
            'attempt_count': aggregate['attempt_count'],
            'correct_count': aggregate['correct_count'],
            'wrong_count': aggregate['wrong_count'],
            'pending_count': aggregate['pending_count'],
            'accuracy': _rate(
                aggregate['correct_count'],
                aggregate['correct_count'] + aggregate['wrong_count'],
            ),
        })

    mission_student_total = sum(row['student_count'] for row in mission_rows)
    return {
        'class_id': str(class_obj.id),
        'class_name': class_obj.class_name,
        'mission_count': len(mission_rows),
        'student_count': len(class_students),
        'summary': {
            'student_count': len(class_students),
            'mission_count': len(mission_rows),
            'completed_mission_count': total_completed,
            'mission_student_total': mission_student_total,
            'completion_rate': _rate(total_completed, mission_student_total),
            'expected_answer_count': total_expected,
            'answer_count': total_answered,
            'correct_count': total_correct,
            'wrong_count': total_wrong,
            'pending_count': total_pending,
            'accuracy': _rate(total_correct, total_correct + total_wrong),
        },
        'students': students,
        'missions': mission_rows,
    }


def _student_answer_text(answer_content):
    """Convert supported answer JSON shapes into a teacher-facing label."""
    if answer_content is None or answer_content == '':
        return '未作答'
    if isinstance(answer_content, str):
        return answer_content.strip() or '未作答'
    if not isinstance(answer_content, dict):
        return str(answer_content)
    selected_options = answer_content.get('selected_options')
    if isinstance(selected_options, (list, tuple)):
        values = [str(value).strip() for value in selected_options if str(value).strip()]
        if values:
            return '、'.join(values)
    for key in ('selected', 'text', 'answer', 'content'):
        value = answer_content.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    images = answer_content.get('images')
    if isinstance(images, list) and images:
        return f'已上传 {len(images)} 张图片答案'
    return '未作答'


def _student_attempt_status(attempt):
    if attempt is None:
        return 'unanswered'
    if attempt.is_subjective_pending:
        return 'pending'
    return 'correct' if attempt.is_correct else 'wrong'


def _serialize_student_attempt(attempt):
    if attempt is None:
        return {}
    return {
        'attempt_id': str(attempt.id),
        'attempt_no': attempt.attempt_no,
        'answer_text': _student_answer_text(attempt.answer_content),
        'answer_content': attempt.answer_content or {},
        'is_correct': None if attempt.is_subjective_pending else bool(attempt.is_correct),
        'is_subjective_pending': bool(attempt.is_subjective_pending),
        'score': float(attempt.score) if attempt.score is not None else None,
        'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
    }


def _canonical_subject(value):
    code = normalize_subject_code(value)
    if code:
        return code
    return {
        'm': 'math', 'p': 'physics', 'c': 'chemistry',
    }.get(str(value or '').strip().lower(), str(value or '').strip().lower())


def _knowledge_descriptors(question, relation):
    """Normalize question knowledge-point JSON without changing stored data."""
    snapshot = relation.question_snapshot or {}
    published = apply_snapshot_to_question(question, relation) if question is not None else None
    if 'knowledge_points' in snapshot:
        raw_points = snapshot.get('knowledge_points')
    else:
        raw_points = getattr(published, 'knowledge_points', None) if published is not None else []
    if isinstance(raw_points, dict):
        raw_points = raw_points.get('points') or raw_points.get('knowledge_points') or [raw_points]
    if not isinstance(raw_points, (list, tuple)):
        raw_points = [raw_points] if raw_points else []

    question_subject = _canonical_subject(
        getattr(published, 'subject', None) or getattr(getattr(question, 'paper', None), 'subject', None)
    )
    question_stage = str(
        getattr(getattr(question, 'paper', None), 'stage', None) or ''
    ).strip()
    descriptors = []
    for raw in raw_points:
        if isinstance(raw, dict):
            kp_id = raw.get('id')
            name = str(raw.get('module') or raw.get('name') or raw.get('label') or '').strip()
            subject = _canonical_subject(raw.get('subject') or question_subject)
            stage = str(raw.get('stage') or question_stage or '').strip()
            grade_index = raw.get('grade_index')
            grade_name = str(raw.get('grade_name') or '').strip()
            chapter = str(raw.get('chapter') or '').strip()
        else:
            kp_id = None
            name = str(raw or '').strip()
            subject = question_subject
            stage = question_stage
            grade_index = None
            grade_name = ''
            chapter = ''
        if not name and kp_id in (None, ''):
            continue
        try:
            normalized_grade_index = int(grade_index) if grade_index not in (None, '') else None
        except (TypeError, ValueError):
            normalized_grade_index = None
        if kp_id not in (None, ''):
            key = f'kp:{kp_id}'
        else:
            key = 'kp:' + '|'.join([
                subject, stage, str(normalized_grade_index or ''), chapter, name,
            ])
        descriptors.append({
            'key': key,
            'id': str(kp_id) if kp_id not in (None, '') else None,
            'name': name or f'知识点 {kp_id}',
            'subject': subject or 'unknown',
            'stage': stage or 'unknown',
            'grade_index': normalized_grade_index,
            'grade_name': grade_name,
            'chapter': chapter,
        })
    return descriptors


def _student_question_rows(mission, student_id):
    """Load visible questions with the relation needed for target/snapshot rules."""
    relations = [
        relation for relation in ordered_mission_question_rels(mission)
        if relation.is_required
    ]
    question_ids = list(dict.fromkeys(str(relation.question_id) for relation in relations))
    question_map = {
        str(question.id): question
        for question in ExamQuestion.objects.filter(id__in=question_ids).prefetch_related('images', 'options')
    }
    rows = []
    seen_question_ids = set()
    for display_no, relation in enumerate(relations, start=1):
        question_id = str(relation.question_id)
        question = question_map.get(question_id)
        targets = {str(value) for value in (relation.target_student_ids or [])}
        if targets and str(student_id) not in targets:
            continue
        if question_id in seen_question_ids:
            continue
        seen_question_ids.add(question_id)
        snapshot = relation.question_snapshot or {}
        if question is None:
            payload = {
                'id': question_id,
                'question_no': str(snapshot.get('question_no') or ''),
                'question_type': str(snapshot.get('question_type') or ''),
                'stem': str(snapshot.get('stem') or ''),
            }
            question_missing = True
            knowledge_points = _knowledge_descriptors(None, relation)
        else:
            payload = snapshot_payload(question, relation)
            published = apply_snapshot_to_question(question, relation)
            knowledge_points = _knowledge_descriptors(question, relation)
            payload['question_type'] = getattr(published, 'question_type', None) or payload.get('question_type') or ''
            payload['stem'] = getattr(published, 'stem', None) or payload.get('stem') or ''
            question_missing = False
        rows.append({
            'question_id': question_id,
            'display_no': display_no,
            'question_no': str(payload.get('question_no') or ''),
            'stem': payload.get('stem') or '',
            'question_type': payload.get('question_type') or '',
            'question_missing': question_missing,
            'knowledge_points': knowledge_points,
        })
    return rows


def _student_knowledge_graph(question_contexts, attempts):
    """Aggregate all attempts and latest objective outcomes into a tree."""
    descriptors_by_key = {}
    context_points = {}
    for key, row in question_contexts.items():
        points = row.get('knowledge_points') or []
        context_points[key] = [point['key'] for point in points]
        for point in points:
            descriptors_by_key.setdefault(point['key'], point)

    stats = defaultdict(lambda: {
        'attempt': 0, 'correct': 0, 'wrong': 0, 'last_practiced_at': None,
    })
    latest_objective = {}
    for attempt in attempts:
        context_key = (str(attempt.mission_id), str(attempt.question_id))
        point_keys = context_points.get(context_key) or []
        if not point_keys:
            continue
        for point_key in point_keys:
            item = stats[point_key]
            item['attempt'] += 1
            if attempt.is_subjective_pending:
                pass
            elif attempt.is_correct:
                item['correct'] += 1
            else:
                item['wrong'] += 1
            if attempt.submitted_at and (
                item['last_practiced_at'] is None
                or attempt.submitted_at > item['last_practiced_at']
            ):
                item['last_practiced_at'] = attempt.submitted_at
        if not attempt.is_subjective_pending:
            question_key = str(attempt.question_id)
            previous = latest_objective.get(question_key)
            if previous is None or (
                attempt.submitted_at,
                attempt.attempt_no,
                str(attempt.id),
            ) > (
                previous[0].submitted_at,
                previous[0].attempt_no,
                str(previous[0].id),
            ):
                latest_objective[question_key] = (attempt, point_keys)

    kp_ids = []
    modules = []
    for point in descriptors_by_key.values():
        if point.get('id'):
            try:
                kp_ids.append(int(point['id']))
            except (TypeError, ValueError):
                pass
        if point.get('name'):
            modules.append(point['name'])
    records_by_id = {}
    records_by_signature = {}
    # KnowledgePoint maps an external legacy table and is intentionally
    # unmanaged.  Some test/first-deploy databases do not have that table;
    # check before querying so a caught PostgreSQL error cannot abort the
    # request transaction for subsequent API calls.
    if KnowledgePoint._meta.db_table in connection.introspection.table_names():
        try:
            records = KnowledgePoint.objects.filter(id__in=kp_ids) if kp_ids else KnowledgePoint.objects.none()
            if modules:
                records = records | KnowledgePoint.objects.filter(module__in=list(set(modules)))
            for record in records:
                records_by_id[str(record.id)] = record
                signature = '|'.join([
                    _canonical_subject(record.subject), str(record.stage or ''),
                    str(record.grade_index or ''), str(record.chapter or ''), str(record.module or ''),
                ])
                records_by_signature[signature] = record
        except DatabaseError:
            # Keep unknown knowledge nodes usable when the legacy catalog is unavailable.
            records_by_id = {}
            records_by_signature = {}

    items = []
    for key, descriptor in descriptors_by_key.items():
        record = records_by_id.get(str(descriptor.get('id') or ''))
        if record is None:
            signature = '|'.join([
                descriptor.get('subject') or '', descriptor.get('stage') or '',
                str(descriptor.get('grade_index') or ''), descriptor.get('chapter') or '',
                descriptor.get('name') or '',
            ])
            record = records_by_signature.get(signature)
        item = stats[key]
        objective_total = item['correct'] + item['wrong']
        latest_correct = latest_total = 0
        for attempt, point_keys in latest_objective.values():
            if key in point_keys:
                latest_total += 1
                latest_correct += int(bool(attempt.is_correct))
        latest_accuracy = _rate(latest_correct, latest_total)
        mastery = (
            'not_started' if not latest_total else
            'mastered' if latest_accuracy >= 85 else
            'reviewing' if latest_accuracy >= 60 else 'weak'
        )
        items.append({
            'id': key,
            'name': record.module if record is not None else descriptor['name'],
            'subject': _canonical_subject(record.subject) if record is not None else descriptor['subject'],
            'stage': record.stage if record is not None else descriptor['stage'],
            'grade_index': record.grade_index if record is not None else descriptor['grade_index'],
            'grade_name': record.grade_name if record is not None else descriptor['grade_name'],
            'chapter': record.chapter if record is not None else descriptor['chapter'],
            'attempt': item['attempt'],
            'correct': item['correct'],
            'accuracy': _rate(item['correct'], objective_total),
            'latest_attempt': latest_total,
            'latest_correct': latest_correct,
            'latest_accuracy': latest_accuracy,
            'mastery': mastery,
            'last_practiced_at': item['last_practiced_at'].isoformat() if item['last_practiced_at'] else None,
        })

    tree_map = {}
    subject_labels = dict(KnowledgePoint.SUBJECT_CHOICES)
    stage_labels = KnowledgePoint.STAGE_LABELS
    for item in items:
        subject = item['subject'] or 'unknown'
        stage = item['stage'] or 'unknown'
        grade_key = f"{stage}:{item['grade_index'] or item['grade_name'] or 'unknown'}"
        subject_node = tree_map.setdefault(subject, {
            'id': f'subject:{subject}', 'name': subject_labels.get(subject, subject),
            'type': 'subject', 'children': {},
        })
        stage_node = subject_node['children'].setdefault(stage, {
            'id': f'stage:{stage}', 'name': stage_labels.get(stage, stage),
            'type': 'stage', 'children': {},
        })
        grade_node = stage_node['children'].setdefault(grade_key, {
            'id': f'grade:{grade_key}', 'name': item['grade_name'] or grade_key,
            'type': 'grade', 'children': [],
        })
        grade_node['children'].append({**item, 'type': 'knowledge'})

    def flatten(node):
        children = node.get('children')
        if isinstance(children, dict):
            node['children'] = [flatten(value) for value in children.values()]
        elif isinstance(children, list):
            node['children'] = [flatten(value) for value in children]
        return node

    return {
        'metric_version': 'latest_question_attempt_v1',
        'items': sorted(items, key=lambda value: (value['accuracy'], value['name'])),
        'tree': [flatten(value) for value in tree_map.values()],
    }


def build_student_learning_stats(class_obj, student, mission_id='', page=1, page_size=20):
    """Build one student's scoped history and knowledge mastery tree."""
    active_statuses = ('published', 'running', 'closed')
    legacy_ids = list(LearningMission.objects.filter(
        class_obj_id=class_obj.id, status__in=active_statuses,
    ).values_list('id', flat=True))
    assignment_ids = list(LearningMission.objects.filter(
        class_assignments__class_obj_id=class_obj.id,
        class_assignments__status='active',
        status__in=active_statuses,
    ).values_list('id', flat=True))
    mission_ids = list(dict.fromkeys([str(value) for value in legacy_ids + assignment_ids]))
    missions = list(LearningMission.objects.filter(id__in=mission_ids).order_by('-created_at', '-id'))

    student_id = str(student.id)
    class_student_ids = {student_id}
    scoped_missions = []
    question_contexts = {}
    mission_question_rows = {}
    all_question_ids = set()
    for mission in missions:
        assignment = _assignment_for_class(mission, class_obj.id)
        assigned_students = _mission_student_ids(mission, class_student_ids, assignment)
        if student_id not in assigned_students:
            continue
        rows = _student_question_rows(mission, student_id)
        scoped_missions.append(mission)
        mission_question_rows[str(mission.id)] = rows
        for row in rows:
            all_question_ids.add(row['question_id'])
            question_contexts[(str(mission.id), row['question_id'])] = row

    attempts = list(AnswerAttempt.objects.filter(
        mission_id__in=[str(mission.id) for mission in scoped_missions],
        student_user_id=student,
        question_id__in=all_question_ids,
    ).exclude(submit_source='draft').order_by(
        'mission_id', 'question_id', 'submitted_at', 'attempt_no', 'id',
    )) if all_question_ids else []
    attempts_by_key = defaultdict(list)
    for attempt in attempts:
        attempts_by_key[(str(attempt.mission_id), str(attempt.question_id))].append(attempt)

    mission_rows = []
    summary = {
        'mission_count': len(scoped_missions), 'answered_question_count': 0,
        'attempt_count': len(attempts), 'correct_count': 0, 'wrong_count': 0,
        'pending_count': 0, 'accuracy': 0, 'last_submitted_at': None,
    }
    summary_objective_total = 0
    for mission in scoped_missions:
        mission_key = str(mission.id)
        rows = []
        correct_count = wrong_count = pending_count = answered_count = 0
        mission_last_submitted = None
        for source_row in mission_question_rows[mission_key]:
            history = attempts_by_key.get((mission_key, source_row['question_id']), [])
            latest = history[-1] if history else None
            status = _student_attempt_status(latest)
            if latest is not None:
                answered_count += 1
                if status == 'correct':
                    correct_count += 1
                elif status == 'wrong':
                    wrong_count += 1
                elif status == 'pending':
                    pending_count += 1
                if latest.submitted_at and (
                    mission_last_submitted is None or latest.submitted_at > mission_last_submitted
                ):
                    mission_last_submitted = latest.submitted_at
            rows.append({
                'question_id': source_row['question_id'],
                'display_no': source_row['display_no'],
                'question_no': source_row['question_no'],
                'stem': source_row['stem'],
                'question_type': source_row['question_type'],
                'question_missing': source_row['question_missing'],
                'status': status,
                'answer_text': _student_answer_text(latest.answer_content) if latest else '未作答',
                'score': float(latest.score) if latest and latest.score is not None else None,
                'last_submitted_at': latest.submitted_at.isoformat() if latest and latest.submitted_at else None,
                'latest_attempt': _serialize_student_attempt(latest),
                'attempt_history': [
                    _serialize_student_attempt(attempt) for attempt in reversed(history)
                ],
            })
        objective_total = correct_count + wrong_count
        summary['answered_question_count'] += answered_count
        summary['correct_count'] += correct_count
        summary['wrong_count'] += wrong_count
        summary['pending_count'] += pending_count
        summary_objective_total += objective_total
        if mission_last_submitted and (
            summary['last_submitted_at'] is None
            or mission_last_submitted.isoformat() > summary['last_submitted_at']
        ):
            summary['last_submitted_at'] = mission_last_submitted.isoformat()
        mission_rows.append({
            'mission_id': mission_key,
            'mission_name': mission.mission_name,
            'mission_no': mission.mission_no,
            'created_at': mission.created_at.isoformat() if mission.created_at else None,
            'status': mission.status,
            'question_count': len(rows),
            'answered_count': answered_count,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'pending_count': pending_count,
            'accuracy': _rate(correct_count, objective_total),
            'completion_status': _student_status(answered_count, len(rows), pending_count),
            'last_submitted_at': mission_last_submitted.isoformat() if mission_last_submitted else None,
            'questions': rows,
        })
    summary['accuracy'] = _rate(summary['correct_count'], summary_objective_total)

    selected = None
    if mission_id:
        selected = next((row for row in mission_rows if row['mission_id'] == str(mission_id)), None)
        if selected is None:
            raise ValueError('指定作业不属于该学生在当前班级的可查看范围')
    start = max((page - 1) * page_size, 0)
    paged_rows = mission_rows[start:start + page_size]
    if selected is not None and selected not in paged_rows:
        paged_rows = [selected] + [row for row in paged_rows if row['mission_id'] != selected['mission_id']]
        paged_rows = paged_rows[:page_size]

    return {
        'class': {'id': str(class_obj.id), 'name': class_obj.class_name},
        'student': {
            'id': student_id, 'name': student.display_name or student.mobile,
            'mobile': student.mobile,
        },
        'summary': summary,
        'missions': paged_rows,
        'knowledge_graph': _student_knowledge_graph(question_contexts, attempts),
    }, len(mission_rows)
