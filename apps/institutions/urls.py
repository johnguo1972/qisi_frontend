"""URL routing for institutions app."""

from django.urls import path

from . import (
    institution_views,
    member_views,
    class_views,
    request_views,
    student_views,
    import_views,
)

app_name = 'institutions'

urlpatterns = [
    # ── Admin: Institution management ──
    path('admin/institutions', institution_views.institution_list_create, name='institution-list-create'),
    path('admin/institutions/<uuid:institution_id>', institution_views.institution_detail, name='institution-detail'),
    path('admin/institutions/<uuid:institution_id>/status', institution_views.update_institution_status, name='institution-status'),

    # ── Institution Admin: Member management ──
    path('institutions/<uuid:institution_id>/members', member_views.member_list_add, name='member-list-add'),
    path('institutions/<uuid:institution_id>/members/<uuid:user_id>', member_views.update_member, name='member-update'),

    # ── Teacher: Get my institutions ──
    path('teacher/institutions', institution_views.teacher_institutions, name='teacher-institutions'),

    # ── Teacher: Class management ──
    path('classes', class_views.class_list_create, name='class-list-create'),
    path('classes/simple', class_views.class_simple_list, name='class-simple-list'),
    path('classes/<uuid:class_id>', class_views.class_detail, name='class-detail'),
    path('classes/<uuid:class_id>/regenerate-code', class_views.regenerate_invite_code, name='class-regenerate-code'),
    path('classes/<uuid:class_id>/students', class_views.class_students, name='class-students'),
    path('classes/<uuid:class_id>/students/import-template', import_views.import_template, name='student-import-template'),
    path('classes/<uuid:class_id>/students/import', import_views.import_students, name='student-import'),
    path('student-imports/<uuid:task_id>', import_views.import_status, name='student-import-status'),
    path('student-imports/<uuid:task_id>/errors', import_views.import_errors, name='student-import-errors'),
    path('classes/<uuid:class_id>/learning-stats', class_views.class_learning_stats, name='class-learning-stats'),
    path('classes/<uuid:class_id>/students/<uuid:student_id>', class_views.remove_student, name='class-student-manage'),

    # ── Teacher: Join request approval ──
    path('classes/<uuid:class_id>/join-requests', request_views.join_request_list, name='join-request-list'),
    path('classes/join-requests/<uuid:request_id>/approve', request_views.approve_request, name='join-request-approve'),
    path('classes/join-requests/<uuid:request_id>/reject', request_views.reject_request, name='join-request-reject'),

    # ── Student: Join classes ──
    path('student/classes/search', student_views.search_classes, name='student-search-classes'),
    path('student/classes/join-by-code', student_views.join_by_code, name='student-join-by-code'),
    path('student/classes/<uuid:class_id>/quit', student_views.quit_class, name='student-quit-class'),
    path('student/my-classes', student_views.my_classes, name='student-my-classes'),
    path('classes/join-request', student_views.submit_join_request, name='student-submit-join-request'),
    path('student/join-requests', student_views.my_join_requests, name='student-my-join-requests'),
]
