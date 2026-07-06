"""API routes for review app."""
from django.urls import path
from . import views

urlpatterns = [
    path('review/papers/', views.paper_review_list, name='paper-review-list'),
    path('review/papers/<int:paper_id>/questions/', views.question_list, name='question-list'),
    path('review/questions/<int:question_id>/', views.question_detail, name='question-detail'),
    path('review/questions/<int:question_id>/update/', views.question_update, name='question-update'),
    path('review/questions/<int:question_id>/confirm/', views.question_confirm, name='question-confirm'),
    path('review/questions/<int:question_id>/reject/', views.question_reject, name='question-reject'),
    path('review/questions/<int:question_id>/delete/', views.question_delete, name='question-delete'),
    # AI Review endpoints
    path('review/question/<int:question_id>/ai-process/', views.ai_process_question, name='ai-process-question'),
    path('review/ai-task/<str:task_id>/status/', views.single_ai_task_status, name='single-ai-task-status'),
    path('review/question/<int:question_id>/ai-process-mode/<str:mode>/', views.ai_process_single_mode, name='ai-process-single-mode'),
    path('review/ai-task/<str:task_id>/status-v2/', views.ai_task_status, name='ai-task-status'),
    path('review/question/<int:question_id>/ai-confirm/<str:mode>/', views.ai_confirm_answer, name='ai-confirm-answer'),
    path('review/question/<int:question_id>/ai-answer/<str:mode>/', views.ai_update_answer, name='ai-update-answer'),
    path('review/question/<int:question_id>/ai-knowledge/', views.ai_update_knowledge, name='ai-update-knowledge'),
    path('review/question/<int:question_id>/ai-status/', views.ai_question_status, name='ai-question-status'),
    # Batch AI processing endpoints
    path('review/batch-ai-process/', views.batch_ai_process, name='batch-ai-process'),
    path('review/batch-task/<str:task_id>/status/', views.batch_task_status, name='batch-task-status'),
    path('review/batch-task/<str:task_id>/cancel/', views.batch_task_cancel, name='batch-task-cancel'),
    # JSON bbox crop & assets management REST APIs
    path('review/questions/<int:question_id>/assets/', views.get_question_assets, name='get-question-assets'),
    path('review/questions/<int:question_id>/images/crop/', views.crop_question_image_api, name='crop-question-image-api'),
    path('review/questions/<int:question_id>/images/<int:image_id>/', views.delete_question_image_api, name='delete-question-image-api'),
]
