"""Permissions that keep both the effective student and the audit actor."""
from rest_framework import permissions

from apps.accounts.auth import get_request_role
from apps.accounts.roles import has_user_role
from apps.study.permissions import effective_student_user

from .feature_flags import practice_feature_enabled_for


class IsPracticeStudentOrParentContext(permissions.BasePermission):
    message = '精练功能暂未对当前账号开放'

    def has_permission(self, request, view):
        actor = getattr(request, 'user', None)
        if not practice_feature_enabled_for(actor):
            return False
        student = effective_student_user(request)
        if student is None:
            return False
        request._practice_actor = actor
        request._effective_student = student
        return True


class IsPracticeStudentOnly(permissions.BasePermission):
    message = '家长端不能代替学生提交精练答案'

    def has_permission(self, request, view):
        if not practice_feature_enabled_for(getattr(request, 'user', None)):
            return False
        if get_request_role(request) != 'student':
            return False
        if getattr(request.user, 'status', None) != 'active' or not has_user_role(request.user, 'student'):
            return False
        request._practice_actor = request.user
        request._effective_student = request.user
        return True
