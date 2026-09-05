"""Authenticated question-ingestion history endpoint."""

from datetime import timedelta
import uuid

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.courses.views import _check_course_owner, _get_course_or_404

from .models import QuestionIngestionBatch


def _error_response(message, status):
    return Response({
        'code': status,
        'message': str(message),
        'data': None,
        'trace_id': uuid.uuid4().hex[:16],
    }, status=status)


def _batch_item(batch):
    return {
        'id': str(batch.id),
        'source_type': batch.source_type,
        'source_name': batch.source_name,
        'status': batch.status,
        'course_id': str(batch.course_id) if batch.course_id else None,
        'paper_id': str(batch.paper_id) if batch.paper_id else None,
        'total_read': batch.total_read,
        'created_count': batch.created_count,
        'skipped_existing_count': batch.skipped_existing_count,
        'skipped_in_package_count': batch.skipped_in_package_count,
        'failed_count': batch.failed_count,
        'started_at': batch.started_at,
        'finished_at': batch.finished_at,
        'created_at': batch.created_at,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ingestion_history(request):
    """Return the caller's recent audit batches, optionally for one course."""
    scope = request.query_params.get('scope', 'bank')
    batches = QuestionIngestionBatch.objects.filter(
        actor=request.user,
        created_at__gte=timezone.now() - timedelta(days=30),
    )

    if scope == 'course':
        course_id = request.query_params.get('course_id')
        if not course_id:
            return _error_response('course_id is required for course scope', 400)
        try:
            uuid.UUID(str(course_id))
        except (TypeError, ValueError, AttributeError):
            return _error_response('course_id must be a UUID', 400)
        try:
            course = _get_course_or_404(course_id)
        except NotFound as exc:
            return _error_response(exc.detail, 404)
        try:
            _check_course_owner(course, request.user)
        except PermissionDenied as exc:
            return _error_response(exc.detail, 403)
        batches = batches.filter(course=course)
    elif scope != 'bank':
        return _error_response('scope must be bank or course', 400)

    items = [_batch_item(batch) for batch in batches.order_by('-finished_at', '-created_at')[:30]]
    return Response({
        'code': 0,
        'message': 'success',
        'data': {'items': items},
        'trace_id': uuid.uuid4().hex[:16],
    })
