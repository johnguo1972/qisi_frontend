# Task 1: Django App 脚手架 + 数据库模型 + 迁移

**位置**: `apps/courses/` 新建 Django app

## 要求

### 新建文件

1. `apps/courses/__init__.py` - 空文件 + `default_app_config`
2. `apps/courses/apps.py` - AppConfig
3. `apps/courses/models.py` - 5 个模型
4. `apps/courses/tests/__init__.py` - 空文件
5. `apps/courses/tests/test_models.py` - 模型测试

### 修改文件

1. `config/settings.py` - 添加 `'apps.courses'` 到 `INSTALLED_APPS`

### 模型定义

**Course** (db_table: 'course'):
- id, name(CharField 200), description(TextField null), subject(CharField 50), grade_level(CharField 50), cover_image(CharField 500 null), teacher(FK UserAccount PROTECT), is_deleted(Boolean False), created_at, updated_at

**CourseMaterial** (db_table: 'course_material'):
- id, course(FK Course CASCADE), name(CharField 255), file_path(CharField 500), file_type(CharField 20), file_size(BigIntegerField), mime_type(CharField 100), is_deleted(Boolean False), uploaded_by(FK UserAccount SET_NULL null), created_at

**CourseTree** (db_table: 'course_tree'):
- id, course(FK Course CASCADE), parent(FK self CASCADE null blank), name(CharField 200), sort_order(IntegerField 0), created_at
- ordering = ['sort_order']

**CourseQuestionLink** (db_table: 'course_question_link'):
- id, course(FK Course CASCADE), tree_node(FK CourseTree SET_NULL null blank), question(FK parser.ExamQuestion CASCADE), source(CharField 30, choices), source_course_name(CharField 200 null), is_deleted(Boolean False), created_at
- unique_together = ('course', 'question')

**VariantTask** (db_table: 'course_variant_task'):
- id, original_question(FK parser.ExamQuestion CASCADE), variant_mode(CharField 30), status(CharField 20, choices), generator_result(JSONField null), verifier_result(JSONField null), generated_question(JSONField null), error_message(TextField null), created_at, completed_at(DateTimeField null)

### 测试

6 个测试用例：
1. test_course_creation - 基本创建
2. test_course_soft_delete - 软删除
3. test_course_material_creation - 资料创建
4. test_course_tree_hierarchy - 树层级
5. test_course_question_link - 习题关联 + 唯一约束
6. test_variant_task_creation - 变式题任务创建

### 迁移

运行 `python manage.py makemigrations courses --name 0001_initial` 然后 `python manage.py migrate`

### 约束
- 仅修改 ./front 目录
- 数据库: PostgreSQL
- 复用 UserAccount (AUTH_USER_MODEL) 和 ExamQuestion (parser.ExamQuestion)
