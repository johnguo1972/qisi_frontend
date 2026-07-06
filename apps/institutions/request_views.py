"""Join request approval views (teacher only)."""

import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import Class, ClassJoinRequest, ClassStudent
from apps.institutions.serializers import ClassJoinRequestSerializer


def _trace() -> str:
    return uuid.uuid4().hex[:16]


def _check_teacher_of_class(user, class_id):
    """Return True if user is a teacher of the given class."""
    from apps.institutions.models import ClassTeacher
    return ClassTeacher.objects.filter(
        class_obj_id=class_id, teacher=user,
    ).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def join_request_list(request, class_id):
    """GET /api/v1/classes/<id>/join-requests - List join requests with optional status filter."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, class_id):
        return Response({
            'code': 4003, 'message': '无权限访问', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    qs = cls.join_requests.select_related('applicant').order_by('-created_at')
    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    page_number = request.GET.get('page', 1)
    page_size = int(request.GET.get('page_size', 20))
    start = (int(page_number) - 1) * page_size
    end = start + page_size
    total = qs.count()
    items = qs[start:end]

    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'total': total,
            'page': int(page_number),
            'page_size': page_size,
            'items': ClassJoinRequestSerializer(items, many=True).data,
        },
        'trace_id': _trace(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_request(request, request_id):
    """POST /api/v1/classes/join-requests/<id>/approve - Approve a join request."""
    try:
        join_req = ClassJoinRequest.objects.select_related('class_obj').get(id=request_id)
    except ClassJoinRequest.DoesNotExist:
        return Response({
            'code': 4004, 'message': '申请不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, join_req.class_obj_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    if join_req.status != 'pending':
        return Response({
            'code': 4001, 'message': '该申请已处理', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    join_req.status = 'approved'
    join_req.handled_by = request.user
    join_req.handled_at = timezone.now()
    join_req.save()

    # Create or reactivate ClassStudent
    ClassStudent.objects.update_or_create(
        class_obj=join_req.class_obj,
        student=join_req.applicant,
        defaults={'status': 'active', 'join_type': join_req.request_type},
    )

    return Response({
        'code': 0,
        'message': '已批准',
        'data': ClassJoinRequestSerializer(join_req).data,
        'trace_id': _trace(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_request(request, request_id):
    """POST /api/v1/classes/join-requests/<id>/reject - Reject a join request."""
    try:
        join_req = ClassJoinRequest.objects.select_related('class_obj').get(id=request_id)
    except ClassJoinRequest.DoesNotExist:
        return Response({
            'code': 4004, 'message': '申请不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, join_req.class_obj_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    if join_req.status != 'pending':
        return Response({
            'code': 4001, 'message': '该申请已处理', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    join_req.status = 'rejected'
    join_req.handled_by = request.user
    join_req.handled_at = timezone.now()
    join_req.save()

    # Mark ClassStudent as removed if exists
    ClassStudent.objects.filter(
        class_obj=join_req.class_obj, student=join_req.applicant,
    ).update(status='removed')

    return Response({
        'code': 0,
        'message': '已拒绝',
        'data': ClassJoinRequestSerializer(join_req).data,
        'trace_id': _trace(),
    })
