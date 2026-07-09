"""Class management views (teacher only)."""

import uuid

from django.db import transaction
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import (
    Institution,
    InstitutionMember,
    Class,
    ClassTeacher,
    ClassStudent,
)
from apps.institutions.permissions import IsClassTeacher
from apps.institutions.serializers import (
    ClassListSerializer,
    ClassDetailSerializer,
    CreateClassSerializer,
    UpdateClassSerializer,
    ClassStudentSerializer,
)


def _trace() -> str:
    return uuid.uuid4().hex[:16]


def _check_teacher_of_class(user, class_id):
    """Return True if user is a teacher of the given class."""
    return ClassTeacher.objects.filter(
        class_obj_id=class_id, teacher=user,
    ).exists()


def _create_class_impl(request):
    """POST /api/v1/classes - Create a class. User must be a teacher member of the institution."""
    institution_id = request.data.get('institution_id')
    if not institution_id:
        return Response({
            'code': 4001, 'message': 'institution_id 不能为空', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Verify user is a teacher member of this institution
    if not InstitutionMember.objects.filter(
        institution=institution, user=request.user, role='teacher', status='active',
    ).exists():
        return Response({
            'code': 4003, 'message': '您不是该机构的教师，无法创建班级', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    serializer = CreateClassSerializer(
        data=request.data,
        context={'institution_id': institution_id, 'request': request},
    )
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        cls = serializer.save()

        # Create ClassTeacher relation
        ClassTeacher.objects.create(
            class_obj=cls, teacher=request.user, role='owner',
        )

    return Response({
        'code': 0,
        'message': '创建成功',
        'data': ClassDetailSerializer(cls).data,
        'trace_id': _trace(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_class(request):
    """POST /api/v1/classes - Create a class."""
    return _create_class_impl(request)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def class_list_create(request):
    """GET /api/v1/classes - List classes where user is a teacher.
    POST /api/v1/classes - Create a class.
    """
    if request.method == 'GET':
        return _class_list_impl(request)
    return _create_class_impl(request)


def _class_list_impl(request):
    """GET /api/v1/classes - List classes where user is a teacher."""
    qs = Class.objects.filter(
        Q(class_teachers__teacher=request.user) | Q(creator_teacher=request.user),
    ).distinct().order_by('-created_at')

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
            'items': ClassListSerializer(items, many=True).data,
        },
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_list(request):
    """GET /api/v1/classes - List classes where user is a teacher."""
    return _class_list_impl(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_simple_list(request):
    """GET /api/v1/classes/simple - Simple list of classes for dropdown selectors (no pagination)."""
    qs = Class.objects.filter(
        class_teachers__teacher=request.user,
        status='active',
    ).order_by('-created_at').values('id', 'class_name', 'class_no')

    return Response({
        'code': 0,
        'message': 'success',
        'data': list(qs),
        'trace_id': _trace(),
    })


def _delete_class_impl(cls):
    """Delete a class after checking it has no students or teachers."""
    # Check for students
    student_count = cls.class_students.filter(status='active').count()
    if student_count > 0:
        return Response({
            'code': 4001,
            'message': f'该班级下还有 {student_count} 名学生，请先移除所有学生',
            'data': {'student_count': student_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check for teachers (excluding the requesting user who is trying to delete)
    teacher_count = cls.class_teachers.count()
    if teacher_count > 0:
        return Response({
            'code': 4001,
            'message': f'该班级下还有 {teacher_count} 名老师，请先移除所有老师',
            'data': {'teacher_count': teacher_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    class_name = cls.class_name
    cls.delete()
    return Response({
        'code': 0,
        'message': f'班级"{class_name}"已删除',
        'data': None,
        'trace_id': _trace(),
    })


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def class_detail(request, class_id):
    """GET /api/v1/classes/<id> - Get class detail.
    PUT /api/v1/classes/<id> - Update class.
    DELETE /api/v1/classes/<id> - Delete class.
    """
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

    if request.method == 'GET':
        return Response({
            'code': 0,
            'message': 'success',
            'data': ClassDetailSerializer(cls).data,
            'trace_id': _trace(),
        })

    if request.method == 'PUT':
        serializer = UpdateClassSerializer(cls, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'code': 0,
            'message': '更新成功',
            'data': ClassDetailSerializer(cls).data,
            'trace_id': _trace(),
        })

    if request.method == 'DELETE':
        return _delete_class_impl(cls)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_class(request, class_id):
    """PUT /api/v1/classes/<id> - Update class."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, class_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    serializer = UpdateClassSerializer(cls, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()

    return Response({
        'code': 0,
        'message': '更新成功',
        'data': ClassDetailSerializer(cls).data,
        'trace_id': _trace(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_invite_code(request, class_id):
    """POST /api/v1/classes/<id>/regenerate-code - Regenerate invite code."""
    import string
    import random

    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, class_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    # Generate new unique invite code
    while True:
        new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Class.objects.filter(invite_code=new_code).exists():
            break

    cls.invite_code = new_code
    cls.save()

    return Response({
        'code': 0,
        'message': '邀请码已更新',
        'data': {'invite_code': new_code},
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_students(request, class_id):
    """GET /api/v1/classes/<id>/students - List students in a class."""
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

    qs = cls.class_students.select_related('student').order_by('-joined_at')
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
            'items': ClassStudentSerializer(items, many=True).data,
        },
        'trace_id': _trace(),
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def remove_student(request, class_id, student_id):
    """PUT /api/v1/classes/<id>/students/<student_id> - Remove student (set status=removed)."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request.user, class_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        rel = ClassStudent.objects.get(class_obj=cls, student_id=student_id)
    except ClassStudent.DoesNotExist:
        return Response({
            'code': 4004, 'message': '学生不在该班级', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    rel.status = 'removed'
    rel.save()

    return Response({
        'code': 0,
        'message': '移除成功',
        'data': ClassStudentSerializer(rel).data,
        'trace_id': _trace(),
    })
