"""Institution member management views (institution admin only)."""

import uuid

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.auth import get_request_role
from apps.accounts.roles import grant_user_role, has_user_role
from apps.institutions.models import Institution, InstitutionMember
from apps.accounts.models import UserAccount
from apps.institutions.serializers import (
    InstitutionMemberSerializer,
    AddMemberSerializer,
)


def _trace() -> str:
    return uuid.uuid4().hex[:16]


def _can_manage_institution_members(request, institution_id):
    active_role = get_request_role(request)
    if active_role == 'admin' and has_user_role(request.user, 'admin'):
        return True
    return (
        active_role == 'teacher'
        and has_user_role(request.user, 'teacher')
        and InstitutionMember.objects.filter(
            institution_id=institution_id,
            user=request.user,
            role='admin',
            status='active',
        ).exists()
    )


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

    if not _can_manage_institution_members(request, institution_id):
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
    if role_filter:
        qs = qs.filter(role=role_filter)

    page_number = request.GET.get('page', 1)
    page_size = int(request.GET.get('page_size', 20))
    start = (int(page_number) - 1) * page_size
    end = start + page_size
    grouped = {}
    for member in qs:
        grouped.setdefault(member.user_id, []).append(member)
    grouped_items = list(grouped.values())
    total = len(grouped_items)
    page_groups = grouped_items[start:end]
    items = [members[0] for members in page_groups]
    page_user_ids = [member.user_id for member in items]
    active_roles_by_user = {user_id: set() for user_id in page_user_ids}
    for user_id, role in InstitutionMember.objects.filter(
        institution=institution,
        user_id__in=page_user_ids,
        status='active',
    ).values_list('user_id', 'role'):
        active_roles_by_user[user_id].add(role)
    roles_by_user = {
        user_id: [
            role for role in ('admin', 'teacher')
            if role in active_roles_by_user[user_id]
        ]
        for user_id in page_user_ids
    }

    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'total': total,
            'page': int(page_number),
            'page_size': page_size,
            'items': InstitutionMemberSerializer(
                items, many=True, context={'roles_by_user': roles_by_user},
            ).data,
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

    if not _can_manage_institution_members(request, institution_id):
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
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_member(request, institution_id):
    return _add_member_impl(request, institution_id)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_member(request, institution_id, user_id):
    """PUT /api/v1/institutions/<id>/members/<user_id> - Update member role/status."""
    try:
        institution = Institution.objects.get(id=institution_id)
    except Institution.DoesNotExist:
        return Response({
            'code': 4004, 'message': '机构不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not _can_manage_institution_members(request, institution_id):
        return Response({
            'code': 4003, 'message': '无权限操作', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_403_FORBIDDEN)

    if not InstitutionMember.objects.filter(
        institution=institution, user_id=user_id,
    ).exists():
        return Response({
            'code': 4004, 'message': '成员不存在', 'data': None, 'trace_id': _trace(),
        }, status=status.HTTP_404_NOT_FOUND)

    selected_roles = request.data.get('roles')
    if selected_roles is not None:
        if (
            not isinstance(selected_roles, list)
            or any(role not in ('admin', 'teacher') for role in selected_roles)
        ):
            return Response({
                'code': 4001,
                'message': 'roles must contain only admin or teacher',
                'data': None,
                'trace_id': _trace(),
            }, status=status.HTTP_400_BAD_REQUEST)
        selected_roles = set(selected_roles)

    with transaction.atomic():
        members = list(InstitutionMember.objects.select_for_update().filter(
            institution=institution, user_id=user_id,
        ).select_related('user'))
        user = members[0].user

        new_mobile = request.data.get('mobile')
        if new_mobile is not None:
            new_mobile = new_mobile.strip()
            if (
                new_mobile
                and new_mobile != user.mobile
                and UserAccount.objects.filter(mobile=new_mobile).exclude(id=user.id).exists()
            ):
                return Response({
                    'code': 4001,
                    'message': '该手机号已被其他账号使用',
                    'data': None,
                    'trace_id': _trace(),
                }, status=status.HTTP_400_BAD_REQUEST)

        requested_status = request.data.get('status')
        if requested_status == 'removed':
            InstitutionMember.objects.filter(
                institution=institution, user_id=user_id,
            ).update(status='removed')
        elif selected_roles is not None:
            for role in ('admin', 'teacher'):
                if role in selected_roles:
                    InstitutionMember.objects.update_or_create(
                        institution=institution,
                        user=user,
                        role=role,
                        defaults={'status': 'active'},
                    )
                    if role == 'teacher':
                        grant_user_role(user, 'teacher')
                else:
                    InstitutionMember.objects.filter(
                        institution=institution,
                        user=user,
                        role=role,
                    ).update(status='removed')
        elif requested_status is not None:
            InstitutionMember.objects.filter(
                institution=institution, user_id=user_id,
            ).update(status=requested_status)

        user_changed = False
    if 'mobile' in request.data:
        new_mobile = request.data['mobile'].strip()
        if new_mobile and new_mobile != user.mobile:
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
    member = InstitutionMember.objects.filter(
        institution=institution, user_id=user_id, status='active',
    ).order_by('role').first()
    if member is None:
        member = InstitutionMember.objects.filter(
            institution=institution, user_id=user_id,
        ).order_by('role').first()

    return Response({
        'code': 0,
        'message': '更新成功',
        'data': InstitutionMemberSerializer(member).data,
        'trace_id': _trace(),
    })
