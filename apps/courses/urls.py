"""课程管理 URL 路由"""
from django.urls import path
from . import views

urlpatterns = [
    # 课程 CRUD
    path('courses/', views.course_list, name='course-list'),
    path('courses/', views.course_create, name='course-create'),
    path('courses/<int:course_id>/', views.course_detail, name='course-detail'),
    path('courses/<int:course_id>/', views.course_update, name='course-update'),
    path('courses/<int:course_id>/', views.course_delete, name='course-delete'),

    # 课程资料
    path('courses/<int:course_id>/materials/', views.material_list, name='material-list'),
    path('courses/<int:course_id>/materials/upload/', views.material_upload, name='material-upload'),
    path('courses/<int:course_id>/materials/<int:material_id>/download/', views.material_download, name='material-download'),
    path('courses/<int:course_id>/materials/<int:material_id>/preview/', views.material_preview, name='material-preview'),
    path('courses/<int:course_id>/materials/<int:material_id>/', views.material_delete, name='material-delete'),

    # 目录树
    path('courses/<int:course_id>/tree/', views.tree_list, name='tree-list'),
    path('courses/<int:course_id>/tree/', views.tree_node_create, name='tree-node-create'),
    path('courses/<int:course_id>/tree/<int:node_id>/', views.tree_node_update, name='tree-node-update'),
    path('courses/<int:course_id>/tree/<int:node_id>/', views.tree_node_delete, name='tree-node-delete'),
    path('courses/<int:course_id>/tree/<int:node_id>/move/', views.tree_node_move, name='tree-node-move'),

    # 变式任务查询
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/', views.variant_task_detail, name='variant-task-detail'),
]
