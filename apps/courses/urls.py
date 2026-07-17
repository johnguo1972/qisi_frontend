"""课程管理 URL 路由"""
from django.urls import path
from . import views

urlpatterns = [
    # 课程 CRUD（合并视图：GET/POST 共用一个 path）
    path('courses/', views.course_list_or_create, name='course-list-create'),
    path('courses/<int:course_id>/', views.course_detail_update_delete, name='course-detail-update-delete'),

    # 课程资料
    path('courses/<int:course_id>/materials/', views.material_list, name='material-list'),
    path('courses/<int:course_id>/materials/upload/', views.material_upload, name='material-upload'),
    path('courses/<int:course_id>/materials/<int:material_id>/download/', views.material_download, name='material-download'),
    path('courses/<int:course_id>/materials/<int:material_id>/preview/', views.material_preview, name='material-preview'),
    path('courses/<int:course_id>/materials/<int:material_id>/', views.material_delete, name='material-delete'),

    # 目录树（合并视图：GET/POST 共用一个 path）
    path('courses/<int:course_id>/tree/', views.tree_list_or_create, name='tree-list-create'),
    path('courses/<int:course_id>/tree/<int:node_id>/', views.tree_node_update_or_delete, name='tree-node-update-delete'),
    path('courses/<int:course_id>/tree/<int:node_id>/move/', views.tree_node_move, name='tree-node-move'),

    # 变式任务查询
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/', views.variant_task_detail, name='variant-task-detail'),

    # ============================================================
    # 习题管理
    # ============================================================
    path('courses/<int:course_id>/questions/', views.question_list, name='question-list'),
    path('courses/<int:course_id>/questions/import/', views.question_import, name='question-import'),
    path('courses/<int:course_id>/questions/batch-delete/', views.question_batch_delete, name='question-batch-delete'),
    path('courses/<int:course_id>/questions/batch-move/', views.question_batch_move, name='question-batch-move'),

    # AI 处理
    path('courses/<int:course_id>/questions/ai-process/', views.question_ai_process, name='question-ai-process'),
    path('courses/<int:course_id>/questions/<int:question_id>/ai-confirm/', views.question_ai_confirm, name='question-ai-confirm'),

    # 变式题生成
    path('courses/<int:course_id>/questions/<int:question_id>/generate-variant/', views.question_generate_variant, name='question-generate-variant'),
    path('courses/<int:course_id>/questions/batch-generate-variant/', views.question_batch_generate_variant, name='question-batch-generate-variant'),

    # 变式题确认/驳回
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/confirm/', views.variant_task_confirm, name='variant-task-confirm'),
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/reject/', views.variant_task_reject, name='variant-task-reject'),
    path('courses/<int:course_id>/generate-mission/', views.generate_mission, name='generate-mission'),
]
