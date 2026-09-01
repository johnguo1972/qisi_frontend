"""Teacher-facing per-question learning statistics for one assignment."""

import uuid

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsTeacherSession
from apps.accounts.models import UserAccount
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt

from .models import LearningMission
from .services import ordered_mission_question_rels
from .snapshots import snapshot_payload
from .views import _mission_assignments, _mission_student_ids


def make_trace_id():
    return uuid.uuid4().hex[:16]


def _answer_text(answer_content):
    """Convert the supported answer JSON shapes into a compact display value."""
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


def _status_for_attempt(attempt):
    if attempt is None:
        return 'unanswered'
    if attempt.is_subjective_pending:
        return 'pending'
    return 'correct' if attempt.is_correct else 'wrong'


def _question_rows(mission):
    """Return the mission's visible questions and a stable display sequence."""
    relations = [relation for relation in ordered_mission_question_rels(mission) if relation.is_required]
    question_ids = list(dict.fromkeys(str(relation.question_id) for relation in relations))
    question_map = {
        str(question.id): question
        for question in ExamQuestion.objects.filter(id__in=question_ids).prefetch_related('images', 'options')
    }

    rows = []
    relation_by_question = {}
    target_by_question = {}
    for relation in relations:
        question_id = str(relation.question_id)
        if question_id not in question_map:
            continue
        relation_by_question.setdefault(question_id, relation)
        targets = {str(value) for value in (relation.target_student_ids or [])}
        if question_id not in target_by_question:
            target_by_question[question_id] = targets or None
        elif not targets:
            target_by_question[question_id] = None
        elif target_by_question[question_id] is not None:
            target_by_question[question_id].update(targets)

    for display_no, question_id in enumerate(relation_by_question, start=1):
        question = question_map[question_id]
        relation = relation_by_question[question_id]
        payload = snapshot_payload(question, relation)
        payload['id'] = question_id
        payload['display_no'] = display_no
        payload['question_no'] = str(payload.get('question_no') or '')
        payload['answer'] = payload.get('answer') or ''
        payload['assigned_student_ids'] = sorted(target_by_question.get(question_id) or [])
        rows.append(payload)
    return rows


def _build_learning_stats(mission, class_id=''):
    question_rows = _question_rows(mission)
    question_ids = [row['id'] for row in question_rows]
    student_ids = list(_mission_student_ids(mission, class_id=class_id or None))
    students = list(
        UserAccount.objects.filter(id__in=student_ids, status='active')
        .order_by('display_name', 'mobile')
    )

    attempts = AnswerAttempt.objects.filter(
        mission=mission,
        student_user_id__in=student_ids,
        question_id__in=question_ids,
    ).exclude(submit_source='draft').order_by(
        'student_user_id', 'question_id', '-submitted_at', '-attempt_no',
    )
    latest = {}
    for attempt in attempts:
        latest.setdefault((str(attempt.student_user_id_id), str(attempt.question_id)), attempt)

    summary = {
        'students': len(students),
        'questions': len(question_rows),
        'correct': 0,
        'wrong': 0,
        'pending': 0,
        'unanswered': 0,
        'submitted': 0,
    }
    student_rows = []
    for student in students:
        student_id = str(student.id)
        cells = []
        for question in question_rows:
            question_id = question['id']
            assigned_ids = set(question.get('assigned_student_ids') or [])
            if assigned_ids and student_id not in assigned_ids:
                cells.append({
                    'question_id': question_id,
                    'display_no': question['display_no'],
                    'status': 'not_assigned',
                    'answer_text': '',
                    'answer_content': {},
                    'score': None,
                    'submitted_at': None,
                })
                continue

            attempt = latest.get((student_id, question_id))
            status = _status_for_attempt(attempt)
            if status in summary:
                summary[status] += 1
            if attempt is not None:
                summary['submitted'] += 1
            cells.append({
                'question_id': question_id,
                'display_no': question['display_no'],
                'status': status,
                'answer_text': _answer_text(attempt.answer_content if attempt else None),
                'answer_content': attempt.answer_content if attempt else {},
                'is_correct': (None if attempt is None or attempt.is_subjective_pending else bool(attempt.is_correct)),
                'score': float(attempt.score) if attempt else None,
                'submitted_at': attempt.submitted_at.isoformat() if attempt else None,
            })
        student_rows.append({
            'student_id': student_id,
            'student_name': student.display_name or student.mobile,
            'mobile': student.mobile,
            'cells': cells,
        })

    return {
        'mission_id': str(mission.id),
        'mission_name': mission.mission_name,
        'class_id': class_id or None,
        'summary': summary,
        'questions': question_rows,
        'students': student_rows,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_learning_stats(request, mission_id):
    """Return a dense student-by-question answer matrix for one mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '作业不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=404)

    class_id = str(request.query_params.get('class_id') or '').strip()
    if class_id and not any(str(item.class_obj_id) == class_id for item in _mission_assignments(mission)):
        return Response({
            'code': 404, 'message': '班级任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=404)

    return Response({
        'code': 0,
        'message': 'success',
        'data': _build_learning_stats(mission, class_id),
        'trace_id': make_trace_id(),
    })
