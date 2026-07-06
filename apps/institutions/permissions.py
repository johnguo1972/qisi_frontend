from rest_framework import permissions

from apps.institutions.models import InstitutionMember, ClassTeacher


class IsPlatformAdmin(permissions.BasePermission):
    """Only platform admins (role_type == 'admin') can access."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role_type == 'admin'


class IsInstitutionAdmin(permissions.BasePermission):
    """Only active admin members of the institution can access."""

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        institution_id = getattr(obj, 'id', None)
        if institution_id is None:
            # If the object is not an Institution, try to get it from the object
            institution_id = getattr(obj, 'institution_id', None)
        if institution_id is None:
            return False
        return InstitutionMember.objects.filter(
            institution_id=institution_id,
            user=request.user,
            role='admin',
            status='active',
        ).exists()


class IsClassTeacher(permissions.BasePermission):
    """Only teachers assigned to the class can access."""

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        class_id = getattr(obj, 'id', None)
        if class_id is None:
            class_id = getattr(obj, 'class_obj_id', None)
        if class_id is None:
            return False
        return ClassTeacher.objects.filter(
            class_obj_id=class_id,
            teacher=request.user,
        ).exists()
