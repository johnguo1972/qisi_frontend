"""URL routing for institutions app."""

from django.urls import path

from . import (
    institution_views,
    member_views,
    class_views,
    request_views,
    student_views,
)

app_name = 'institutions'

urlpatterns = [
    # ── Admin: Institution management ──
    path('admin/institutions', institution_views.institution_list_create, name='institution-list-create'),
    path('admin/institutions/<int:institution_id>', institution_views.institution_detail, name='institution-detail'),
    path('admin/institutions/<int:institution_id>/status', institution_views.update_institution_status, name='institution-status'),

    # ── Institution Admin: Member management ──
    path('institutions/<int:institution_id>/members', member_views.member_list_add, name='member-list-add'),
    path('institutions/<int:institution_id>/members/<int:user_id>', member_views.update_member, name='member-update'),

    # ── Teacher: Get my institutions ──
    path('teacher/institutions', institution_views.teacher_institutions, name='teacher-institutions'),

    # ── Teacher: Class management ──
    path('classes', class_views.class_list_create, name='class-list-create'),
    path('classes/simple', class_views.class_simple_list, name='class-simple-list'),
    path('classes/<int:class_id>', class_views.class_detail, name='class-detail'),
    path('classes/<int:class_id>/regenerate-code', class_views.regenerate_invite_code, name='class-regenerate-code'),
    path('classes/<int:class_id>/students', class_views.class_students, name='class-students'),
    path('classes/<int:class_id>/students/<int:student_id>', class_views.remove_student, name='class-remove-student'),

    # ── Teacher: Join request approval ──
    path('classes/<int:class_id>/join-requests', request_views.join_request_list, name='join-request-list'),
    path('classes/join-requests/<int:request_id>/approve', request_views.approve_request, name='join-request-approve'),
    path('classes/join-requests/<int:request_id>/reject', request_views.reject_request, name='join-request-reject'),

    # ── Student: Join classes ──
    path('student/classes/search', student_views.search_classes, name='student-search-classes'),
    path('student/classes/join-by-code', student_views.join_by_code, name='student-join-by-code'),
    path('student/classes/<int:class_id>/quit', student_views.quit_class, name='student-quit-class'),
    path('student/my-classes', student_views.my_classes, name='student-my-classes'),
    path('classes/join-request', student_views.submit_join_request, name='student-submit-join-request'),
    path('student/join-requests', student_views.my_join_requests, name='student-my-join-requests'),
]
