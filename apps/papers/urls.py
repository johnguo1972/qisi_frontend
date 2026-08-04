"""Papers app URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:paper_id>/', views.delete_paper, name='delete-paper'),
]
