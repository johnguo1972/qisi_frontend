"""Institution management views (platform admin only)."""

import uuid

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import Institution, InstitutionMember
from apps.institutions.permissions import IsPlatformAdmin
from apps.institutions.serializers import (
    InstitutionListSerializer,
    InstitutionDetailSerializer,
    CreateInstitutionSerializer,
)


def _trace() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def institution_list_create(request):
    """GET /api/v1/admin/institutions - List institutions with pagination and name filter.
    POST /api/v1/admin/institutions - Create a new institution.
    """
    if request.method == 'GET':
        return _institution_list_impl(request)
    return _create_institution_impl(request)


def _institution_list_impl(request):
    """GET /api/v1/admin/institutions - List institutions with pagination and name filter."""
    name = request.GET.get('name', '').strip()
    qs = Institution.objects.all().order_by('-created_at')
    if name:
        qs = qs.filter(institution_name__icontains=name)

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
            'items': InstitutionListSerializer(items, many=True).data,
        },
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def institution_list(request):
    """GET /api/v1/admin/institutions - List institutions with pagination and name filter."""
    return _institution_list_impl(request)


def _create_institution_impl(request):
    """POST /api/v1/admin/institutions - Create a new institution."""
    serializer = CreateInstitutionSerializer(
        data=request.data, context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    institution = serializer.save()

    # Add creator as institution admin
    InstitutionMember.objects.get_or_create(
        institution=institution,
        user=request.user,
        defaults={'role': 'admin', 'status': 'active'},
    )

    return Response({
        'code': 0,
        'message': '创建成功',
        'data': InstitutionDetailSerializer(institution).data,
        'trace_id': _trace(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def create_institution(request):
    """POST /api/v1/admin/institutions - Create a new institution."""
    return _create_institution_impl(request)


def _delete_institution_impl(institution):
    """Delete institution after checking it has no classes or teacher members."""
    # Check for active classes
    class_count = institution.classes.count()
    if class_count > 0:
        return Response({
            'code': 4001,
            'message': f'该机构下还有 {class_count} 个班级，请先删除所有班级',
            'data': {'class_count': class_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check for teacher members
    teacher_count = InstitutionMember.objects.filter(
        institution=institution, role='teacher',
    ).count()
    if teacher_count > 0:
        return Response({
            'code': 4001,
            'message': f'该机构下还有 {teacher_count} 名老师，请先移除所有老师',
            'data': {'teacher_count': teacher_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    institution_name = institution.institution_name
    institution.delete()
    return Response({
        'code': 0,
        'message': f'机构"{institution_name}"已删除',
        'data': None,
        'trace_id': _trace(),
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def delete_institution(request, institution_id):
    """DELETE /api/v1/admin/institutions/<id> - Delete institution.

    Fails if the institution still has classes or teacher members.
    """
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Check for active classes
    class_count = institution.classes.count()
    if class_count > 0:
        return Response({
            'code': 4001,
            'message': f'该机构下还有 {class_count} 个班级，请先删除所有班级',
            'data': {'class_count': class_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check for teacher members
    teacher_count = InstitutionMember.objects.filter(
        institution=institution, role='teacher',
    ).count()
    if teacher_count > 0:
        return Response({
            'code': 4001,
            'message': f'该机构下还有 {teacher_count} 名老师，请先移除所有老师',
            'data': {'teacher_count': teacher_count},
            'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    institution_name = institution.institution_name
    institution.delete()
    return Response({
        'code': 0,
        'message': f'机构"{institution_name}"已删除',
        'data': None,
        'trace_id': _trace(),
    })


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def institution_detail(request, institution_id):
    """GET /api/v1/admin/institutions/<id> - Get institution detail.
    PUT /api/v1/admin/institutions/<id> - Update institution.
    DELETE /api/v1/admin/institutions/<id> - Delete institution.
    """
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({
            'code': 0,
            'message': 'success',
            'data': InstitutionDetailSerializer(institution).data,
            'trace_id': _trace(),
        })

    if request.method == 'PUT':
        for field in ['institution_name', 'contact_name', 'contact_phone',
                      'contact_email', 'address', 'status']:
            if field in request.data:
                setattr(institution, field, request.data[field])
        institution.save()
        return Response({
            'code': 0,
            'message': '更新成功',
            'data': InstitutionDetailSerializer(institution).data,
            'trace_id': _trace(),
        })

    if request.method == 'DELETE':
        return _delete_institution_impl(institution)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def update_institution(request, institution_id):
    """PUT /api/v1/admin/institutions/<id> - Update institution."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    for field in ['institution_name', 'contact_name', 'contact_phone',
                  'contact_email', 'address']:
        if field in request.data:
            setattr(institution, field, request.data[field])
    institution.save()

    return Response({
        'code': 0,
        'message': '更新成功',
        'data': InstitutionDetailSerializer(institution).data,
        'trace_id': _trace(),
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def update_institution_status(request, institution_id):
    """PUT /api/v1/admin/institutions/<id>/status - Update institution status."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get('status')
    if not new_status:
        return Response({
            'code': 4001, 'message': 'status 参数不能为空', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_400_BAD_REQUEST)

    institution.status = new_status
    institution.save()

    return Response({
        'code': 0,
        'message': '状态更新成功',
        'data': {'id': institution.id, 'status': institution.status},
        'trace_id': _trace(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_institutions(request):
    """GET /api/v1/teacher/institutions - List institutions where current user is a teacher."""
    memberships = InstitutionMember.objects.filter(
        user=request.user, role='teacher', status='active',
    ).select_related('institution')

    items = [{
        'id': m.institution.id,
        'institution_name': m.institution.institution_name,
    } for m in memberships]

    return Response({
        'code': 0,
        'message': 'success',
        'data': items,
        'trace_id': _trace(),
    })
