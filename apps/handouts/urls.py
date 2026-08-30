from django.urls import path
from . import views

urlpatterns = [
    path('handouts/', views.handout_list_or_create, name='handout-list-create'),
    path('handouts/<uuid:handout_id>/', views.handout_detail, name='handout-detail'),
    path('handouts/<uuid:handout_id>/questions/replace/', views.handout_replace_questions, name='handout-questions-replace'),
    path('handouts/<uuid:handout_id>/preview/', views.handout_preview, name='handout-preview'),
    path('handouts/<uuid:handout_id>/publish/', views.handout_publish, name='handout-publish'),
    path('handouts/<uuid:handout_id>/export-pdf/', views.handout_export_pdf, name='handout-export-pdf'),
]
