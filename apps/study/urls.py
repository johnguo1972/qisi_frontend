"""Study app URLs: question search, import batches, and dict endpoints."""
from django.urls import path
from . import question_views, import_views, dict_views, create_views, photo_views

urlpatterns = [
    # Question endpoints (at /api/v1/questions/)
    path('', question_views.question_list, name='question-list'),
    # Manual question creation (MUST come before <int:question_id> to avoid URL conflict)
    path('create/', create_views.create_question, name='create-question'),
    path('upload-image/', create_views.upload_question_image, name='upload-question-image'),
    path('photo-create/', photo_views.photo_create_question, name='photo-create'),
    path('photo-list/', photo_views.photo_list_questions, name='photo-list'),
    # Import batches
    path('import-batches', import_views.import_batch_list, name='import-batch-list'),
    path('import-batches/<int:batch_id>', import_views.import_batch_detail, name='import-batch-detail'),
    path('papers', import_views.paper_list, name='paper-list'),
    # Question detail/publish
    path('<int:question_id>', question_views.question_detail, name='question-detail'),
    path('<int:question_id>/publish', question_views.question_publish, name='question-publish'),
]
