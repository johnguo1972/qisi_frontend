# Task 2 Report: Serializers + API Views

**Status:** DONE

## Commit

- **SHA:** 5407211
- **Subject:** feat(courses): 添加课程管理序列化器、API视图和URL路由

## Summary

Django check 通过，14 个 API 端点创建完成。

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `apps/courses/serializers.py` | Created | 5 个序列化器 |
| `apps/courses/views.py` | Created | 14 个 API 视图函数 |
| `apps/courses/urls.py` | Created | URL 路由配置 |
| `config/urls.py` | Modified | 挂载 `path('api/v1/', include('apps.courses.urls'))` |

## Serializers (5)

1. **CourseSerializer** - 课程序列化，含 teacher_name, material_count, question_count, class_count (MethodField)，create 中自动设置 teacher
2. **CourseMaterialSerializer** - 资料序列化，含 uploaded_by_name
3. **CourseTreeNestedSerializer** - 嵌套树形序列化（children 递归）
4. **CourseTreeSerializer** - 扁平节点序列化（has_children 辅助字段）
5. **VariantTaskSerializer** - 变式任务序列化（只读）

## API Endpoints (14)

### 课程 CRUD (5)
| Method | Path | View | Description |
|--------|------|------|-------------|
| GET | `/api/v1/courses/` | course_list | 当前老师课程列表 |
| POST | `/api/v1/courses/` | course_create | 创建课程 |
| GET | `/api/v1/courses/<id>/` | course_detail | 课程详情 |
| PUT | `/api/v1/courses/<id>/` | course_update | 修改课程 |
| DELETE | `/api/v1/courses/<id>/` | course_delete | 软删除课程 |

### 课程资料 (5)
| Method | Path | View | Description |
|--------|------|------|-------------|
| GET | `/api/v1/courses/<id>/materials/` | material_list | 资料列表 |
| POST | `/api/v1/courses/<id>/materials/upload/` | material_upload | 上传文件（50MB限制，UUID文件名） |
| GET | `/api/v1/courses/<id>/materials/<mid>/download/` | material_download | 下载（FileResponse） |
| GET | `/api/v1/courses/<id>/materials/<mid>/preview/` | material_preview | 预览（图片直出，PDF/Word返回URL） |
| DELETE | `/api/v1/courses/<id>/materials/<mid>/` | material_delete | 软删除资料 |

### 目录树 (5)
| Method | Path | View | Description |
|--------|------|------|-------------|
| GET | `/api/v1/courses/<id>/tree/` | tree_list | 嵌套树形结构 |
| POST | `/api/v1/courses/<id>/tree/` | tree_node_create | 新增节点 |
| PUT | `/api/v1/courses/<id>/tree/<nid>/` | tree_node_update | 修改节点 |
| DELETE | `/api/v1/courses/<id>/tree/<nid>/` | tree_node_delete | 递归删除（先删CourseQuestionLink） |
| PUT | `/api/v1/courses/<id>/tree/<nid>/move/` | tree_node_move | 移动节点（改parent/sort_order） |

### 变式任务查询 (1)
| Method | Path | View | Description |
|--------|------|------|-------------|
| GET | `/api/v1/courses/<id>/variant-tasks/<tid>/` | variant_task_detail | 查询任务状态 |

## Permissions

- 所有端点使用 `@api_view` + `@permission_classes([IsAuthenticated])`
- 课程操作验证 `course.teacher == request.user`，否则 PermissionDenied
- 文件上传使用 UUID 文件名避免冲突
- 所有返回统一 `{'success': True/False, 'data': ..., 'message': ...}` 格式

## Concerns

无重大问题。注意点：
- `tree_node_delete` 递归删除时需要先清理关联的 `CourseQuestionLink`，已通过 `collect_descendants()` 递归收集所有子节点 ID 后统一删除
- `tree_node_update` 和 `tree_node_move` 均验证了父节点不能是自身且必须属于同一课程
- 文件上传端点检查了 50MB 大小限制，文件名使用 `uuid4().hex` 确保唯一性
