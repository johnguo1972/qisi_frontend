# Task 2 Fix Report

**Status:** DONE_WITH_CONCERNS

## 修复内容

### 1. 重复 URL 路径（Critical）
- `course_list` + `course_create` → 合并为 `course_list_or_create(request)` 处理 GET/POST
- `course_detail` + `course_update` + `course_delete` → 合并为 `course_detail_update_delete(request, course_id)` 处理 GET/PUT/DELETE
- `tree_list` + `tree_node_create` → 合并为 `tree_list_or_create(request, course_id)` 处理 GET/POST
- `tree_node_update` + `tree_node_delete` → 合并为 `tree_node_update_or_delete(request, course_id, node_id)` 处理 PUT/DELETE

### 2. 软删除课程可访问（Critical）
- `_get_course_or_404` 添加 `is_deleted=False` 过滤，已删除课程返回 404

### 3. CourseQuestionLink 硬删除（Bug）
- `tree_node_delete` 中 `.delete()` 改为 `.update(is_deleted=True)` 软删除

## 验证
- `python manage.py check` — 通过（0 issues）
- 无测试或模板引用旧 URL name 或旧视图函数名

## Concerns
- 前端如有硬编码 URL（如 `/api/courses/`），行为不变，无需修改
- 如有客户端通过 URL name 反向解析（`reverse('course-list')` 等），需要更新为新的 URL name（如 `course-list-create`）
- 建议运行端到端测试确认前端调用不受影响

## 修改文件
- `d:\workspace\code\qidi\front\apps\courses\urls.py`
- `d:\workspace\code\qidi\front\apps\courses\views.py`
