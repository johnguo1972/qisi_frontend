from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.study.permissions import IsParentReadContext
from apps.study.parent_views import _mission_queryset
from apps.missions.models import LearningMission

from .services import latest_report, report_payload


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsParentReadContext])
def parent_classroom_feedback(request, mission_id):
    student = request._effective_student
    try:
        mission = _mission_queryset(student).get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 'MISSION_NOT_VISIBLE', 'message': '当前孩子无权查看该课堂反馈', 'data': None,
        }, status=404)

    class_ids = list(
        student.student_classes.filter(status='active').values_list('class_obj_id', flat=True)
    )
    assigned_ids = list(
        mission.class_assignments.filter(status='active', class_obj_id__in=class_ids)
        .values_list('class_obj_id', flat=True)
    )
    if not assigned_ids and mission.class_obj_id in class_ids:
        assigned_ids = [mission.class_obj_id]
    report = latest_report(mission.id, assigned_ids[0]) if assigned_ids else None
    if report is None:
        return Response({'code': 0, 'message': 'success', 'data': {
            'feedback_available': False, 'report': {'status': 'not_ready', 'mission_name': mission.mission_name},
        }})
    payload = report_payload(report, include_students=False, student=student)
    if payload is None or not payload.get('student_feedback'):
        return Response({'code': 0, 'message': 'success', 'data': {
            'feedback_available': False, 'report': {'status': 'not_ready', 'mission_name': mission.mission_name},
        }})
    payload.pop('pdf_download_url', None)
    payload.update({
        'feedback_available': report.status in ('ready', 'partial'),
        'report': {
            'id': str(report.id), 'status': report.status,
            'mission_name': mission.mission_name,
            'class_name': report.class_obj.class_name,
            'participant_count': report.participant_count,
            'question_count': report.question_count,
            'total_wrong_count': report.total_wrong_count,
            'average_wrong_count': float(report.average_wrong_count),
        },
    })
    return Response({'code': 0, 'message': 'success', 'data': payload})
