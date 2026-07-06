"""Dictionary API URL routes."""
from django.urls import path
from . import dict_views

urlpatterns = [
    path('subjects', dict_views.subjects, name='dict-subjects'),
    path('knowledge-points', dict_views.knowledge_points, name='dict-knowledge'),
    path('question-types', dict_views.question_types, name='dict-question-types'),
    path('difficulty-levels', dict_views.difficulty_levels, name='dict-difficulty'),
]
