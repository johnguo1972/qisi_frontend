"""Teacher endpoints for classroom feedback reports."""
from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsTeacherSession
from apps.common.media import media_url
from apps.missions.wrongbook_matrix import MatrixError

from .models import ClassroomFeedbackReport
from .services import (
    build_feedback_snapshot,
    create_feedback_report,
    latest_report,
    mark_stale_reports,
    prepare_feedback_scope,
    report_payload,
)
from .tasks import generate_classroom_feedback_report


def _trace_id():
    import uuid
    return uuid.uuid4().hex[:16]


def _error(exc):
    return Response({
        'code': exc.code if isinstance(exc, MatrixError) else 'INVALID_REQUEST',
        'message': str(exc), 'data': getattr(exc, 'data', {}), 'trace_id': _trace_id(),
    }, status=getattr(exc, 'http_status', 400))


def _classroom_feedback_detail(request, mission_id):
    try:
        class_id = request.query_params.get('class_id') if request.method == 'GET' else request.data.get('class_id')
        mission, matrix, selected_class_id = prepare_feedback_scope(mission_id, request.user, class_id)
        if request.method == 'GET':
            mark_stale_reports(mission, matrix)
            report = latest_report(mission.id, selected_class_id)
            current = build_feedback_snapshot(mission, matrix)
            overview = {key: current[key] for key in (
                'participant_count', 'question_count', 'total_wrong_count', 'average_wrong_count',
            )}
            return Response({
                'code': 0, 'message': 'success', 'data': {
                    'current_matrix_version': matrix.version,
                    'class_id': selected_class_id,
                    'class_options': [
                        {'class_id': str(item.class_obj_id), 'class_name': item.class_obj.class_name}
                        for item in mission.class_assignments.filter(status='active').select_related('class_obj')
                    ] or ([{'class_id': str(mission.class_obj_id), 'class_name': mission.class_obj.class_name}] if mission.class_obj_id else []),
                    'overview': overview,
                    'current_summary': overview,
                    'report': report_payload(report),
                }, 'trace_id': _trace_id(),
            })

        try:
            version = int(request.data.get('matrix_version'))
        except (TypeError, ValueError):
            raise MatrixError('matrix_version 必须是整数', 'INVALID_REQUEST', 400)
        if version != matrix.version:
            raise MatrixError('统计数据已更新，请刷新后重新生成', 'VERSION_CONFLICT', 409, {'current_version': matrix.version})
        report = create_feedback_report(
            mission, matrix, request.user, request.data.get('idempotency_key') or '',
        )
        if report.status == 'queued':
            try:
                generate_classroom_feedback_report.apply_async(args=[str(report.id)], queue='ai.feedback')
            except Exception as exc:
                report.status = 'failed'
                report.error_message = '反馈任务投递失败'
                report.save(update_fields=['status', 'error_message', 'updated_at'])
                raise MatrixError('反馈任务暂时无法启动', 'TASK_DISPATCH_FAILED', 503) from exc
        return Response({'code': 0, 'message': 'success', 'data': {'report': report_payload(report)}, 'trace_id': _trace_id()}, status=202)
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError) as exc:
        return _error(MatrixError(str(exc), 'INVALID_REQUEST', 400))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_feedback_detail(request, mission_id):
    return _classroom_feedback_detail(request, mission_id)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_feedback_generate(request, mission_id):
    """Compatibility endpoint; generation is also accepted by detail POST."""
    return _classroom_feedback_detail(request, mission_id)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_feedback_export_pdf(request, mission_id):
    try:
        class_id = request.data.get('class_id')
        report_id = request.data.get('report_id')
        mission, matrix, selected_class_id = prepare_feedback_scope(mission_id, request.user, class_id)
        if str(selected_class_id) != str(class_id):
            raise MatrixError('班级不属于该课堂练习', 'CLASS_NOT_IN_SCOPE', 404)
        report = ClassroomFeedbackReport.objects.filter(
            pk=report_id, mission=mission, class_obj_id=selected_class_id,
        ).first()
        if report is None:
            raise MatrixError('反馈报告不存在', 'REPORT_NOT_FOUND', 404)
        if report.status not in ('ready', 'partial'):
            raise MatrixError('报告尚未完成，暂不能导出 PDF', 'REPORT_NOT_READY', 409)
        if report.pdf_file_path:
            return Response({'code': 0, 'message': 'success', 'data': {'download_url': media_url(report.pdf_file_path)}, 'trace_id': _trace_id()})
        from .pdf_service import generate_feedback_pdf
        relative_path = generate_feedback_pdf(report)
        ClassroomFeedbackReport.objects.filter(pk=report.pk).update(pdf_file_path=relative_path)
        return Response({'code': 0, 'message': 'success', 'data': {'download_url': media_url(relative_path)}, 'trace_id': _trace_id()})
    except MatrixError as exc:
        return _error(exc)
    except Exception:
        return Response({'code': 'PDF_GENERATE_FAILED', 'message': '课堂反馈 PDF 生成失败', 'data': {}, 'trace_id': _trace_id()}, status=500)
