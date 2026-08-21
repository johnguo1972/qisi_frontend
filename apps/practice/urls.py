from django.urls import path

from . import views


app_name = 'practice'

urlpatterns = [
    path('health', views.practice_health, name='practice-health'),
    path('health/', views.practice_health, name='practice-health-slash'),
    path('pool', views.pool_list, name='pool-list-no-slash'),
    path('pool/', views.pool_list, name='pool-list'),
    path('pool/items', views.pool_items_create, name='pool-items-create'),
    path('pool/items/', views.pool_items_create, name='pool-items-create-slash'),
    path('pool/items/<uuid:item_id>', views.pool_item_remove, name='pool-item-remove'),
    path('pool/items/<uuid:item_id>/', views.pool_item_remove, name='pool-item-remove-slash'),
    path('pool/items/batch-remove', views.pool_items_batch_remove, name='pool-items-batch-remove'),
    path('pool/items/batch-remove/', views.pool_items_batch_remove, name='pool-items-batch-remove-slash'),
    path('sets/', views.practice_set_list, name='practice-set-list'),
    path('sets', views.practice_set_list, name='practice-set-list-no-slash'),
    path('sets/create', views.practice_set_create, name='practice-set-create'),
    path('sets/create/', views.practice_set_create, name='practice-set-create-slash'),
    path('sets/<uuid:set_id>/', views.practice_set_detail, name='practice-set-detail'),
    path('sets/<uuid:set_id>/activate', views.practice_set_activate, name='practice-set-activate'),
    path('sets/<uuid:set_id>/activate/', views.practice_set_activate, name='practice-set-activate-slash'),
    path('sets/<uuid:set_id>/submit', views.practice_set_submit, name='practice-set-submit'),
    path('sets/<uuid:set_id>/submit/', views.practice_set_submit, name='practice-set-submit-slash'),
    path('sets/<uuid:set_id>/questions', views.practice_set_questions, name='practice-set-questions'),
    path('sets/<uuid:set_id>/questions/', views.practice_set_questions, name='practice-set-questions-slash'),
    path('sets/<uuid:set_id>/progress', views.practice_set_progress, name='practice-set-progress'),
    path('sets/<uuid:set_id>/progress/', views.practice_set_progress, name='practice-set-progress-slash'),
    path('sets/<uuid:set_id>/items/<uuid:set_item_id>/attempts', views.practice_attempt_submit, name='practice-attempt-submit'),
    path('sets/<uuid:set_id>/items/<uuid:set_item_id>/attempts/', views.practice_attempt_submit, name='practice-attempt-submit-slash'),
    path('sets/<uuid:set_id>/items/<uuid:set_item_id>/attempts/draft', views.practice_photo_attempt_draft, name='practice-photo-attempt-draft'),
    path('sets/<uuid:set_id>/items/<uuid:set_item_id>/attempts/draft/', views.practice_photo_attempt_draft, name='practice-photo-attempt-draft-slash'),
    path('attempts/<uuid:attempt_id>/images', views.practice_photo_image_upload, name='practice-photo-image-upload'),
    path('attempts/<uuid:attempt_id>/images/', views.practice_photo_image_upload, name='practice-photo-image-upload-slash'),
    path('attempts/<uuid:attempt_id>/submit', views.practice_photo_attempt_submit, name='practice-photo-attempt-submit'),
    path('attempts/<uuid:attempt_id>/submit/', views.practice_photo_attempt_submit, name='practice-photo-attempt-submit-slash'),
    path('sets/<uuid:set_id>/export-pdf', views.practice_set_export_pdf, name='practice-set-export-pdf'),
    path('sets/<uuid:set_id>/export-pdf/', views.practice_set_export_pdf, name='practice-set-export-pdf-slash'),
    path('sets/<uuid:set_id>/pdf', views.practice_set_pdf, name='practice-set-pdf'),
    path('sets/<uuid:set_id>/pdf/', views.practice_set_pdf, name='practice-set-pdf-slash'),
    path(
        'wrong-book/<uuid:wrong_item_id>/candidates/',
        views.wrongbook_candidates,
        name='wrongbook-candidates',
    ),
    # 兼容小程序请求被代理层去掉末尾斜杠的情况。
    path(
        'wrong-book/<uuid:wrong_item_id>/candidates',
        views.wrongbook_candidates,
        name='wrongbook-candidates-no-slash',
    ),
]
