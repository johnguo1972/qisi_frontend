"""Papers app URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_paper, name='upload-paper'),
    # ``str`` keeps the legacy endpoint's JSON 404 contract for malformed IDs;
    # the view still validates the ID through the ORM.
    path('<str:paper_id>/parse/', views.start_parse, name='start-parse'),
    path('<str:paper_id>/stop-parse/', views.stop_parse, name='stop-parse'),
    path('<str:paper_id>/reparse/', views.reparse_paper, name='reparse-paper'),
    path('<str:paper_id>/progress/', views.paper_parse_progress, name='paper-progress'),
    path('<str:paper_id>/', views.delete_paper, name='delete-paper'),
]
