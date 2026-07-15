# Task 2: Serializers + API Views（课程管理 + 资料 + 目录树）

**位置**: `apps/courses/` 新增 serializers.py, views.py, urls.py

## 要求

### 新建文件

1. `apps/courses/serializers.py` - 5 个序列化器
2. `apps/courses/views.py` - REST API Views（课程 CRUD + 资料 + 目录树 + 变式任务查询）
3. `apps/courses/urls.py` - URL 路由

### 修改文件

1. `config/urls.py` - 挂载 `path('api/v1/', include('apps.courses.urls'))`

### Serializers

- `CourseSerializer`: 课程序列化，包含 teacher_name, material_count, question_count, class_count (MethodField)，create 中自动设置 request.user 为 teacher
- `CourseMaterialSerializer`: 资料序列化
- `CourseTreeSerializer`: 扁平节点序列化
- `CourseTreeNestedSerializer`: 嵌套树形序列化（children 递归）
- `VariantTaskSerializer`: 变式任务序列化（只读）

### API Views

**课程 CRUD**:
- GET /api/v1/courses/ - 当前老师的课程列表（is_deleted=False）
- POST /api/v1/courses/ - 创建课程
- GET /api/v1/courses/<id>/ - 课程详情
- PUT /api/v1/courses/<id>/ - 修改课程
- DELETE /api/v1/courses/<id>/ - 软删除（is_deleted=True）

**课程资料**:
- GET /api/v1/courses/<id>/materials/ - 资料列表（排除软删除）
- POST /api/v1/courses/<id>/materials/upload/ - 上传文件（50MB 限制，保存到 MEDIA_ROOT/courses/{id}/materials/）
- GET /api/v1/courses/<id>/materials/<mid>/download/ - 下载（FileResponse）
- GET /api/v1/courses/<id>/materials/<mid>/preview/ - 预览（图片直出，PDF/Word 返回 URL）
- DELETE /api/v1/courses/<id>/materials/<mid>/ - 软删除

**目录树**:
- GET /api/v1/courses/<id>/tree/ - 嵌套树形结构（根节点 parent=None）
- POST /api/v1/courses/<id>/tree/ - 新增节点
- PUT /api/v1/courses/<id>/tree/<nid>/ - 修改节点
- DELETE /api/v1/courses/<id>/tree/<nid>/ - 递归删除节点及子节点（先删除关联的 CourseQuestionLink）
- PUT /api/v1/courses/<id>/tree/<nid>/move/ - 移动节点（改 parent 或 sort_order）

**变式任务查询**:
- GET /api/v1/courses/<id>/variant-tasks/<tid>/ - 查询任务状态

### 权限
- 所有端点使用 `@api_view` + `IsAuthenticated`
- 课程操作需验证 `course.teacher == request.user`，否则 PermissionDenied
- 文件上传使用 `request.FILES['file']`，文件名用 UUID 避免冲突

### API 响应格式
所有返回 `{'success': True/False, 'data': ..., 'message': ...}`

### 约束
- 仅修改 ./front 目录
- 复用现有认证模式（参考 apps/review/views.py 中的 @api_view + IsAuthenticated）
- 文件保存到 settings.MEDIA_ROOT 目录
