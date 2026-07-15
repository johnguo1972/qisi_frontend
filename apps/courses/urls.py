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
]
