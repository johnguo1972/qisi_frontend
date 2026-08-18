"""Papers app URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    # ``str`` keeps the legacy endpoint's JSON 404 contract for malformed IDs;
    # the view still validates the ID through the ORM.
    path('<str:paper_id>/', views.delete_paper, name='delete-paper'),
]
