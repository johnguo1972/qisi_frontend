"""Papers app URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_paper, name='upload-paper'),
    path('<int:paper_id>/parse/', views.start_parse, name='start-parse'),
    path('<int:paper_id>/stop-parse/', views.stop_parse, name='stop-parse'),
    path('<int:paper_id>/reparse/', views.reparse_paper, name='reparse-paper'),
    path('<int:paper_id>/progress/', views.paper_parse_progress, name='paper-progress'),
    path('<int:paper_id>/', views.delete_paper, name='delete-paper'),
]
