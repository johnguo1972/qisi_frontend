from rest_framework import permissions
from django.core.cache import cache
from apps.accounts.models import StudentParentBind


class IsStudent(permissions.BasePermission):
    """仅允许 role_type=='student'。"""
    def has_permission(self, request, view):
        return getattr(request.user, 'role_type', None) == 'student'


def effective_student_user(request):
    """Return the student represented by a student or an active parent context."""
    if getattr(request.user, 'role_type', None) == 'student':
        return request.user
    if getattr(request.user, 'role_type', None) != 'parent':
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
