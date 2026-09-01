"""Assignment-level learning statistics for a teacher's class overview."""

from collections import defaultdict

from apps.missions.models import LearningMission
from apps.missions.services import ordered_mission_question_rels
from apps.missions.snapshots import snapshot_payload
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt

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
