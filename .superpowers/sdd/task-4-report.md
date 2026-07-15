# Task 4: 习题管理 API — 实现报告

## 状态: DONE

## 修改文件

1. `apps/courses/views.py` — 追加 11 个 API 端点视图函数
2. `apps/courses/urls.py` — 追加 11 条 URL 路由
3. `apps/courses/serializers.py` — 追加 `CourseQuestionLinkSerializer` 序列化器

## 新增端点清单

### 习题管理 (4)
| 方法 | 路径 | 视图函数 | 说明 |
|------|------|----------|------|
| GET | `/api/v1/courses/<id>/questions/` | `question_list` | 课程习题列表，支持 `?tree_node_id=` 筛选 |
| POST | `/api/v1/courses/<id>/questions/import/` | `question_import` | 从题库引入习题，跳过已存在关联 |
| POST | `/api/v1/courses/<id>/questions/batch-delete/` | `question_batch_delete` | 批量软删除 CourseQuestionLink |
| POST | `/api/v1/courses/<id>/questions/batch-move/` | `question_batch_move` | 批量移动习题所属树节点 |

### AI 处理 (2)
| 方法 | 路径 | 视图函数 | 说明 |
|------|------|----------|------|
| POST | `/api/v1/courses/<id>/questions/ai-process/` | `question_ai_process` | 复用 `apps.review.tasks.single_ai_process_question` |
| POST | `/api/v1/courses/<id>/questions/<qid>/ai-confirm/` | `question_ai_confirm` | 委托给 `apps.review.views.ai_confirm_answer` |

### 变式题生成 (2)
| 方法 | 路径 | 视图函数 | 说明 |
|------|------|----------|------|
| POST | `/api/v1/courses/<id>/questions/<qid>/generate-variant/` | `question_generate_variant` | 检查 review_status='confirmed' 后调用 Celery 任务 |
| POST | `/api/v1/courses/<id>/questions/batch-generate-variant/` | `question_batch_generate_variant` | 批量分发独立的 generate_variant_task |

### 变式题确认/驳回 (2)
| 方法 | 路径 | 视图函数 | 说明 |
|------|------|----------|------|
| POST | `/api/v1/courses/<id>/variant-tasks/<tid>/confirm/` | `variant_task_confirm` | 更新 ExamQuestion.review_status 为 confirmed |
| POST | `/api/v1/courses/<id>/variant-tasks/<tid>/reject/` | `variant_task_reject` | 更新 VariantTask 状态为 failed |

## 设计决策

1. **复用 review 模块**: `ai-process` 和 `ai-confirm` 端点复用 `apps.review` 中的 Serializer 和 Celery task，不重复实现
2. **权限校验**: 所有端点使用 `@api_view` + `IsAuthenticated` + `_check_course_owner` 三重校验
3. **变式题归属查询**: `variant_task_confirm/reject` 使用 `original_question__course_links__course=course` 关联查询，确保任务归属验证
4. **确认逻辑**: Celery 任务已保存 ExamQuestion (review_status='need_review')，confirm 只需更新状态为 'confirmed'
5. **软删除一致性**: 批量删除使用 `is_deleted=True` 软删除，与现有资料/课程删除模式一致

## 验证

- `python manage.py check` 通过，0 错误
- 所有端点遵循现有代码风格（`{'success': True, 'data': ...}` 响应格式）
- 所有端点使用相同的 `_check_course_owner` 权限辅助函数
