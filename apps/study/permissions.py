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


def effective_student_user(request):
    """Return the student represented by a student or an active parent context."""
    active_role = get_request_role(request)
    if (
        active_role == 'student'
        and has_user_role(request.user, 'student')
    ):
        return request.user
    if active_role != 'parent' or not has_user_role(request.user, 'parent'):
        return None
    child_id = cache.get(f'parent_context:{request.user.id}')
    if not child_id:
        return None
    relation = StudentParentBind.objects.filter(
        parent_user_id=request.user, student_user_id=child_id, bind_status='active',
    ).select_related('student_user_id').first()
    return relation.student_user_id if relation else None


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
