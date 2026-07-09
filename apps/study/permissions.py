from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    """仅允许 role_type=='student'。"""
    def has_permission(self, request, view):
        return getattr(request.user, 'role_type', None) == 'student'
