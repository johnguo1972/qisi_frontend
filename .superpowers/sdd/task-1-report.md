# Task 1 Report: Django App 脚手架 + 数据库模型 + 迁移

## Status: DONE

## Commit

```
b50afd9 feat(courses): 创建 courses Django app + 5 个模型 + 迁移
```

Branch: `feature/task-1-courses-app`

## 创建的文件

| 文件 | 说明 |
|------|------|
| `apps/courses/__init__.py` | 空文件 |
| `apps/courses/apps.py` | AppConfig (verbose_name: 课程管理) |
| `apps/courses/models.py` | 5 个数据模型 |
| `apps/courses/migrations/0001_initial.py` | 初始迁移 |
| `apps/courses/migrations/__init__.py` | 空文件 |
| `apps/courses/tests/__init__.py` | 空文件 |
| `apps/courses/tests/test_models.py` | 7 个单元测试 |

## 修改的文件

| 文件 | 说明 |
|------|------|
| `config/settings.py` | 添加 `'apps.courses'` 到 INSTALLED_APPS |

## 模型清单

1. **Course** (db_table: `course`) — 课程基本信息，关联教师 (PROTECT)，软删除标记
2. **CourseMaterial** (db_table: `course_material`) — 课程资料，级联删除课程，上传者 SET_NULL
3. **CourseTree** (db_table: `course_tree`) — 课程树节点，自引用 parent，按 sort_order 排序
4. **CourseQuestionLink** (db_table: `course_question_link`) — 课程与题库习题关联，unique_together (course, question)
5. **VariantTask** (db_table: `course_variant_task`) — 变式题生成任务，JSON 字段存储生成/校验结果

## 测试摘要

7 个测试全部通过：
- `test_course_creation` — 课程基本创建
- `test_course_soft_delete` — 软删除标记
- `test_course_material_creation` — 资料创建
- `test_course_tree_hierarchy` — 树层级关系
- `test_course_question_link` — 习题关联
- `test_course_question_link_unique_together` — 唯一约束
- `test_variant_task_creation` — 变式题任务创建

## 遇到的问题

1. **ExamPaper.grade_level 字段不存在** — 实际字段名为 `grade`，测试已修正
2. **测试数据库 stale** — 手动删除 test_qisi_ai_tutor 后恢复
3. **makemigrations --name 参数** — Django 不接受带连字符的名称，自动生成 `0001_initial.py` 符合规范

## 注意事项

- 数据库为 PostgreSQL，迁移已应用到生产数据库
- 遵循了现有 apps 的命名模式和代码风格
- `AUTH_USER_MODEL` 用于教师外键，`'parser.ExamQuestion'` 用于习题外键
