from django.urls import path

from .parent_views import parent_mission_detail, parent_missions, parent_overview

urlpatterns = [
    path('overview', parent_overview, name='parent-overview'),
    path('missions', parent_missions, name='parent-missions'),
    path('missions/<uuid:mission_id>', parent_mission_detail, name='parent-mission-detail'),
]
