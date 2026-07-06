"""URL configuration for knowledge app (page views)."""
from django.urls import path
from . import views

urlpatterns = [
    path('knowledge/', views.knowledge_list, name='knowledge-list'),
    path('knowledge/tree-data/', views.tree_data, name='knowledge-tree-data'),
]
