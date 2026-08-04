"""Papers app URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_paper, name='upload-paper'),
    path('<uuid:paper_id>/parse/', views.start_parse, name='start-parse'),
    path('<uuid:paper_id>/stop-parse/', views.stop_parse, name='stop-parse'),
    path('<uuid:paper_id>/reparse/', views.reparse_paper, name='reparse-paper'),
    path('<uuid:paper_id>/progress/', views.paper_parse_progress, name='paper-progress'),
    path('<uuid:paper_id>/', views.delete_paper, name='delete-paper'),
]
