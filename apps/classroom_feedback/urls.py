from django.urls import path

from .views import classroom_feedback_detail, classroom_feedback_export_pdf, classroom_feedback_generate

urlpatterns = [
    path('missions/<uuid:mission_id>/classroom-feedback', classroom_feedback_detail, name='classroom-feedback-detail'),
    path('missions/<uuid:mission_id>/classroom-feedback/generate', classroom_feedback_generate, name='classroom-feedback-generate'),
    path('missions/<uuid:mission_id>/classroom-feedback/export-pdf', classroom_feedback_export_pdf, name='classroom-feedback-export-pdf'),
]
