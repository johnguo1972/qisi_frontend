"""Institution member management views (institution admin only)."""

import uuid

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.institutions.models import Institution, InstitutionMember
from apps.accounts.models import UserAccount
from apps.institutions.serializers import (
    InstitutionMemberSerializer,
    AddMemberSerializer,
)


def _trace() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def member_list_add(request, institution_id):
    """GET /api/v1/institutions/<id>/members - List members.
    POST /api/v1/institutions/<id>/members - Add member.
    """
    if request.method == 'GET':
        return _member_list_impl(request, institution_id)
    return _add_member_impl(request, institution_id)


def _member_list_impl(request, institution_id):
    """GET /api/v1/institutions/<id>/members - List institution members."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Allow platform admins OR institution admins to view members
    is_platform_admin = request.user.role_type == 'admin'
    is_inst_admin = InstitutionMember.objects.filter(
        institution_id=institution_id,
        user=request.user,
        role='admin',
        status='active',
    ).exists()
    if not is_platform_admin and not is_inst_admin:
        return Response({
            'code': 4003, 'message': '无权限访问', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', None)
    qs = institution.members.select_related('user').order_by('-joined_at')
    # Default to active members only if no status filter specified
    if status_filter is None:
        qs = qs.filter(status='active')
    elif status_filter:
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
            'items': InstitutionMemberSerializer(items, many=True).data,
        },
        'trace_id': _trace(),
    })


def _add_member_impl(request, institution_id):
    """POST /api/v1/institutions/<id>/members - Add institution member."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Allow platform admins OR institution admins to add members
    is_platform_admin = request.user.role_type == 'admin'
    is_inst_admin = InstitutionMember.objects.filter(
        institution_id=institution_id,
        user=request.user,
        role='admin',
        status='active',
    ).exists()
    if not is_platform_admin and not is_inst_admin:
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    serializer = AddMemberSerializer(
        data=request.data, context={'institution': institution, 'request': request},
    )
    serializer.is_valid(raise_exception=True)
    member = serializer.save()

    return Response({
        'code': 0,
        'message': '添加成功',
        'data': InstitutionMemberSerializer(member).data,
        'trace_id': _trace(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_member(request, institution_id):
    return _add_member_impl(request, institution_id)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_member(request, institution_id, user_id):
    """PUT /api/v1/institutions/<id>/members/<user_id> - Update member role/status."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Allow platform admins OR institution admins to update members
    is_platform_admin = request.user.role_type == 'admin'
    is_inst_admin = InstitutionMember.objects.filter(
        institution_id=institution_id,
        user=request.user,
        role='admin',
        status='active',
    ).exists()
    if not is_platform_admin and not is_inst_admin:
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        member = InstitutionMember.objects.get(
            institution=institution, user_id=user_id,
        )
    except InstitutionMember.DoesNotExist:
        return Response({
            'code': 4004, 'message': '成员不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Update member role/status
    if 'role' in request.data:
        member.role = request.data['role']
    if 'status' in request.data:
        member.status = request.data['status']
    member.save()

    # Update user info (mobile, display_name, subject)
    user = member.user
    user_changed = False
    if 'mobile' in request.data:
        new_mobile = request.data['mobile'].strip()
        if new_mobile and new_mobile != user.mobile:
            # Check uniqueness
            if UserAccount.objects.filter(mobile=new_mobile).exclude(id=user.id).exists():
                return Response({
                    'code': 4001, 'message': '该手机号已被其他账号使用', 'data': None, 'trace_id': _trace(),
                }, status=status.HTTP_400_BAD_REQUEST)
            user.mobile = new_mobile
            user.login_name = new_mobile
            user_changed = True
    if 'display_name' in request.data:
        new_name = request.data['display_name'].strip()
        if new_name and new_name != user.display_name:
            user.display_name = new_name
            user_changed = True
    if 'subject' in request.data:
        new_subject = request.data['subject'].strip()
        if new_subject != user.subject:
            user.subject = new_subject if new_subject else None
            user_changed = True
    if 'stages' in request.data:
        new_stages = request.data['stages']
        if new_stages != user.stages:
            user.stages = new_stages if new_stages else None
            user_changed = True
    if user_changed:
        user.save()

    return Response({
        'code': 0,
        'message': '更新成功',
        'data': InstitutionMemberSerializer(member).data,
        'trace_id': _trace(),
    })
