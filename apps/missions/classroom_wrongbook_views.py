"""HTTP endpoints for classroom-practice wrong-question statistics."""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsTeacherSession
from apps.missions.models import LearningMission, MissionQuestionRel
from apps.study.models import AnswerAttempt

from .classroom_wrongbook_service import (
    classroom_statistics_payload,
    import_batch_payload,
    import_classroom_workbook,
    prepare_classroom_matrix,
    save_classroom_manual_marks,
)
from .wrongbook_matrix import MatrixError
from .wrongbook_matrix import _students_for_assignment, _assignments
from .views import make_trace_id


def _error(exc):
    return Response({
        'code': exc.code,
        'message': str(exc),
        'data': exc.data,
        'trace_id': make_trace_id(),
    }, status=exc.http_status)


def _mission_payload(mission):
    assignments = _assignments(mission)
    class_ids = [str(row.class_obj_id) for row in assignments if row.class_obj_id]
    class_names = [row.class_obj.class_name for row in assignments if getattr(row, 'class_obj', None)]
    question_ids = list(MissionQuestionRel.objects.filter(mission=mission).values_list('question_id', flat=True).distinct())
    scoped_student_ids = set()
    for assignment in assignments:
        scoped_student_ids.update(
            str(member.student_id) for member in _students_for_assignment(mission, assignment)
        )
    online_answer_count = AnswerAttempt.objects.filter(
        mission_id=mission.id,
        student_user_id__in=scoped_student_ids,
        question_id__in=question_ids,
    ).exclude(submit_source='draft').count()
    offline_student_count = 0
    for assignment in assignments:
        members = _students_for_assignment(mission, assignment)
        student_ids = {str(member.student_id) for member in members}
        online_ids = set(str(value) for value in AnswerAttempt.objects.filter(
            mission_id=mission.id,
            student_user_id__in=student_ids,
            question_id__in=question_ids,
        ).exclude(submit_source='draft').values_list('student_user_id', flat=True).distinct())
        offline_student_count += len(student_ids - online_ids)
    return {
        'mission_id': str(mission.id),
        'mission_name': mission.mission_name,
        'status': mission.status,
        'class_ids': class_ids,
        'class_names': class_names,
        'node_count': mission.levels.count(),
        'question_count': len(question_ids),
        'online_answer_count': online_answer_count,
        'offline_student_count': offline_student_count,
        'updated_at': mission.updated_at,
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrongbook_statistics(request, mission_id):
    try:
        if request.method == 'GET':
            mission, matrix, _ = prepare_classroom_matrix(
                mission_id, request.user, request.GET.get('class_id'),
            )
            return Response({'code': 0, 'message': 'success', 'data': classroom_statistics_payload(mission, matrix), 'trace_id': make_trace_id()})

        class_id = request.data.get('class_id')
        mission, matrix, _ = prepare_classroom_matrix(mission_id, request.user, class_id)
        changes = request.data.get('cells', [])
        if not isinstance(changes, list):
            raise MatrixError('cells 必须是数组', 'INVALID_REQUEST', 400)
        save_classroom_manual_marks(
            mission, matrix, request.user, changes, request.data.get('version'),
        )
        mission, matrix, _ = prepare_classroom_matrix(mission_id, request.user, class_id)
        return Response({'code': 0, 'message': 'success', 'data': classroom_statistics_payload(mission, matrix), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError):
        return _error(MatrixError('请求参数格式错误', 'INVALID_REQUEST', 400))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrongbook_import(request, mission_id):
    try:
        workbook = request.FILES.get('file')
        if workbook is None:
            raise MatrixError('请上传 xlsx 文件', 'FILE_REQUIRED', 400)
        class_id = request.data.get('class_id')
        mission, matrix, _ = prepare_classroom_matrix(mission_id, request.user, class_id)
        batch, matrix = import_classroom_workbook(
            mission,
            matrix,
            request.user,
            workbook,
            request.data.get('version'),
            request.data.get('replace_scope') or 'offline_students_in_uploaded_nodes',
        )
        data = classroom_statistics_payload(mission, matrix)
        return Response({
            'code': 0,
            'message': 'success',
            'data': {
                **import_batch_payload(batch),
                'matrix': data,
            },
            'trace_id': make_trace_id(),
        })
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError, OSError):
        return _error(MatrixError('Excel 文件格式错误', 'IMPORT_INVALID', 400))
