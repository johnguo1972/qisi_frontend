"""Class management views (teacher only)."""

import uuid

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import Prefetch

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.auth import get_request_role
from apps.accounts.roles import has_user_role
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
    AddClassStudentSerializer,
    UpdateClassStudentSerializer,
)
from apps.accounts.models import StudentParentBind
from apps.institutions.student_management import (
    StudentManagementError,
    add_student,
    update_student,
)


def _trace() -> str:
    return uuid.uuid4().hex[:16]


def _is_teacher_request(request):
    return (
        get_request_role(request) == 'teacher'
        and has_user_role(request.user, 'teacher')
    )


def _check_teacher_of_class(request, class_id):
    """Return True if user is a teacher of the given class."""
    return _is_teacher_request(request) and (
        ClassTeacher.objects.filter(
            class_obj_id=class_id, teacher=request.user,
        ).exists()
        or Class.objects.filter(id=class_id, creator_teacher=request.user).exists()
    )


def _create_class_impl(request):
    """POST /api/v1/classes - Create a class. User must be a teacher member of the institution."""
    if not _is_teacher_request(request):
        return Response({'code': 4003, 'message': '无权限操作'}, status=403)

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
    if not _is_teacher_request(request):
        return Response({'code': 4003, 'message': '无权限访问'}, status=403)

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
    if not _is_teacher_request(request):
        return Response({'code': 4003, 'message': '无权限访问'}, status=403)

    qs = Class.objects.filter(
        Q(class_teachers__teacher=request.user) | Q(creator_teacher=request.user),
        status='active',
    ).distinct().order_by('-created_at').values(
        'id', 'class_name', 'class_no', 'grade_level',
    )

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

    if not _check_teacher_of_class(request, class_id):
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

    if not _check_teacher_of_class(request, class_id):
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

    if not _check_teacher_of_class(request, class_id):
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


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def class_students(request, class_id):
    """List students or manually add one to a teacher-managed class."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request, class_id):
        return Response({
            'code': 4003, 'message': '无权限访问', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'POST':
        serializer = AddClassStudentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            relation = add_student(
                user=request.user,
                current_class=cls,
                data=serializer.validated_data,
            )
        except StudentManagementError as exc:
            return Response({
                'code': exc.code,
                'message': exc.message,
                'data': None,
                'trace_id': _trace(),
            }, status=exc.http_status)
        except IntegrityError:
            return Response({
                'code': 'DATA_CONFLICT',
                'message': '学生或家长手机号、绑定关系存在冲突，请刷新后重试',
                'data': None,
                'trace_id': _trace(),
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'code': 0,
            'message': '学生添加成功',
            'data': ClassStudentSerializer(relation).data,
            'trace_id': _trace(),
        }, status=status.HTTP_201_CREATED)

    parent_queryset = StudentParentBind.objects.filter(
        bind_status='active',
    ).select_related('parent_user_id').order_by('-is_primary', 'bound_at', 'id')
    qs = cls.class_students.select_related('student', 'class_obj').prefetch_related(
        Prefetch(
            'student__parent_binds_as_student',
            queryset=parent_queryset,
            to_attr='active_parent_binds',
        ),
    ).order_by('-joined_at')
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def class_learning_stats(request, class_id):
    """Return assignment and answer statistics for students in a class."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'code': 404, 'message': '班级不存在', 'data': None}, status=404)
    if not _check_teacher_of_class(request, class_id):
        return Response({'code': 403, 'message': '无权访问'}, status=403)
    from apps.institutions.learning_stats_service import build_class_learning_stats

    return Response({
        'code': 0,
        'data': build_class_learning_stats(cls),
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_learning_stats(request, class_id, student_id):
    """Return one student's scoped history and knowledge graph for a class."""
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 404, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)
    if not _check_teacher_of_class(request, class_id):
        return Response({
            'code': 403, 'message': '无权访问', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    membership = ClassStudent.objects.filter(
        class_obj=cls, student_id=student_id, status='active',
    ).select_related('student').first()
    if membership is None:
        return Response({
            'code': 404, 'message': '学生不在该班级', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    def parse_positive_int(name, default, maximum=None):
        raw = request.query_params.get(name)
        if raw in (None, ''):
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f'{name} 必须是正整数')
        if value < 1 or (maximum is not None and value > maximum):
            raise ValueError(f'{name} 超出有效范围')
        return value

    try:
        page = parse_positive_int('page', 1)
        page_size = parse_positive_int('page_size', 20, maximum=50)
    except ValueError as exc:
        return Response({
            'code': 400, 'message': str(exc), 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    mission_id = str(request.query_params.get('mission_id') or '').strip()
    from apps.institutions.learning_stats_service import build_student_learning_stats
    try:
        data, total = build_student_learning_stats(
            cls, membership.student, mission_id=mission_id,
            page=page, page_size=page_size,
        )
    except ValueError as exc:
        return Response({
            'code': 404, 'message': str(exc), 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'code': 0,
        'message': 'success',
        'data': data,
        'meta': {'page': page, 'page_size': page_size, 'total': total},
        'trace_id': _trace(),
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def remove_student(request, class_id, student_id):
    """Manage a class student.

    PUT without a display_name keeps the legacy remove behavior. PATCH with
    display_name updates the student's account name without changing class
    membership.
    """
    try:
        cls = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 4004, 'message': '班级不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _check_teacher_of_class(request, class_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        rel = ClassStudent.objects.get(class_obj=cls, student_id=student_id)
    except ClassStudent.DoesNotExist:
        return Response({
            'code': 4004, 'message': '学生不在该班级', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        serializer = UpdateClassStudentSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        try:
            updated_relation = update_student(
                user=request.user,
                current_class=cls,
                student_id=student_id,
                data=serializer.validated_data,
            )
        except StudentManagementError as exc:
            return Response({
                'code': exc.code,
                'message': exc.message,
                'data': None,
                'trace_id': _trace(),
            }, status=exc.http_status)
        except IntegrityError:
            return Response({
                'code': 'DATA_CONFLICT',
                'message': '学生或家长手机号、绑定关系存在冲突，请刷新后重试',
                'data': None,
                'trace_id': _trace(),
            }, status=status.HTTP_409_CONFLICT)
        return Response({
            'code': 0,
            'message': '学生信息更新成功',
            'data': ClassStudentSerializer(updated_relation).data,
            'trace_id': _trace(),
        })

    if 'display_name' in request.data:
        display_name = str(request.data.get('display_name') or '').strip()
        if not display_name:
            return Response({
                'code': 4001, 'message': '学生姓名不能为空', 'data': None,
                'trace_id': _trace(),
            }, status=status.HTTP_400_BAD_REQUEST)
        if len(display_name) > 64:
            return Response({
                'code': 4001, 'message': '学生姓名不能超过64个字符', 'data': None,
                'trace_id': _trace(),
            }, status=status.HTTP_400_BAD_REQUEST)
        rel.student.display_name = display_name
        rel.student.save(update_fields=['display_name', 'updated_at'])
        message = '学生姓名已更新'
    else:
        rel.status = 'removed'
        rel.save()
        message = '移除成功'

    return Response({
        'code': 0,
        'message': message,
        'data': ClassStudentSerializer(rel).data,
        'trace_id': _trace(),
    })
