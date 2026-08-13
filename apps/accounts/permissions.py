from rest_framework import permissions

from apps.accounts.auth import get_request_role
from apps.accounts.roles import has_user_role


class IsTeacherSession(permissions.BasePermission):
    """Require a teacher-authenticated session with an active teacher grant."""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and get_request_role(request) == "teacher"
            and has_user_role(request.user, "teacher")
        )
