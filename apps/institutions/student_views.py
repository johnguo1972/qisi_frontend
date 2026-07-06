"""Student-facing views for joining classes."""

import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import Class, ClassStudent, ClassJoinRequest
from apps.institutions.serializers import (
    SearchClassesSerializer,
    MyClassesSerializer,
    JoinByCodeSerializer,
    CreateJoinRequestSerializer,
    ClassJoinRequestSerializer,
)
from apps.missions.models import LearningMission
from apps.study.models import StudentMissionProgress, StudentLevelProgress


def _trace() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_classes(request):
    """POST /api/v1/student/classes/search - Search classes by teacher mobile."""
    serializer = SearchClassesSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    teacher_mobile = serializer.validated_data['teacher_mobile']

    # Find classes where teacher has invite join enabled and is taught by a teacher with this mobile
    qs = Class.objects.filter(
        class_teachers__teacher__mobile=teacher_mobile,
        allow_invite_join=True,
        status='active',
    ).distinct().order_by('-created_at')

    return Response({
        'code': 0,
        'message': 'success',
        'data': SearchClassesSerializer().to_representation(qs),
        'trace_id': _trace(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_by_code(request):
    """POST /api/v1/student/classes/join-by-code - Join a class by invite code."""
    serializer = JoinByCodeSerializer(
        data=request.data, context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    student = serializer.save()

    return Response({
        'code': 0,
        'message': '加入成功',
        'data': {
            'class_id': student.class_obj_id,
            'class_name': student.class_obj.class_name,
        },
        'trace_id': _trace(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_join_request(request):
    """POST /api/v1/classes/join-request - Submit a join request for approval."""
    serializer = CreateJoinRequestSerializer(
        data=request.data, context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    join_req = serializer.save()

    return Response({
        'code': 0,
        'message': '申请已提交，等待教师审核',
        'data': ClassJoinRequestSerializer(join_req).data,
        'trace_id': _trace(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_classes(request):
    """GET /api/v1/student/my-classes - List my active classes."""
    qs = ClassStudent.objects.filter(
        student=request.user, status='active',
    ).select_related('class_obj__institution', 'class_obj__creator_teacher').order_by('-joined_at')

    page_number = request.GET.get('page', 1)
    page_size = int(request.GET.get('page_size', 20))
    start = (int(page_number) - 1) * page_size
    end = start + page_size
    total = qs.count()
    items = qs[start:end]

    serializer = MyClassesSerializer()
    serialized_items = [serializer.to_representation(item) for item in items]

    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'total': total,
            'page': int(page_number),
            'page_size': page_size,
            'items': serialized_items,
        },
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_join_requests(request):
    """GET /api/v1/student/join-requests - List my join requests."""
    qs = ClassJoinRequest.objects.filter(
        applicant=request.user,
    ).select_related('class_obj').order_by('-created_at')

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
def quit_class(request, class_id):
    """POST /api/v1/student/classes/{class_id}/quit - Quit a class."""
    student = request.user

    # 1. Verify student is a member of this class
    membership = ClassStudent.objects.filter(
        class_obj_id=class_id,
        student=student,
        status='active',
    ).first()

    if not membership:
        return Response({
            'code': 404,
            'message': '你不是该班级的成员',
            'data': None,
            'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # 2. Find all missions belonging to this class
    mission_ids = LearningMission.objects.filter(
        class_obj_id=class_id,
    ).values_list('id', flat=True)

    # 3. Clean up StudentMissionProgress
    StudentMissionProgress.objects.filter(
        mission_id__in=mission_ids,
        student_user_id=student,
    ).delete()

    # 4. Clean up StudentLevelProgress
    # LearningMission -> MissionLevel (via level.mission foreign key)
    StudentLevelProgress.objects.filter(
        level__mission_id__in=mission_ids,
        student_user_id=student,
    ).delete()

    # 5. Physical delete ClassStudent record
    membership.delete()

    return Response({
        'code': 0,
        'message': '已退出班级',
        'data': None,
        'trace_id': _trace(),
    })
