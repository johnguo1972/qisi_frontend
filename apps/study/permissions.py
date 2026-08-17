from rest_framework import permissions
from django.core.cache import cache
from apps.accounts.auth import get_request_role
from apps.accounts.models import StudentParentBind
from apps.accounts.roles import has_user_role
from apps.institutions.models import ClassStudent


class IsStudent(permissions.BasePermission):
    """Require a student session, active grant, and active class membership."""
    def has_permission(self, request, view):
        return (
            get_request_role(request) == 'student'
            and has_user_role(request.user, 'student')
            and ClassStudent.objects.filter(
                student=request.user, status='active',
            ).exists()
        )


def effective_student_user(request):
    """Return the student represented by a student or an active parent context."""
    active_role = get_request_role(request)
    if (
        active_role == 'student'
        and has_user_role(request.user, 'student')
        and ClassStudent.objects.filter(student=request.user, status='active').exists()
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


def effective_student_home_user(request):
    """Return the student represented by a student session or parent context.

    The home page is also a valid entry point for a newly-created student
    account that has not joined a class yet.  It must be able to return an
    empty home state instead of turning that normal business state into 403.
    Parent requests still require a validated, selected child context.
    """
    active_role = get_request_role(request)
    if active_role == 'student' and has_user_role(request.user, 'student'):
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
