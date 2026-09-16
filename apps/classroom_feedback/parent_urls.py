from django.urls import path

from .parent_views import parent_classroom_feedback

urlpatterns = [
    path('missions/<uuid:mission_id>/classroom-feedback', parent_classroom_feedback, name='parent-classroom-feedback'),
]
