from rest_framework import permissions
from django.core.cache import cache
from apps.accounts.auth import get_request_role
from apps.accounts.models import StudentParentBind
from apps.accounts.roles import has_user_role


class IsStudent(permissions.BasePermission):
    """Require a student session and active student grant."""
    def has_permission(self, request, view):
        return (
            get_request_role(request) == 'student'
            and has_user_role(request.user, 'student')
        )


class IsStudentOnly(permissions.BasePermission):
    """Allow learning writes only for an active student session."""

    message = '家长端仅支持查看，不能代替学生答题'

    def has_permission(self, request, view):
        return (
            get_request_role(request) == 'student'
            and getattr(request.user, 'status', None) == 'active'
            and has_user_role(request.user, 'student')
        )


class IsNotParentSession(permissions.BasePermission):
    """Reject parent sessions while preserving existing teacher/admin checks."""

    message = '家长端仅支持查看，不能代替学生答题'

    def has_permission(self, request, view):
        return (
            get_request_role(request) != 'parent'
            and getattr(request.user, 'role_type', None) != 'parent'
        )


def effective_student_user(request):
    """Return the student represented by a student or an active parent context."""
    active_role = get_request_role(request)
    if (
        active_role == 'student'
        and getattr(request.user, 'status', None) == 'active'
        and has_user_role(request.user, 'student')
    ):
        return request.user
    if (
        active_role != 'parent'
        or getattr(request.user, 'status', None) != 'active'
        or not has_user_role(request.user, 'parent')
    ):
        return None
    child_id = cache.get(f'parent_context:{request.user.id}')
    if not child_id:
        return None
    relation = StudentParentBind.objects.filter(
        parent_user_id=request.user, student_user_id=child_id, bind_status='active',
    ).select_related('student_user_id').first()
    if not relation or relation.student_user_id.status != 'active':
        return None
    return relation.student_user_id


class IsParentReadContext(permissions.BasePermission):
    """Require an active parent session and an active selected child."""

    message = '请先选择已绑定的孩子'

    def has_permission(self, request, view):
        if get_request_role(request) != 'parent':
            return False
        student = effective_student_user(request)
        if student is None:
            return False
        request._effective_student = student
        request._user = student
        return True


def effective_student_home_user(request):
    """Return the student represented by a student session or parent context.

    The home page is also a valid entry point for a newly-created student
    account that has not joined a class yet.  It must be able to return an
    empty home state instead of turning that normal business state into 403.
    Parent requests still require a validated, selected child context.
    """
    active_role = get_request_role(request)
    if (
        active_role == 'student'
        and getattr(request.user, 'status', None) == 'active'
        and has_user_role(request.user, 'student')
    ):
        return request.user
    return effective_student_user(request)


class IsStudentOrParentContext(permissions.BasePermission):
    """Allow students and parents with a valid selected child context."""
    def has_permission(self, request, view):
        student = effective_student_user(request)
        if student is None:
            return False
        # Existing student views use request.user throughout; scope them to the
        # validated child for this request without changing authentication data.
        request._effective_student = student
        request._user = student
        return True


class IsStudentOrParentHomeContext(permissions.BasePermission):
    """Allow the home page for students and validated parent contexts."""

    def has_permission(self, request, view):
        student = effective_student_home_user(request)
        if student is None:
            return False
        request._effective_student = student
        request._user = student
        return True
