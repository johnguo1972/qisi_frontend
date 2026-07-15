# Task 4: 习题管理 API

**位置**: 修改 `apps/courses/views.py` 和 `apps/courses/urls.py`

## 要求

在现有 views.py 和 urls.py 中追加以下端点：

### 习题管理

- GET `/api/v1/courses/<id>/questions/` — 课程习题列表（按 tree_node_id 筛选）
  - 返回格式：包含题目 id, system_id, question_no, question_type, stem_preview, difficulty, knowledge_points_count, review_status, ai_answer_a/b/c, source, tree_node_id
- POST `/api/v1/courses/<id>/questions/import/` — 从题库引入习题
  - 请求体：`{ "question_ids": [1,2,3], "tree_node_id": 5 }`
  - 跳过已存在的关联
- POST `/api/v1/courses/<id>/questions/batch-delete/` — 批量从课程移除（软删除 CourseQuestionLink）
- POST `/api/v1/courses/<id>/questions/batch-move/` — 批量移动所属节点
  - 请求体：`{ "question_ids": [1,2], "target_node_id": 5 }`

### AI 处理（复用现有 review API）

- POST `/api/v1/courses/<id>/questions/ai-process/` — AI处理
  - 委托给 `apps.review.views.ai_process_question`
- POST `/api/v1/courses/<id>/questions/<qid>/ai-confirm/` — AI答案确认
  - 委托给 `apps.review.views.ai_confirm_answer`

### 变式题生成

- POST `/api/v1/courses/<id>/questions/<qid>/generate-variant/` — 发起变式题任务
  - 检查题目 review_status == 'confirmed'
  - 调用 `generate_variant_task.delay(question_id, variant_mode, tree_node_id)`
- POST `/api/v1/courses/<id>/questions/batch-generate-variant/` — 批量生成
  - 调用 `batch_generate_variants_task.delay(question_ids, variant_mode, tree_node_id)`

### 变式题确认/驳回

- POST `/api/v1/courses/<id>/variant-tasks/<tid>/confirm/` — 确认变式题入库
- POST `/api/v1/courses/<id>/variant-tasks/<tid>/reject/` — 驳回变式题

## 约束
- 仅修改 ./front 目录
- 复用 `from apps.review.views import ai_process_question, ai_confirm_answer`
- 复用 `from apps.courses.tasks import generate_variant_task, batch_generate_variants_task`
- 所有端点使用 `@api_view` + `IsAuthenticated` + `_check_course_owner`
