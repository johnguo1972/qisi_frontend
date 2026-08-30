"""Study app URLs: question search, import batches, and dict endpoints."""
from django.urls import path
from . import question_views, import_views, dict_views, create_views, photo_views
from . import json_import_views, basket_views, batch_views
# 新增导入（barcode_views 依赖 python-barcode，设为可选）
from . import tag_views
from . import qr_views
from apps.knowledge import match_views
try:
    from . import barcode_views
    HAS_BARCODE = True
except ImportError:
    barcode_views = None
    HAS_BARCODE = False

urlpatterns = [
    # === 现有路由（不变）===
    path('', question_views.question_list, name='question-list'),
    path('create/', create_views.create_question, name='create-question'),
    path('upload-image/', create_views.upload_question_image, name='upload-question-image'),
    path('photo-create/', photo_views.photo_create_question, name='photo-create'),
    path('photo-list/', photo_views.photo_list_questions, name='photo-list'),
    path('import-batches', import_views.import_batch_list, name='import-batch-list'),
    path('import-batches/<uuid:batch_id>', import_views.import_batch_detail, name='import-batch-detail'),
    path('papers', import_views.paper_list, name='paper-list'),

    # === 新增路由（必须在通用题目 UUID 路由之前注册！）===

    # 标签管理
    path('tags/', tag_views.tag_list, name='tag-list'),
    path('tags/create/', tag_views.tag_create, name='tag-create'),
    path('tags/<str:tag_id>/update/', tag_views.tag_update, name='tag-update'),
    path('tags/<str:tag_id>/delete/', tag_views.tag_delete, name='tag-delete'),

    # P2 question/knowledge-point matching
    path('knowledge-matches/preview', match_views.knowledge_match_preview, name='knowledge-match-preview'),
    path('knowledge-matches/batch-confirm', match_views.knowledge_match_batch_confirm, name='knowledge-match-batch-confirm'),
    path('knowledge-matches/pending', match_views.knowledge_match_pending, name='knowledge-match-pending'),
    path('knowledge-matches/rebuild', match_views.knowledge_match_rebuild_batch, name='knowledge-match-rebuild-batch'),
    path('<uuid:question_id>/knowledge-matches/rebuild', match_views.knowledge_match_rebuild, name='knowledge-match-rebuild'),

    # JSON数据包导入
    path('import-json-package', json_import_views.import_json_package, name='import-json-package'),
    path('import-json-task/<str:task_id>/status/', json_import_views.import_json_task_status, name='import-json-task-status'),
    path('json-import-history/', json_import_views.json_import_history, name='json-import-history'),

    # 题目篮子
    path('basket/', basket_views.basket_list, name='basket-list'),
    path('basket/add/', basket_views.basket_add, name='basket-add'),
    path('basket/<str:question_id>/', basket_views.basket_remove, name='basket-remove'),
    path('basket/clear/', basket_views.basket_clear, name='basket-clear'),

    # 批量操作
    path('batch-update/', batch_views.batch_update, name='batch-update'),
    path('<str:question_id>/qr/', qr_views.question_qr, name='question-qr'),
    path('<str:question_id>/similar/', question_views.similar_questions, name='similar-questions'),

    # 条形码（需要 python-barcode 包）
    path('barcode/scan/', barcode_views.barcode_scan if HAS_BARCODE else lambda r: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'code': 503, 'message': 'python-barcode not installed'}, status=503), name='barcode-scan'),

    # ️ 以下通配路由必须放在最后
    path('<uuid:question_id>', question_views.question_detail, name='question-detail'),
    path('<uuid:question_id>/publish', question_views.question_publish, name='question-publish'),

    # 题目标签（通配路由，放在最后）
    path('<str:question_id>/tags/', tag_views.question_tags, name='question-tags'),
    path('<str:question_id>/tags/add/', tag_views.question_add_tag, name='question-add-tag'),
    path('<str:question_id>/tags/<str:tag_id>/remove/', tag_views.question_remove_tag, name='question-remove-tag'),
]

# 条形码图片路由（仅当 python-barcode 可用时注册）
if HAS_BARCODE:
    urlpatterns.append(
        path('<str:question_id>/barcode/', barcode_views.question_barcode, name='question-barcode')
    )
