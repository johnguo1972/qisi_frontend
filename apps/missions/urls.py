from django.urls import path
from . import views

app_name = 'missions'
urlpatterns = [
    path('', views.mission_list, name='mission-list'),
    # Keep both canonical API forms during the existing frontend migration.
    # POST/PUT callers must not depend on APPEND_SLASH redirects.
    path('<uuid:mission_id>', views.mission_detail, name='mission-detail-no-slash'),
    path('<uuid:mission_id>/', views.mission_detail, name='mission-detail'),
    path('<uuid:mission_id>/delete', views.mission_delete, name='mission-delete-no-slash'),
    path('<uuid:mission_id>/delete/', views.mission_delete, name='mission-delete'),
    path('<uuid:mission_id>/levels', views.mission_levels, name='mission-levels-no-slash'),
    path('<uuid:mission_id>/levels/', views.mission_levels, name='mission-levels'),
    path('<uuid:mission_id>/levels/batch', views.mission_levels_batch, name='mission-levels-batch-no-slash'),
    path('<uuid:mission_id>/levels/batch/', views.mission_levels_batch, name='mission-levels-batch'),
    path('<uuid:mission_id>/levels/<uuid:level_id>', views.mission_level_detail, name='mission-level-detail-no-slash'),
    path('<uuid:mission_id>/levels/<uuid:level_id>/', views.mission_level_detail, name='mission-level-detail'),
    path('<uuid:mission_id>/questions', views.mission_questions, name='mission-questions-no-slash'),
    path('<uuid:mission_id>/questions/', views.mission_questions, name='mission-questions'),
    path('<uuid:mission_id>/favorites', views.mission_add_favorites, name='mission-add-favorites-no-slash'),
    path('<uuid:mission_id>/favorites/', views.mission_add_favorites, name='mission-add-favorites'),
    path('<uuid:mission_id>/export-pdf', views.mission_export_pdf, name='mission-export-pdf-no-slash'),
    path('<uuid:mission_id>/export-pdf/', views.mission_export_pdf, name='mission-export-pdf'),
    path('<uuid:mission_id>/grading', views.mission_grading, name='mission-grading-no-slash'),
    path('<uuid:mission_id>/grading/', views.mission_grading, name='mission-grading'),
    path('<uuid:mission_id>/grading/attempts/<uuid:attempt_id>', views.mission_grade_attempt, name='mission-grade-attempt-no-slash'),
    path('<uuid:mission_id>/grading/attempts/<uuid:attempt_id>/', views.mission_grade_attempt, name='mission-grade-attempt'),
    path('<uuid:mission_id>/grading/generate-variant', views.mission_generate_variant, name='mission-generate-variant-no-slash'),
    path('<uuid:mission_id>/grading/generate-variant/', views.mission_generate_variant, name='mission-generate-variant'),
    path('<uuid:mission_id>/publish', views.mission_publish, name='mission-publish-no-slash'),
    path('<uuid:mission_id>/publish/', views.mission_publish, name='mission-publish'),
    path('<uuid:mission_id>/clone', views.mission_clone, name='mission-clone-no-slash'),
    path('<uuid:mission_id>/clone/', views.mission_clone, name='mission-clone'),
    path('<uuid:mission_id>/clone-with-class', views.mission_clone_with_class, name='mission-clone-with-class-no-slash'),
    path('<uuid:mission_id>/clone-with-class/', views.mission_clone_with_class, name='mission-clone-with-class'),
    # Teacher B/C mode guidance
    path('guidance/start/', views.start_teacher_guidance, name='teacher-guidance-start'),
    path('guidance/reply/<str:session_id>/', views.teacher_guidance_reply, name='teacher-guidance-reply'),
]
