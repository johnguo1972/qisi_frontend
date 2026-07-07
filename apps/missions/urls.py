from django.urls import path
from . import views

app_name = 'missions'
urlpatterns = [
    path('', views.mission_list, name='mission-list'),
    path('<int:mission_id>/', views.mission_detail, name='mission-detail'),
    path('<int:mission_id>/delete/', views.mission_delete, name='mission-delete'),
    path('<int:mission_id>/levels/', views.mission_levels, name='mission-levels'),
    path('<int:mission_id>/levels/batch/', views.mission_levels_batch, name='mission-levels-batch'),
    path('<int:mission_id>/levels/<int:level_id>/', views.mission_level_detail, name='mission-level-detail'),
    path('<int:mission_id>/questions/', views.mission_questions, name='mission-questions'),
    path('<int:mission_id>/publish/', views.mission_publish, name='mission-publish'),
    path('<int:mission_id>/clone/', views.mission_clone, name='mission-clone'),
    path('<int:mission_id>/clone-with-class/', views.mission_clone_with_class, name='mission-clone-with-class'),
    # Teacher B/C mode guidance
    path('guidance/start/', views.start_teacher_guidance, name='teacher-guidance-start'),
    path('guidance/reply/<str:session_id>/', views.teacher_guidance_reply, name='teacher-guidance-reply'),
]
