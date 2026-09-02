"""HTTP API for the teacher wrong-book matrix."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsTeacherSession

from .models import WrongBookGenerationBatch, RelatedQuestionRecommendation
from .wrongbook_matrix import (
    MatrixError, batch_payload, batch_recommendations, can_manage_matrix,
    confirm_recommendations, get_or_create_matrix, get_source_mission,
    matrix_payload, request_generation, save_marks, summary_payload,
    student_history_payload,
)
from .teacher_wrongbook_selection import (
    confirm_teacher_selection,
    next_teacher_candidate_group,
    request_teacher_generation,
    teacher_candidate_groups,
)
from .views import make_trace_id


def _error(exc):
    return Response({
        'code': exc.code, 'message': str(exc), 'data': exc.data,
        'trace_id': make_trace_id(),
    }, status=exc.http_status)


def _matrix(request, mission_id, refresh=False):
    mission = get_source_mission(mission_id, request.user)
    return get_or_create_matrix(mission, request.user, request.GET.get('class_id'), refresh=refresh)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix(request, mission_id):
    try:
        if request.method == 'GET':
            return Response({'code': 0, 'data': matrix_payload(_matrix(request, mission_id)), 'trace_id': make_trace_id()})
        data = request.data
        matrix = get_or_create_matrix(get_source_mission(mission_id, request.user), request.user, data.get('class_id'))
        changes = data.get('cells', data.get('changes', []))
        if not isinstance(changes, list):
            raise MatrixError('cells 必须是数组', 'invalid')
        matrix, saved = save_marks(matrix, request.user, changes, data.get('version'), make_trace_id())
        return Response({'code': 0, 'data': {'matrix': matrix_payload(matrix), 'saved': saved}, 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError):
        return _error(MatrixError('version 必须是有效数字', 'invalid'))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix_generate(request, mission_id):
    try:
        matrix = get_or_create_matrix(get_source_mission(mission_id, request.user), request.user, request.data.get('class_id'))
        batch = request_generation(
            matrix, request.user, request.data.get('version'), request.data.get('idempotency_key'),
            request.data.get('cell_ids'), request.data.get('related_limit', 3), make_trace_id(),
        )
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()}, status=201)
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError):
        return _error(MatrixError('请求参数格式错误', 'invalid'))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def teacher_wrongbook_generate(request, mission_id):
    """Start the optional AI-first, teacher-selection fallback workflow."""
    try:
        matrix = get_or_create_matrix(
            get_source_mission(mission_id, request.user), request.user,
            request.data.get('class_id'),
        )
        batch = request_teacher_generation(
            matrix, request.user, request.data.get('version'),
            request.data.get('idempotency_key'), request.data.get('cell_ids'), make_trace_id(),
        )
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()}, status=201)
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError):
        return _error(MatrixError('请求参数格式错误', 'invalid'))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_generation_detail(request, batch_id):
    try:
        batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权查看该生成任务', 'forbidden', 403)
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()})
    except WrongBookGenerationBatch.DoesNotExist:
        return _error(MatrixError('生成任务不存在', 'not_found', 404))
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_generation_history(request, mission_id):
    try:
        matrix = _matrix(request, mission_id)
        batches = matrix.generation_batches.all()[:50]
        return Response({'code': 0, 'data': [batch_payload(batch) for batch in batches], 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix_summary(request, mission_id):
    try:
        return Response({'code': 0, 'data': summary_payload(_matrix(request, mission_id), request.GET.get('class_id')), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix_student(request, mission_id, student_id):
    try:
        matrix = _matrix(request, mission_id)
        return Response({'code': 0, 'data': student_history_payload(matrix, student_id), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix_refresh_scope(request, mission_id):
    try:
        matrix = get_or_create_matrix(get_source_mission(mission_id, request.user), request.user, request.data.get('class_id'), refresh=True)
        return Response({'code': 0, 'data': matrix_payload(matrix), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_generation_retry(request, batch_id):
    try:
        batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权重试该生成任务', 'forbidden', 403)
        batch.items.filter(status__in=('failed', 'snapshot_failed', 'publish_failed')).update(status='queued', error_stage='', error_code='', error_message='')
        batch.status = 'retrying'
        batch.save(update_fields=['status'])
        from .tasks import generate_wrongbook_batch_task
        generate_wrongbook_batch_task.delay(str(batch.id))
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()})
    except WrongBookGenerationBatch.DoesNotExist:
        return _error(MatrixError('生成任务不存在', 'not_found', 404))
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_matrix_close(request, mission_id):
    try:
        matrix = _matrix(request, mission_id)
        matrix.status = 'closed'
        matrix.save(update_fields=['status', 'updated_at'])
        from .wrongbook_matrix import _audit
        _audit(matrix, request.user, 'matrix_closed', make_trace_id())
        return Response({'code': 0, 'data': matrix_payload(matrix), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


def _recommendation_payload(rec):
    candidate = (rec.result_json or {}).get('candidate') or {}
    return {
        'id': str(rec.id), 'source_student_id': str(rec.source_student_id),
        'source_question_id': str(rec.source_question_id),
        'source_wrong_book_item_id': str(rec.source_wrong_book_item_id),
        'candidate_question_id': str(rec.candidate_question_id), 'provider': rec.provider,
        'model_name': rec.model_name, 'score': float(rec.score) if rec.score is not None else None,
        'confidence': float(rec.confidence) if rec.confidence is not None else None,
        'status': rec.status, 'candidate': candidate,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_recommendations(request, batch_id):
    try:
        batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权操作该生成任务', 'forbidden', 403)
        if request.method == 'POST':
            recs = batch_recommendations(batch, request.user, request.data.get('limit', 10), make_trace_id())
        else:
            recs = batch.recommendations.all().order_by('source_student_id', '-score', 'id')
        return Response({'code': 0, 'data': [_recommendation_payload(rec) for rec in recs], 'trace_id': make_trace_id()})
    except WrongBookGenerationBatch.DoesNotExist:
        return _error(MatrixError('生成任务不存在', 'not_found', 404))
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_recommendations_confirm(request, batch_id):
    try:
        batch = WrongBookGenerationBatch.objects.select_related('matrix__source_mission').get(pk=batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权确认该推荐', 'forbidden', 403)
        ids = request.data.get('recommendation_ids', [])
        mission = confirm_recommendations(
            batch, request.user, ids, request.data.get('idempotency_key', ''), make_trace_id(),
        )
        return Response({'code': 0, 'data': {'mission_id': str(mission.id), 'mission_name': mission.mission_name}, 'trace_id': make_trace_id()}, status=201)
    except WrongBookGenerationBatch.DoesNotExist:
        return _error(MatrixError('生成任务不存在', 'not_found', 404))
    except MatrixError as exc:
        return _error(exc)


def _validate_nested_batch(request, mission_id, batch_id):
    matrix = _matrix(request, mission_id)
    try:
        batch = WrongBookGenerationBatch.objects.get(pk=batch_id, matrix=matrix)
    except WrongBookGenerationBatch.DoesNotExist:
        raise MatrixError('生成任务不存在或不属于该作业', 'not_found', 404)
    return batch


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_generation_detail_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权查看该生成任务', 'forbidden', 403)
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_generation_retry_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        batch.items.filter(status__in=('failed', 'snapshot_failed', 'publish_failed')).update(status='queued', error_stage='', error_code='', error_message='')
        batch.status = 'retrying'
        batch.save(update_fields=['status'])
        from .tasks import generate_wrongbook_batch_task
        generate_wrongbook_batch_task.delay(str(batch.id))
        return Response({'code': 0, 'data': batch_payload(batch), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_recommendations_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权操作该生成任务', 'forbidden', 403)
        recs = batch_recommendations(batch, request.user, request.data.get('limit', 10), make_trace_id()) if request.method == 'POST' else batch.recommendations.all().order_by('source_student_id', '-score', 'id')
        return Response({'code': 0, 'data': [_recommendation_payload(rec) for rec in recs], 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def teacher_wrongbook_candidate_groups_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权查看该生成任务', 'forbidden', 403)
        if batch.generation_mode != 'teacher_select':
            raise MatrixError('该批次不是教师选择模式', 'conflict', 409)
        return Response({'code': 0, 'data': teacher_candidate_groups(batch), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def teacher_wrongbook_candidate_group_next_nested(request, mission_id, batch_id, item_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权操作该生成任务。', 'forbidden', 403)
        excluded_ids = request.data.get('excluded_question_ids') or []
        if not isinstance(excluded_ids, list):
            raise MatrixError('excluded_question_ids 必须是数组。', 'invalid')
        group = next_teacher_candidate_group(batch, item_id, excluded_ids)
        return Response({'code': 0, 'data': group, 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def teacher_wrongbook_candidate_groups_confirm_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权确认该生成任务', 'forbidden', 403)
        mission = confirm_teacher_selection(
            batch, request.user, request.data.get('groups', []),
            request.data.get('idempotency_key', ''), make_trace_id(),
        )
        return Response({
            'code': 0,
            'data': {'mission_id': str(mission.id), 'mission_name': mission.mission_name},
            'trace_id': make_trace_id(),
        }, status=201)
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def wrongbook_recommendations_confirm_nested(request, mission_id, batch_id):
    try:
        batch = _validate_nested_batch(request, mission_id, batch_id)
        if not can_manage_matrix(batch.matrix.source_mission, request.user):
            raise MatrixError('无权确认该推荐', 'forbidden', 403)
        mission = confirm_recommendations(batch, request.user, request.data.get('recommendation_ids', []), request.data.get('idempotency_key', ''), make_trace_id())
        return Response({'code': 0, 'data': {'mission_id': str(mission.id), 'mission_name': mission.mission_name}, 'trace_id': make_trace_id()}, status=201)
    except MatrixError as exc:
        return _error(exc)
