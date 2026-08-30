from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import ClassStudent
from apps.missions.models import LearningMission
from apps.wrongbook.models import WrongBookItem

from .models import AnswerAttempt, StudentLevelProgress, StudentMissionProgress
from .permissions import IsParentReadContext
from .student_views import _visible_mission_rels
from apps.missions.services import assignment_levels, close_stale_missions
from apps.missions.pdf_service import mission_pdf_download_url


def make_trace_id():
    import uuid
    return uuid.uuid4().hex[:16]


def _active_class_ids(student):
    return list(
        ClassStudent.objects.filter(student=student, status='active')
        .values_list('class_obj_id', flat=True)
    )


def _mission_queryset(student, scope=None):
    close_stale_missions()
    class_ids = _active_class_ids(student)
    queryset = LearningMission.objects.filter(
        status='published',
    ).filter(
        Q(class_obj_id__in=class_ids) | Q(class_assignments__class_obj_id__in=class_ids)
    ).select_related('class_obj').prefetch_related('levels', 'class_assignments__class_obj').distinct().order_by('-created_at')
    now = timezone.now()
    if scope == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        queryset = queryset.filter(end_at__gte=start, end_at__lt=start + timedelta(days=1))
    elif scope == 'week':
        queryset = queryset.filter(end_at__lte=now + timedelta(days=7))
    return queryset


def _level_payload(level, student):
    question_count = len(_visible_mission_rels(level, student.id))
    attempts = AnswerAttempt.objects.filter(student_user_id=student, level=level)
    correct_count = attempts.filter(is_correct=True).values('question_id').distinct().count()
    attempt_count = attempts.exclude(is_subjective_pending=True).count()
    progress_percent = round(correct_count / max(question_count, 1) * 100, 0) if question_count else 0
    progress = StudentLevelProgress.objects.filter(
        level=level, student_user_id=student,
    ).first()
    latest_attempt = attempts.order_by('-submitted_at').first()
    status = progress.status if progress else ('completed' if progress_percent >= 100 else 'not_started')
    accuracy = round(correct_count / max(attempt_count, 1) * 100, 1) if attempt_count else 0
    return {
        'id': level.id,
        'level_no': level.level_no,
        'level_name': level.level_name,
        'level_type': level.level_type,
        'question_count': question_count,
        'completed_count': correct_count,
        'progress_percent': progress_percent,
        'accuracy': accuracy,
        'attempt_count': attempt_count,
        'status': status,
        'last_attempt_at': latest_attempt.submitted_at if latest_attempt else None,
    }


def _mission_payload(mission, student, include_levels=False):
    levels = [_level_payload(level, student) for level in assignment_levels(mission)]
    overall = round(
        sum(float(level['progress_percent']) for level in levels) / max(len(levels), 1),
        2,
    )
    progress = StudentMissionProgress.objects.filter(
        mission=mission, student_user_id=student,
    ).first()
    status = progress.progress_status if progress else ('completed' if overall >= 100 else 'not_started')
    attempts = AnswerAttempt.objects.filter(student_user_id=student, mission=mission)
    completed_attempts = attempts.exclude(is_subjective_pending=True)
    correct = completed_attempts.filter(is_correct=True).count()
    accuracy = round(correct / max(completed_attempts.count(), 1) * 100, 1) if completed_attempts.exists() else 0
    latest_attempt = attempts.order_by('-submitted_at').first()
    payload = {
        'id': mission.id,
        'mission_no': mission.mission_no,
        'mission_name': mission.mission_name,
        'goal_text': mission.goal_text,
        'class_name': '、'.join(item.class_obj.class_name for item in mission.class_assignments.filter(status='active') if item.class_obj) or (mission.class_obj.class_name if mission.class_obj else None),
        'deadline': mission.end_at,
        'assignment_mode': mission.assignment_mode,
        'pdf_download_url': mission_pdf_download_url(mission),
        'level_count': len(levels),
        'question_count': sum(level['question_count'] for level in levels),
        'progress_status': status,
        'progress_percent': overall,
        'accuracy': accuracy,
        'last_attempt_at': latest_attempt.submitted_at if latest_attempt else None,
    }
    if include_levels:
        payload['levels'] = levels
    return payload


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentReadContext])
def parent_overview(request):
    student = request._effective_student
    missions = [_mission_payload(mission, student) for mission in _mission_queryset(student)]
    attempts = AnswerAttempt.objects.filter(student_user_id=student)
    completed_attempts = attempts.exclude(is_subjective_pending=True)
    correct_count = completed_attempts.filter(is_correct=True).count()
    classes = list(
        ClassStudent.objects.filter(student=student, status='active')
        .select_related('class_obj').values_list('class_obj__class_name', flat=True)
    )
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today_count = sum(
        1 for mission in missions
        if mission['deadline'] and today_start <= mission['deadline'] < today_end
    )
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'student': {
                'id': student.id,
                'display_name': student.display_name,
                'grade_level': student.grade_level,
            },
            'class_name': '、'.join(name for name in classes if name),
            'today_mission_count': today_count,
            'completed_mission_count': sum(1 for mission in missions if mission['progress_status'] == 'completed'),
            'total_mission_count': len(missions),
            'total_attempt_count': completed_attempts.count(),
            'accuracy': round(correct_count / max(completed_attempts.count(), 1) * 100, 1),
            'wrong_book_count': WrongBookItem.objects.filter(student_user_id=student).count(),
        },
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentReadContext])
def parent_missions(request):
    student = request._effective_student
    scope = request.query_params.get('scope')
    missions = [_mission_payload(mission, student) for mission in _mission_queryset(student, scope)]
    return Response({'code': 0, 'message': 'success', 'data': {'missions': missions}, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentReadContext])
def parent_mission_detail(request, mission_id):
    student = request._effective_student
    try:
        mission = _mission_queryset(student).get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 'MISSION_NOT_VISIBLE',
            'message': '当前孩子无权查看该任务',
            'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    return Response({
        'code': 0,
        'message': 'success',
        'data': {'mission': _mission_payload(mission, student, include_levels=True)},
        'trace_id': make_trace_id(),
    })
