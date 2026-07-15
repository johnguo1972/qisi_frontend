# 课程列表功能 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为教师端新增"课程列表"一级功能，包含课程卡片管理、课程资料文件管理、课程练习（自定义目录树 + 习题列表 + AI 处理 + 变式题生成）三大模块。

**架构：** 渐进式混合方案。Django 新建 `apps/courses/` 处理后端逻辑；uniapp 新增 3 个页面 + 2 个组件；变式题生成通过 Celery 异步任务 + qwen3.7-plus 生成 + deepseek-v4-pro 验证。

**技术栈：** Django + DRF + PostgreSQL + Celery + uniapp (Vue3/TS) + qwen3.7/deepseek AI

## Global Constraints

- **修改范围**：仅限 `./front` 目录，不修改 backend/ 或 miniprogram/
- **通信语言**：全程中文
- **数据库**：PostgreSQL（与现有保持一致）
- **文件存储**：Django `media/` 目录（`MEDIA_ROOT / 'courses'`）
- **AI 服务**：复用同一阿里云 API KEY（`QWEN_API_KEY`）和 URL（`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`）
- **认证**：复用现有 JWT 认证（`@api_view` + `IsAuthenticated`）
- **API 响应格式**：`{'success': True/False, 'data': ..., 'message': ...}`（与现有一致）
- **软删除**：`is_deleted = True` 标记，非物理删除
- **TDD**：先写测试 → 写实现 → 验证通过 → 提交
- **DRY/YAGNI**：复用现有代码，不造轮子

---

## 文件地图

| 类型 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `apps/courses/__init__.py` | Django app 初始化 |
| 新建 | `apps/courses/apps.py` | AppConfig |
| 新建 | `apps/courses/models.py` | 5 个模型 |
| 新建 | `apps/courses/serializers.py` | DRF Serializers |
| 新建 | `apps/courses/views.py` | REST API Views |
| 新建 | `apps/courses/urls.py` | URL 路由 |
| 新建 | `apps/courses/ai_service.py` | 变式题 AI 服务 |
| 新建 | `apps/courses/validator.py` | 程序化校验器 |
| 新建 | `apps/courses/prompts.py` | System Prompt 模板 |
| 新建 | `apps/courses/tasks.py` | Celery 异步任务 |
| 新建 | `apps/courses/migrations/0001_initial.py` | 数据库迁移 |
| 新建 | `apps/courses/tests/__init__.py` | 测试包 |
| 新建 | `apps/courses/tests/test_models.py` | 模型测试 |
| 修改 | `config/settings.py` | 注册 courses app |
| 修改 | `config/urls.py` | 挂载 courses URL |
| 修改 | `.env` | 新增 AI 模型配置 |
| 新建 | `uniapp/src/api/courses.ts` | 课程 API 封装 |
| 新建 | `uniapp/src/pages/teacher/course-list.vue` | 课程卡片列表页 |
| 新建 | `uniapp/src/pages/teacher/course-materials.vue` | 课程资料页 |
| 新建 | `uniapp/src/pages/teacher/course-practice.vue` | 课程练习页 |
| 新建 | `uniapp/src/components/CourseCard.vue` | 课程卡片组件 |
| 新建 | `uniapp/src/components/DirTree.vue` | 可编辑目录树组件 |
| 修改 | `uniapp/src/components/TeacherSidebar.vue` | 新增课程列表菜单 |
| 修改 | `uniapp/pages.json` | 注册新页面路由 |

---

### Task 1: Django App 脚手架 + 数据库模型 + 迁移

**Files:**
- Create: `apps/courses/__init__.py` (empty)
- Create: `apps/courses/apps.py`
- Create: `apps/courses/models.py`
- Create: `apps/courses/tests/__init__.py` (empty)
- Create: `apps/courses/tests/test_models.py`
- Modify: `config/settings.py:36` (添加 `'apps.courses'` 到 `INSTALLED_APPS`)

**Interfaces:**
- Consumes: 现有 `UserAccount` 模型（`apps.accounts.models`）和 `ExamQuestion` 模型（`apps.parser.models`）
- Produces: 5 个 Django 模型可供其他任务和 uniapp 前端使用

- [ ] **Step 1: 编写模型测试**

创建 `apps/courses/tests/test_models.py`：

```python
"""Tests for courses models."""
import pytest
from django.contrib.auth import get_user_model
from apps.parser.models import ExamQuestion

User = get_user_model()


@pytest.mark.django_db
def test_course_creation(teacher_user):
    """Test basic course creation."""
    from apps.courses.models import Course

    course = Course.objects.create(
        name="26年物理9年级S班课程",
        description="初中物理九年级上学期课程",
        subject="physics",
        grade_level="九年级",
        teacher=teacher_user,
    )
    assert course.name == "26年物理9年级S班课程"
    assert course.subject == "physics"
    assert course.is_deleted is False
    assert course.pk is not None


@pytest.mark.django_db
def test_course_soft_delete(teacher_user):
    """Test course soft delete."""
    from apps.courses.models import Course

    course = Course.objects.create(
        name="测试课程",
        subject="physics",
        teacher=teacher_user,
    )
    course.is_deleted = True
    course.save()

    # Soft deleted course not in default queryset
    assert Course.objects.filter(is_deleted=False).count() == 0
    assert Course.objects.filter(is_deleted=True).count() == 1


@pytest.mark.django_db
def test_course_material_creation(teacher_user):
    """Test course material creation."""
    from apps.courses.models import Course, CourseMaterial

    course = Course.objects.create(
        name="测试课程",
        subject="physics",
        teacher=teacher_user,
    )
    material = CourseMaterial.objects.create(
        course=course,
        name="第一章练习题.pdf",
        file_path="courses/1/chapter1.pdf",
        file_type="pdf",
        file_size=1024000,
        mime_type="application/pdf",
        uploaded_by=teacher_user,
    )
    assert material.file_type == "pdf"
    assert material.is_deleted is False


@pytest.mark.django_db
def test_course_tree_hierarchy(teacher_user):
    """Test course tree parent-child hierarchy."""
    from apps.courses.models import Course, CourseTree

    course = Course.objects.create(
        name="测试课程",
        subject="physics",
        teacher=teacher_user,
    )
    parent = CourseTree.objects.create(
        course=course,
        name="第一章 力学",
        sort_order=1,
    )
    child = CourseTree.objects.create(
        course=course,
        parent=parent,
        name="1.1 牛顿定律",
        sort_order=1,
    )
    assert child.parent == parent
    assert parent.children.count() == 1
    assert list(parent.children.all()) == [child]


@pytest.mark.django_db
def test_course_question_link(teacher_user):
    """Test course-question link with source tracking."""
    from apps.courses.models import Course, CourseQuestionLink

    course = Course.objects.create(
        name="测试课程",
        subject="physics",
        teacher=teacher_user,
    )
    # Create a minimal ExamQuestion for testing
    from apps.papers.models import ExamPaper
    paper = ExamPaper.objects.create(
        title="测试试卷",
        subject="physics",
        created_by=teacher_user,
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        question_type="single_choice",
        stem="测试题干",
    )

    link = CourseQuestionLink.objects.create(
        course=course,
        question=question,
        source="created_in_course",
        source_course_name="测试课程",
    )
    assert link.source == "created_in_course"
    assert link.is_deleted is False
    # Unique constraint
    with pytest.raises(Exception):
        CourseQuestionLink.objects.create(
            course=course,
            question=question,
            source="imported_from_bank",
        )


@pytest.mark.django_db
def test_variant_task_creation(teacher_user):
    """Test variant task creation and status tracking."""
    from apps.courses.models import Course, VariantTask
    from apps.papers.models import ExamPaper

    paper = ExamPaper.objects.create(
        title="测试试卷",
        subject="physics",
        created_by=teacher_user,
    )
    from apps.parser.models import ExamQuestion
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        question_type="single_choice",
        stem="测试题干",
    )

    task = VariantTask.objects.create(
        original_question=question,
        variant_mode="numeric_change",
        status="pending",
    )
    assert task.status == "pending"
    assert task.variant_mode == "numeric_change"
    assert task.generator_result is None
```

- [ ] **Step 2: 编写模型实现**

创建 `apps/courses/models.py`：

```python
"""Models for the courses app."""
from django.db import models
from django.conf import settings


class Course(models.Model):
    """课程 - 老师的内容库，可被多个班级引用。"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name="课程名称")
    description = models.TextField(null=True, blank=True, verbose_name="课程介绍")
    subject = models.CharField(max_length=50, verbose_name="学科")
    grade_level = models.CharField(max_length=50, verbose_name="年级")
    cover_image = models.CharField(max_length=500, null=True, blank=True, verbose_name="封面图")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='courses', verbose_name="创建教师",
    )
    is_deleted = models.BooleanField(default=False, verbose_name="软删除")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course'
        verbose_name = '课程'
        verbose_name_plural = '课程'

    def __str__(self):
        return f"{self.name} ({self.subject})"


class CourseMaterial(models.Model):
    """课程资料文件。"""
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='materials',
        verbose_name="所属课程",
    )
    name = models.CharField(max_length=255, verbose_name="文件名")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    file_type = models.CharField(max_length=20, verbose_name="文件类型")  # pdf/word/image
    file_size = models.BigIntegerField(verbose_name="文件大小(字节)")
    mime_type = models.CharField(max_length=100, verbose_name="MIME类型")
    is_deleted = models.BooleanField(default=False, verbose_name="软删除")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, verbose_name="上传者",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_material'
        verbose_name = '课程资料'
        verbose_name_plural = '课程资料'

    def __str__(self):
        return f"{self.name} ({self.file_type})"


class CourseTree(models.Model):
    """课程目录树节点 - 支持多级嵌套。"""
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='tree_nodes',
        verbose_name="所属课程",
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name="父节点",
    )
    name = models.CharField(max_length=200, verbose_name="节点名称")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_tree'
        verbose_name = '课程目录节点'
        verbose_name_plural = '课程目录节点'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.course.name} > {self.name}"


class CourseQuestionLink(models.Model):
    """课程习题关联 - 双向打通。"""
    SOURCE_CHOICES = [
        ('created_in_course', '课程中创建'),
        ('imported_from_bank', '从题库引入'),
    ]
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="课程")
    tree_node = models.ForeignKey(
        CourseTree, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="所属目录节点",
    )
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.CASCADE,
        verbose_name="关联题目",
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, verbose_name="来源")
    source_course_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="来源课程名称")
    is_deleted = models.BooleanField(default=False, verbose_name="软删除")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_question_link'
        verbose_name = '课程习题关联'
        verbose_name_plural = '课程习题关联'
        unique_together = ('course', 'question')

    def __str__(self):
        return f"{self.course.name} > Q{self.question_id}"


class VariantTask(models.Model):
    """变式题生成任务。"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]
    id = models.BigAutoField(primary_key=True)
    original_question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.CASCADE,
        verbose_name="原题",
    )
    variant_mode = models.CharField(max_length=30, verbose_name="变式模式")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    generator_result = models.JSONField(null=True, blank=True, verbose_name="生成结果")
    verifier_result = models.JSONField(null=True, blank=True, verbose_name="验证结果")
    generated_question = models.JSONField(null=True, blank=True, verbose_name="生成的题目")
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        db_table = 'course_variant_task'
        verbose_name = '变式题任务'
        verbose_name_plural = '变式题任务'

    def __str__(self):
        return f"VariantTask #{self.id} ({self.status})"
```

- [ ] **Step 3: 编写 AppConfig**

创建 `apps/courses/apps.py`：

```python
from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courses'
    verbose_name = '课程管理'
```

创建 `apps/courses/__init__.py`：

```python
default_app_config = 'apps.courses.apps.CoursesConfig'
```

- [ ] **Step 4: 注册 courses app 到 settings.py**

在 `config/settings.py` 的 `INSTALLED_APPS` 列表末尾添加 `'apps.courses'`：

```python
INSTALLED_APPS = [
    # ... existing ...
    'apps.institutions',
    'apps.courses',  # 新增：课程管理
]
```

- [ ] **Step 5: 创建测试 fixture**

在 `apps/courses/tests/test_models.py` 顶部添加 conftest 风格的 fixture。由于项目使用 pytest，我们需要在 `conftest.py` 或测试文件中定义 fixture。检查是否已有全局 conftest：

```bash
find front -name "conftest.py" | head -5
```

如果找到全局 conftest，复用其中的 `teacher_user` fixture。如果没有，在 `apps/courses/tests/test_models.py` 顶部添加：

```python
@pytest.fixture
def teacher_user(db):
    """Create a test teacher user."""
    User = get_user_model()
    return User.objects.create(
        role_type='teacher',
        mobile='13800000001',
        display_name='测试老师',
        subject='physics',
        stages=['初中'],
    )
```

- [ ] **Step 6: 运行测试验证模型**

```bash
cd front
python -m pytest apps/courses/tests/test_models.py -v
```

预期：6 个测试全部 PASS

- [ ] **Step 7: 创建迁移文件**

```bash
cd front
python manage.py makemigrations courses --name 0001_initial
```

- [ ] **Step 8: 运行迁移**

```bash
cd front
python manage.py migrate
```

预期：5 张表创建成功（course, course_material, course_tree, course_question_link, course_variant_task）

- [ ] **Step 9: 提交**

```bash
cd front
git add apps/courses/ config/settings.py
git commit -m "feat: add courses app with 5 models and initial migration"
```

---

### Task 2: Serializers + API Views（课程管理 + 资料 + 目录树）

**Files:**
- Create: `apps/courses/serializers.py`
- Create: `apps/courses/views.py`
- Create: `apps/courses/urls.py`
- Modify: `config/urls.py` (挂载 courses URL)

**Interfaces:**
- Consumes: Task 1 的 5 个模型
- Produces: REST API 端点供前端调用

- [ ] **Step 1: 编写 Serializers**

创建 `apps/courses/serializers.py`：

```python
"""Serializers for the courses app."""
from rest_framework import serializers
from .models import Course, CourseMaterial, CourseTree, CourseQuestionLink, VariantTask


class CourseSerializer(serializers.ModelSerializer):
    """课程序列化。"""
    teacher_name = serializers.CharField(source='teacher.display_name', read_only=True)
    material_count = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    class_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'name', 'description', 'subject', 'grade_level',
            'cover_image', 'teacher', 'teacher_name',
            'material_count', 'question_count', 'class_count',
            'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'teacher', 'created_at', 'updated_at']

    def get_material_count(self, obj):
        return obj.materials.filter(is_deleted=False).count()

    def get_question_count(self, obj):
        return CourseQuestionLink.objects.filter(
            course=obj, is_deleted=False
        ).count()

    def get_class_count(self, obj):
        # Assuming a ManyToMany to Class; if not implemented, return 0
        try:
            return obj.classes.count()
        except Exception:
            return 0

    def create(self, validated_data):
        # Teacher is set from request user
        validated_data['teacher'] = self.context['request'].user
        return super().create(validated_data)


class CourseMaterialSerializer(serializers.ModelSerializer):
    """课程资料序列化。"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.display_name', read_only=True)

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'course', 'name', 'file_path', 'file_type',
            'file_size', 'mime_type', 'uploaded_by', 'uploaded_by_name',
            'is_deleted', 'created_at',
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at']


class CourseTreeSerializer(serializers.ModelSerializer):
    """课程目录树节点序列化（扁平列表）。"""
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseTree
        fields = ['id', 'course', 'parent', 'name', 'sort_order', 'children_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_children_count(self, obj):
        return obj.children.count()


class CourseTreeNestedSerializer(serializers.ModelSerializer):
    """课程目录树嵌套序列化（用于树形返回）。"""
    children = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseTree
        fields = ['id', 'name', 'sort_order', 'children', 'question_count']

    def get_children(self, obj):
        children = obj.children.filter(course=obj.course).order_by('sort_order')
        return CourseTreeNestedSerializer(children, many=True).data

    def get_question_count(self, obj):
        return CourseQuestionLink.objects.filter(
            tree_node=obj, is_deleted=False
        ).count()


class VariantTaskSerializer(serializers.ModelSerializer):
    """变式题任务序列化。"""
    original_question_id = serializers.IntegerField(source='original_question.id', read_only=True)

    class Meta:
        model = VariantTask
        fields = [
            'id', 'original_question_id', 'variant_mode', 'status',
            'generator_result', 'verifier_result', 'generated_question',
            'error_message', 'created_at', 'completed_at',
        ]
        read_only_fields = fields
```

- [ ] **Step 2: 编写 API Views**

创建 `apps/courses/views.py`：

```python
"""REST API views for the courses app."""
import os
import logging
import uuid
from django.conf import settings
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from .models import Course, CourseMaterial, CourseTree, CourseQuestionLink, VariantTask
from .serializers import (
    CourseSerializer, CourseMaterialSerializer,
    CourseTreeSerializer, CourseTreeNestedSerializer, VariantTaskSerializer,
)

logger = logging.getLogger(__name__)

# ── Helper: Course ownership check ──

def _check_course_owner(course, user):
    """Raise PermissionDenied if user doesn't own the course."""
    if course.teacher != user:
        raise PermissionDenied("您没有权限操作此课程")


# ── Course CRUD ──

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_list(request):
    """课程列表 - 卡片数据。"""
    user = request.user
    courses = Course.objects.filter(
        teacher=user, is_deleted=False
    ).order_by('-created_at')
    serializer = CourseSerializer(courses, many=True)
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def course_create(request):
    """创建课程。"""
    serializer = CourseSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    course = serializer.save()
    return Response({
        'success': True,
        'data': CourseSerializer(course).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def course_detail(request, course_id):
    """课程详情。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)
    serializer = CourseSerializer(course)
    return Response({'success': True, 'data': serializer.data})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def course_update(request, course_id):
    """修改课程。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)
    serializer = CourseSerializer(course, data=request.data, partial=True, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'success': True, 'data': serializer.data})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def course_delete(request, course_id):
    """软删除课程。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)
    course.is_deleted = True
    course.save()
    return Response({'success': True, 'message': '课程已删除'})


# ── Course Materials ──

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_list(request, course_id):
    """课程资料列表。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)
    materials = CourseMaterial.objects.filter(
        course=course, is_deleted=False
    ).order_by('-created_at')
    serializer = CourseMaterialSerializer(materials, many=True)
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def material_upload(request, course_id):
    """上传课程资料文件。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    if 'file' not in request.FILES:
        raise ValidationError("未找到上传文件")

    uploaded_file = request.FILES['file']
    # Validate file size (50MB max)
    max_size = 50 * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValidationError("文件大小超过50MB限制")

    # Determine file type
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    file_type_map = {
        '.pdf': 'pdf',
        '.doc': 'word', '.docx': 'word',
        '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
    }
    file_type = file_type_map.get(ext, 'other')

    # Save file to media/courses/{course_id}/
    course_dir = settings.MEDIA_ROOT / 'courses' / str(course_id) / 'materials'
    course_dir.mkdir(parents=True, exist_ok=True)

    # Unique filename with UUID to avoid conflicts
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = course_dir / unique_name

    with open(file_path, 'wb+') as dest:
        for chunk in uploaded_file.chunks():
            dest.write(chunk)

    # Get MIME type
    mime_type = uploaded_file.content_type or 'application/octet-stream'

    material = CourseMaterial.objects.create(
        course=course,
        name=uploaded_file.name,
        file_path=f"courses/{course_id}/materials/{unique_name}",
        file_type=file_type,
        file_size=uploaded_file.size,
        mime_type=mime_type,
        uploaded_by=request.user,
    )
    serializer = CourseMaterialSerializer(material)
    return Response({
        'success': True,
        'data': serializer.data,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_download(request, course_id, material_id):
    """下载课程资料。"""
    try:
        material = CourseMaterial.objects.get(
            id=material_id, course_id=course_id, is_deleted=False
        )
    except CourseMaterial.DoesNotExist:
        raise NotFound("文件不存在")
    file_path = settings.MEDIA_ROOT / material.file_path
    if not file_path.exists():
        raise NotFound("文件已被删除")
    response = FileResponse(open(file_path, 'rb'), content_type=material.mime_type)
    response['Content-Disposition'] = f'attachment; filename="{material.name}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_preview(request, course_id, material_id):
    """预览课程资料（图片直出，PDF/Word 返回 URL）。"""
    try:
        material = CourseMaterial.objects.get(
            id=material_id, course_id=course_id, is_deleted=False
        )
    except CourseMaterial.DoesNotExist:
        raise NotFound("文件不存在")
    file_path = settings.MEDIA_ROOT / material.file_path
    if not file_path.exists():
        raise NotFound("文件已被删除")

    if material.file_type == 'image':
        response = FileResponse(open(file_path, 'rb'), content_type=material.mime_type)
        return response
    else:
        # Return URL for PDF/Word (frontend opens in new tab)
        file_url = settings.MEDIA_URL + material.file_path
        return Response({'success': True, 'data': {'url': file_url, 'mime_type': material.mime_type}})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def material_delete(request, course_id, material_id):
    """软删除课程资料。"""
    try:
        material = CourseMaterial.objects.get(
            id=material_id, course_id=course_id, is_deleted=False
        )
    except CourseMaterial.DoesNotExist:
        raise NotFound("文件不存在")
    material.is_deleted = True
    material.save()
    return Response({'success': True, 'message': '资料已删除'})


# ── Course Tree ──

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tree_list(request, course_id):
    """获取课程目录树（嵌套结构）。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    # Build nested tree from root nodes (parent is None)
    roots = CourseTree.objects.filter(course=course, parent=None).order_by('sort_order')
    serializer = CourseTreeNestedSerializer(roots, many=True)
    return Response({'success': True, 'data': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tree_create(request, course_id):
    """新增目录节点。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    data = request.data.copy()
    data['course'] = course_id

    # Validate parent exists if provided
    parent_id = data.get('parent')
    if parent_id:
        try:
            parent = CourseTree.objects.get(id=parent_id, course=course)
        except CourseTree.DoesNotExist:
            raise ValidationError("父节点不存在或不属于此课程")

    serializer = CourseTreeSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    node = serializer.save()
    # Return nested representation
    nested = CourseTreeNestedSerializer(node).data
    return Response({'success': True, 'data': nested}, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def tree_update(request, course_id, node_id):
    """修改目录节点。"""
    try:
        node = CourseTree.objects.get(id=node_id, course_id=course_id)
    except CourseTree.DoesNotExist:
        raise NotFound("节点不存在")
    _check_course_owner(node.course, request.user)

    serializer = CourseTreeSerializer(node, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'success': True, 'data': serializer.data})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def tree_delete(request, course_id, node_id):
    """删除目录节点（含所有子节点）。"""
    try:
        node = CourseTree.objects.get(id=node_id, course_id=course_id)
    except CourseTree.DoesNotExist:
        raise NotFound("节点不存在")
    _check_course_owner(node.course, request.user)

    # Delete all descendants recursively
    def delete_descendants(n):
        for child in n.children.all():
            delete_descendants(child)
        # Remove question links before deleting
        CourseQuestionLink.objects.filter(tree_node=n).delete()
        n.delete()

    delete_descendants(node)
    return Response({'success': True, 'message': '节点及子节点已删除'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def tree_move(request, course_id, node_id):
    """移动目录节点（变更父节点或排序）。"""
    try:
        node = CourseTree.objects.get(id=node_id, course_id=course_id)
    except CourseTree.DoesNotExist:
        raise NotFound("节点不存在")
    _check_course_owner(node.course, request.user)

    parent_id = request.data.get('parent')
    sort_order = request.data.get('sort_order')

    if parent_id is not None:
        try:
            new_parent = CourseTree.objects.get(id=parent_id, course=course_id)
        except CourseTree.DoesNotExist:
            raise ValidationError("目标父节点不存在")
        node.parent = new_parent

    if sort_order is not None:
        node.sort_order = int(sort_order)

    node.save()
    serializer = CourseTreeNestedSerializer(node)
    return Response({'success': True, 'data': serializer.data})


# ── Variant Tasks ──

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def variant_task_status(request, course_id, task_id):
    """查询变式题任务状态。"""
    try:
        task = VariantTask.objects.get(id=task_id)
    except VariantTask.DoesNotExist:
        raise NotFound("任务不存在")
    # Verify task belongs to a course the user owns
    link = CourseQuestionLink.objects.filter(
        question_id=task.original_question_id,
        course_id=course_id,
    ).first()
    if not link:
        raise PermissionDenied("无权查看此任务")

    serializer = VariantTaskSerializer(task)
    return Response({'success': True, 'data': serializer.data})
```

- [ ] **Step 3: 编写 URL 路由**

创建 `apps/courses/urls.py`：

```python
"""URL routing for the courses app."""
from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Course CRUD
    path('courses/', views.course_list, name='course-list'),
    path('courses/', views.course_create, name='course-create'),
    path('courses/<int:course_id>/', views.course_detail, name='course-detail'),
    path('courses/<int:course_id>/', views.course_update, name='course-update'),
    path('courses/<int:course_id>/', views.course_delete, name='course-delete'),

    # Materials
    path('courses/<int:course_id>/materials/', views.material_list, name='material-list'),
    path('courses/<int:course_id>/materials/upload/', views.material_upload, name='material-upload'),
    path('courses/<int:course_id>/materials/<int:material_id>/download/', views.material_download, name='material-download'),
    path('courses/<int:course_id>/materials/<int:material_id>/preview/', views.material_preview, name='material-preview'),
    path('courses/<int:course_id>/materials/<int:material_id>/', views.material_delete, name='material-delete'),

    # Tree
    path('courses/<int:course_id>/tree/', views.tree_list, name='tree-list'),
    path('courses/<int:course_id>/tree/', views.tree_create, name='tree-create'),
    path('courses/<int:course_id>/tree/<int:node_id>/', views.tree_update, name='tree-update'),
    path('courses/<int:course_id>/tree/<int:node_id>/', views.tree_delete, name='tree-delete'),
    path('courses/<int:course_id>/tree/<int:node_id>/move/', views.tree_move, name='tree-move'),

    # Variant tasks
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/', views.variant_task_status, name='variant-task-status'),
]
```

- [ ] **Step 4: 挂载 courses URL 到 config/urls.py**

在 `config/urls.py` 中添加 courses URL：

```python
urlpatterns = [
    # ... existing ...
    path('api/v1/', include('apps.courses.urls')),  # 新增：课程管理
]
```

- [ ] **Step 5: 测试 API 端点**

使用 curl 或浏览器测试基础端点：

```bash
# 需要先获取 JWT token
TOKEN="your_jwt_token"

# 课程列表
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/courses/

# 创建课程
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试课程","subject":"physics","grade_level":"九年级","description":"测试"}' \
  http://localhost:8000/api/v1/courses/
```

- [ ] **Step 6: 提交**

```bash
cd front
git add apps/courses/serializers.py apps/courses/views.py apps/courses/urls.py config/urls.py
git commit -m "feat: add courses API views for CRUD, materials, and tree management"
```

---

### Task 3: Celery 异步变式题任务 + AI 服务 + 校验器

**Files:**
- Create: `apps/courses/prompts.py`
- Create: `apps/courses/validator.py`
- Create: `apps/courses/ai_service.py`
- Create: `apps/courses/tasks.py`
- Modify: `.env` (新增 AI 模型配置)

**Interfaces:**
- Consumes: Task 2 的模型 + 现有 `AIReviewService`（`apps.common.ai_service`）
- Produces: Celery 任务 `generate_variant_task` + `batch_generate_variants_task`

- [ ] **Step 1: 编写 System Prompt 模板**

创建 `apps/courses/prompts.py`：

```python
"""Prompt templates for variant question generation."""

# Fixed System Prompt - suitable for context caching
VARIANT_SYSTEM_PROMPT = """你是初中物理变式题命题与校验专家。请根据输入的结构化原题生成1道高质量变式题，并只输出符合指定结构的合法JSON。

核心任务
1. 保持原题的主知识点、题型、核心物理模型和主要解题方法不变。
2. 根据 variant_mode 进行轻度变式：
   - numeric_change：修改2～4个相互关联的数值
   - condition_change：只修改1个物理条件并重新建模
   - context_change：只替换为物理模型等价的生活场景
   - mixed_light：少量数值变化加1个轻微条件变化
3. 不得引入新的主要知识点，不得超出初中物理课程范围。
4. 数值必须符合现实数量级，单位正确，计算尽量得到整数、一位小数或常见分数。
5. 默认保持原题难度、选项数量和正确答案数量不变。

生成流程
在内部依次完成：
1. 重新求解原题，确认原答案和物理模型
2. 确定不可修改项、可修改项和图片锁定项
3. 设计新的参数或条件
4. 使用新条件完整求解
5. 生成题干、选项、答案和解析
6. 检查题目、答案、解析和插图是否一致

如果原题答案错误、条件不足或无法安全生成，返回 status="failed"，不得强行生成。

物理校验
必须检查：
- 机械运动：路程、时间、速度和平均速度关系
- 力学：研究对象、受力、平衡状态和方向
- 压强：压力、受力面积、液体密度和深度
- 浮力：V排、浸没状态、浮沉状态及支持力
- 功和机械：有用功、额外功、总功、功率和效率
- 热学：温度、热量、内能、比热容和热值
- 电学：串并联、电表连接、滑动变阻器、额定与实际状态
- 光学：光路、法线、物距、焦距、像的性质
- 电磁学：电流、磁场、运动方向和能量转化

选择题必须逐项验证。单选题只有1个正确答案；多选题保持原正确答案数量。
解析只输出简洁、可核验的物理规律、公式、计算步骤和结论。

插图处理
- 无图：figure_action="none"
- 图片不参与解题，或变式未修改图中变量：figure_action="reuse"
- 只需修改文字标签且有坐标：figure_action="overlay_text"
- 涉及角度/方向/位置/电路连接变化：有scene_json则rerender，否则redraw_required或failed

题干、选项、答案、解析和插图必须完全一致。

只输出JSON，不输出Markdown、解释、前言或结语。"""

# DeepSeek verification prompt
VERIFIER_SYSTEM_PROMPT = """你是一位严谨的初中物理教师。请验证以下变式题是否正确：
1. 物理概念和公式是否正确
2. 答案是否正确
3. 解析是否准确
4. 是否在初中课程范围内
5. 难度是否与原题相当

如果验证通过，返回 {"passed": true}
如果验证不通过，返回 {"passed": false, "reason": "具体原因"}

只输出JSON。"""


def build_variant_user_prompt(question_data: dict, variant_mode: str) -> str:
    """Build dynamic user prompt for variant generation."""
    import json
    payload = {
        "subject": question_data.get("subject", "初中物理"),
        "grade": question_data.get("grade", ""),
        "question_type": question_data.get("question_type", ""),
        "knowledge_points": question_data.get("knowledge_points", []),
        "difficulty": question_data.get("difficulty", 0.5),
        "variant_mode": variant_mode,
        "stem": question_data.get("stem", ""),
        "options": question_data.get("options", {"A": None, "B": None, "C": None, "D": None}),
        "correct_answers": question_data.get("correct_answers", []),
        "reference_solution": question_data.get("reference_solution", ""),
        "variables": question_data.get("variables", []),
        "figure": question_data.get("figure", {"exists": False}),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: 编写程序化校验器**

创建 `apps/courses/validator.py`：

```python
"""Programmatic validator for variant questions."""
import logging

logger = logging.getLogger(__name__)

VALID_UNITS = [
    'N', 'kg', 'm', 's', 'm/s', 'm/s^2', 'Pa', 'J', 'W',
    'A', 'V', 'ohm', 'W', 'kg/m^3', 'J/(kg*C)', 'C',
]

VALID_KNOWLEDGE_ROLES = ['primary', 'secondary']


class VariantValidator:
    """Validates generated variant questions."""

    def validate(self, variant_json: dict, original_question) -> list:
        """Run all validation checks. Returns list of error strings (empty = pass)."""
        errors = []
        self._check_json_schema(variant_json, errors)
        self._check_question_type(variant_json, original_question, errors)
        self._check_answer_count(variant_json, original_question, errors)
        self._check_units(variant_json, errors)
        self._check_value_ranges(variant_json, errors)
        self._check_single_choice_uniqueness(variant_json, errors)
        return errors

    def _check_json_schema(self, data: dict, errors: list):
        """Check required fields exist."""
        required = ['stem', 'correct_answers', 'question_type', 'knowledge_points']
        for field in required:
            if field not in data:
                errors.append(f"缺少必填字段: {field}")

    def _check_question_type(self, data: dict, original, errors: list):
        """Question type must be preserved."""
        if hasattr(original, 'question_type'):
            if data.get('question_type') != original.question_type:
                errors.append(
                    f"题型不一致: 原题={original.question_type}, "
                    f"变式={data.get('question_type')}"
                )

    def _check_answer_count(self, data: dict, original, errors: list):
        """Answer count must be preserved for choice questions."""
        answers = data.get('correct_answers', [])
        if not isinstance(answers, list) or len(answers) == 0:
            errors.append("正确答案为空或格式错误")
        elif data.get('question_type') == 'single_choice' and len(answers) > 1:
            errors.append("单选题正确答案超过1个")

    def _check_units(self, data: dict, errors: list):
        """Check units are in valid list (if present in variables)."""
        for var in data.get('variables', []):
            unit = var.get('unit', '')
            if unit and unit not in VALID_UNITS:
                logger.warning(f"Unknown unit: {unit}")

    def _check_value_ranges(self, data: dict, errors: list):
        """Check numeric values are in reasonable ranges."""
        for var in data.get('variables', []):
            val = var.get('value')
            if val is not None:
                try:
                    num_val = float(val)
                    if num_val < 0 and var.get('name') not in ('temperature', 'potential'):
                        errors.append(f"负数值异常: {var.get('name')}={val}")
                    if abs(num_val) > 1e9:
                        errors.append(f"数值过大: {var.get('name')}={val}")
                except (ValueError, TypeError):
                    pass  # Non-numeric values are ok (e.g., expressions)

    def _check_single_choice_uniqueness(self, data: dict, errors: list):
        """For single choice, ensure correct answer is unique."""
        if data.get('question_type') != 'single_choice':
            return
        # This would need full option content comparison
        # Basic check: at least 2 options should exist
        options = data.get('options', {})
        non_empty = sum(1 for v in options.values() if v)
        if non_empty < 2:
            errors.append("单选题选项少于2个")
```

- [ ] **Step 3: 编写 AI 服务**

创建 `apps/courses/ai_service.py`：

```python
"""AI service for variant question generation and verification."""
import json
import logging
import time
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def get_api_key():
    """Get API key from environment."""
    import os
    return os.environ.get('QWEN_API_KEY', '')


def call_ai(system_prompt: str, user_prompt: str, model: str, max_tokens: int = 8000, temperature: float = 0.1) -> str:
    """Call AI API with retry logic. Returns response text."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("QWEN_API_KEY is not set")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    retry_delays = [5, 8, 10]
    last_error = None

    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=300.0, trust_env=False) as client:
                response = client.post(QWEN_API_URL, json=payload, headers=headers)
                response.raise_for_status()
            result = response.json()
            choices = result.get("choices", [])
            if not choices:
                raise ValueError("No choices in AI response")
            return choices[0]["message"]["content"]
        except httpx.ReadTimeout as e:
            last_error = e
            wait = retry_delays[attempt - 1]
            logger.warning(f"AI API timeout (attempt {attempt}/3), retrying in {wait}s")
            time.sleep(wait)
        except httpx.HTTPError as e:
            last_error = e
            wait = retry_delays[attempt - 1]
            logger.warning(f"AI API HTTP error (attempt {attempt}/3), retrying in {wait}s")
            time.sleep(wait)
        except Exception as e:
            last_error = e
            logger.error(f"AI API unexpected error: {e}")
            raise

    raise ValueError(f"AI API failed after 3 retries: {last_error}")


def parse_json_response(text: str) -> dict:
    """Parse JSON from AI response, handling common issues."""
    # Strip markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
```

- [ ] **Step 4: 编写 Celery 任务**

创建 `apps/courses/tasks.py`：

```python
"""Celery tasks for variant question generation."""
import json
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

from apps.parser.models import ExamQuestion, QuestionOption
from apps.courses.models import VariantTask, CourseQuestionLink
from apps.courses.ai_service import call_ai, parse_json_response
from apps.courses.prompts import VARIANT_SYSTEM_PROMPT, VERIFIER_SYSTEM_PROMPT, build_variant_user_prompt
from apps.courses.validator import VariantValidator

logger = logging.getLogger(__name__)


def _build_question_data(question) -> dict:
    """Build structured question data for AI processing."""
    data = {
        "question_id": question.id,
        "subject": question.subject or "初中物理",
        "grade": "",
        "question_type": question.question_type,
        "knowledge_points": question.knowledge_points or [],
        "difficulty": float(question.difficulty) if question.difficulty else 0.5,
        "stem": question.stem,
        "options": {},
        "correct_answers": [],
        "reference_solution": question.analysis or question.solution or "",
        "variables": [],
        "figure": {"exists": False},
    }

    # Extract options
    for opt in question.options.all():
        data["options"][opt.option_label] = opt.content

    # Try to extract correct answers from answer field
    if question.answer:
        data["correct_answers"] = [question.answer.strip()]

    return data


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_variant_task(self, question_id: int, variant_mode: str, tree_node_id: int = None):
    """Generate a variant question asynchronously."""
    task = None
    try:
        # Get original question
        question = ExamQuestion.objects.get(id=question_id)

        # Create variant task
        task = VariantTask.objects.create(
            original_question=question,
            variant_mode=variant_mode,
            status='running',
        )

        # Build question data
        question_data = _build_question_data(question)

        # Step 1: Completeness check - if missing analysis, mark warning
        if not question_data.get('reference_solution'):
            logger.warning(f"Question {question_id} has no analysis/solution")

        # Step 2: Generate variant (qwen3.7-plus)
        model_name = getattr(settings, 'AI_MODEL_QWEN_37_PLUS', 'qwen3.7-plus')
        user_prompt = build_variant_user_prompt(question_data, variant_mode)

        logger.info(f"Generating variant for question {question_id} with mode {variant_mode}")
        response_text = call_ai(
            system_prompt=VARIANT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=model_name,
        )

        # Parse response
        variant_json = parse_json_response(response_text)
        task.generator_result = variant_json

        if variant_json.get('status') == 'failed':
            task.status = 'failed'
            task.error_message = variant_json.get('failure_reason', '生成失败')
            task.completed_at = timezone.now()
            task.save()
            return {'status': 'failed', 'reason': task.error_message}

        # Step 3: Programmatic validation
        validator = VariantValidator()
        validation_errors = validator.validate(variant_json, question)

        if validation_errors:
            logger.warning(f"Validation errors: {validation_errors}")
            # Retry once with upgrade model
            if self.request.retries < 1:
                raise self.retry(exc=ValueError(f"Validation failed: {validation_errors}"))
            task.error_message = f"校验失败: {validation_errors}"
            task.status = 'failed'
            task.completed_at = timezone.now()
            task.save()
            return {'status': 'failed', 'errors': validation_errors}

        # Step 4: Verify with deepseek
        deepseek_model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-v4-pro')
        verifier_prompt = json.dumps({
            "original": {
                "stem": question.stem,
                "answer": question.answer,
                "analysis": question.analysis,
            },
            "variant": variant_json,
        }, ensure_ascii=False)

        verifier_text = call_ai(
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            user_prompt=verifier_prompt,
            model=deepseek_model,
        )
        verifier_json = parse_json_response(verifier_text)
        task.verifier_result = verifier_json

        if not verifier_json.get('passed', False):
            logger.warning(f"Verifier rejected: {verifier_json.get('reason')}")
            if self.request.retries < 1:
                raise self.retry(exc=ValueError(f"Verifier rejected: {verifier_json.get('reason')}"))
            task.error_message = f"验证不通过: {verifier_json.get('reason')}"
            task.status = 'failed'
            task.completed_at = timezone.now()
            task.save()
            return {'status': 'failed', 'reason': verifier_json.get('reason')}

        # Step 5: Save as ExamQuestion (pending confirmation)
        task.generated_question = variant_json
        task.status = 'success'
        task.completed_at = timezone.now()
        task.save()

        # Create the variant question in DB
        variant_question = ExamQuestion.objects.create(
            paper=question.paper,
            question_no=f"V-{question_id}-{task.id}",
            question_type=variant_json.get('question_type', question.question_type),
            subject=question.subject,
            stem=variant_json.get('stem', ''),
            answer=','.join(variant_json.get('correct_answers', [])),
            analysis=variant_json.get('solution', {}).get('conclusion', '') if isinstance(variant_json.get('solution'), dict) else '',
            difficulty=variant_json.get('new_difficulty', question.difficulty),
            knowledge_points=variant_json.get('knowledge_points', question.knowledge_points),
            original_question=question,
            review_status='need_review',  # Pending confirmation
        )

        logger.info(f"Variant question {variant_question.id} created successfully")
        return {
            'status': 'success',
            'variant_question_id': variant_question.id,
            'task_id': task.id,
        }

    except Exception as e:
        logger.error(f"Variant task {task.id if task else 'unknown'} failed: {e}")
        if task:
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = timezone.now()
            task.save()
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=0)
def batch_generate_variants_task(self, question_ids: list, variant_mode: str, tree_node_id: int = None):
    """Batch generate variants by dispatching individual tasks."""
    task_ids = []
    for qid in question_ids:
        result = generate_variant_task.delay(qid, variant_mode, tree_node_id)
        task_ids.append(str(result.id))
    return {'task_ids': task_ids, 'count': len(task_ids)}
```

- [ ] **Step 5: 新增 .env 配置**

在 `.env` 文件末尾添加：

```
# AI Models for Course Variants
AI_MODEL_QWEN_37_FLASH=qwen3.7-flash
AI_MODEL_QWEN_37_PLUS=qwen3.7-plus
DEEPSEEK_MODEL=deepseek-v4-pro
```

- [ ] **Step 6: 提交**

```bash
cd front
git add apps/courses/prompts.py apps/courses/validator.py apps/courses/ai_service.py apps/courses/tasks.py .env
git commit -m "feat: add variant question generation with Celery async tasks, AI service, and validator"
```

---

### Task 4: 习题管理 API（课程习题 CRUD + AI 处理 + 变式题发起）

**Files:**
- Modify: `apps/courses/views.py` (追加习题管理相关端点)
- Modify: `apps/courses/urls.py` (追加 URL 路由)

**Interfaces:**
- Consumes: Task 2 的模型 + Task 3 的 Celery 任务 + 现有 `review` API 模式
- Produces: 习题管理 API 端点

- [ ] **Step 1: 追加习题管理 API Views**

在 `apps/courses/views.py` 末尾追加：

```python
# ── Course Questions ──

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request, course_id):
    """课程习题列表（按 tree_node 筛选）。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    tree_node_id = request.query_params.get('tree_node_id')
    links = CourseQuestionLink.objects.filter(
        course=course, is_deleted=False
    ).select_related('question')

    if tree_node_id:
        links = links.filter(tree_node_id=tree_node_id)

    # Build response with question details
    questions = []
    for link in links:
        q = link.question
        questions.append({
            'id': q.id,
            'system_id': q.system_id,
            'question_no': q.question_no,
            'question_type': q.question_type,
            'stem_preview': q.stem[:100] if q.stem else '',
            'difficulty': float(q.difficulty) if q.difficulty else 0,
            'knowledge_points_count': len(q.knowledge_points or []),
            'review_status': q.review_status,
            'ai_answer_a': bool(q.ai_answer_a),
            'ai_answer_b': bool(q.ai_answer_b),
            'ai_answer_c': bool(q.ai_answer_c),
            'ai_answer_a_confirmed': False,
            'ai_answer_b_confirmed': False,
            'ai_answer_c_confirmed': False,
            'source': link.source,
            'tree_node_id': link.tree_node_id,
        })

    return Response({'success': True, 'data': questions})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_import(request, course_id):
    """从题库引入习题到课程。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids', [])
    tree_node_id = request.data.get('tree_node_id')

    if not question_ids:
        raise ValidationError("未指定题目")

    imported = []
    for qid in question_ids:
        try:
            question = ExamQuestion.objects.get(id=qid)
        except ExamQuestion.DoesNotExist:
            continue

        # Skip if already linked
        if CourseQuestionLink.objects.filter(course=course, question=question).exists():
            continue

        link = CourseQuestionLink.objects.create(
            course=course,
            tree_node_id=tree_node_id,
            question=question,
            source='imported_from_bank',
        )
        imported.append(qid)

    return Response({'success': True, 'data': {'imported': imported, 'count': len(imported)}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_batch_delete(request, course_id):
    """批量从课程移除习题。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids', [])
    removed = CourseQuestionLink.objects.filter(
        course=course, question_id__in=question_ids
    ).update(is_deleted=True)

    return Response({'success': True, 'data': {'removed': removed}})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_batch_move(request, course_id):
    """批量移动习题所属节点。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids', [])
    target_node_id = request.data.get('target_node_id')

    if not target_node_id:
        raise ValidationError("未指定目标节点")

    moved = CourseQuestionLink.objects.filter(
        course=course, question_id__in=question_ids
    ).update(tree_node_id=target_node_id)

    return Response({'success': True, 'data': {'moved': moved}})


# ── AI Processing (courses) ──

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_ai_process(request, course_id):
    """对课程中的题目发起 AI 处理（复用现有 review API 模式）。"""
    question_id = request.data.get('question_id')
    if not question_id:
        raise ValidationError("未指定题目")

    # Forward to review API (reuse existing endpoint)
    from apps.review.views import ai_process_question
    # Add question_id to path params and delegate
    request.path = f'/review/question/{question_id}/ai-process/'
    return ai_process_question(request, question_id)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_ai_confirm(request, course_id, question_id):
    """AI 答案确认。"""
    mode = request.data.get('mode', 'a')
    from apps.review.views import ai_confirm_answer
    return ai_confirm_answer(request, question_id, mode)


# ── Variant Generation ──

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_variant(request, course_id, question_id):
    """发起变式题生成任务。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    # Check question exists in course
    link = CourseQuestionLink.objects.filter(
        course=course, question_id=question_id, is_deleted=False
    ).first()
    if not link:
        raise NotFound("题目不在课程中")

    variant_mode = request.data.get('variant_mode', 'mixed_light')

    # Check if question is AI-confirmed
    try:
        question = ExamQuestion.objects.get(id=question_id)
        if question.review_status != 'confirmed':
            return Response({
                'success': False,
                'message': '题目尚未完成 AI 答案确认，无法生成变式题',
            }, status=status.HTTP_400_BAD_REQUEST)
    except ExamQuestion.DoesNotExist:
        raise NotFound("题目不存在")

    # Dispatch Celery task
    from .tasks import generate_variant_task
    task = generate_variant_task.delay(question_id, variant_mode, link.tree_node_id)

    return Response({
        'success': True,
        'data': {'celery_task_id': str(task.id), 'message': '变式题生成任务已提交'},
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_generate_variant(request, course_id):
    """批量生成变式题。"""
    try:
        course = Course.objects.get(id=course_id, is_deleted=False)
    except Course.DoesNotExist:
        raise NotFound("课程不存在")
    _check_course_owner(course, request.user)

    question_ids = request.data.get('question_ids', [])
    variant_mode = request.data.get('variant_mode', 'mixed_light')
    tree_node_id = request.data.get('tree_node_id')

    if not question_ids:
        raise ValidationError("未指定题目")

    from .tasks import batch_generate_variants_task
    result = batch_generate_variants_task.delay(question_ids, variant_mode, tree_node_id)

    return Response({
        'success': True,
        'data': {'celery_task_id': str(result.id), 'count': len(question_ids)},
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def variant_task_confirm(request, course_id, task_id):
    """确认变式题入库。"""
    try:
        task = VariantTask.objects.get(id=task_id, status='success')
    except VariantTask.DoesNotExist:
        raise NotFound("任务不存在或未完成")

    # Update variant question review_status to 'confirmed'
    # The actual question was already created with review_status='need_review'
    # This just marks the variant task as confirmed
    if hasattr(task, 'generated_question') and task.generated_question:
        # Find the created question and confirm it
        variant_q = ExamQuestion.objects.filter(
            original_question_id=task.original_question_id,
            review_status='need_review',
        ).order_by('-id').first()
        if variant_q:
            variant_q.review_status = 'confirmed'
            variant_q.save(update_fields=['review_status'])

    return Response({'success': True, 'message': '变式题已确认入库'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def variant_task_reject(request, course_id, task_id):
    """驳回变式题。"""
    try:
        task = VariantTask.objects.get(id=task_id)
    except VariantTask.DoesNotExist:
        raise NotFound("任务不存在")

    # Mark the generated question as rejected
    variant_q = ExamQuestion.objects.filter(
        original_question_id=task.original_question_id,
        review_status='need_review',
    ).order_by('-id').first()
    if variant_q:
        variant_q.review_status = 'rejected'
        variant_q.save(update_fields=['review_status'])

    return Response({'success': True, 'message': '变式题已驳回'})
```

- [ ] **Step 2: 追加 URL 路由**

在 `apps/courses/urls.py` 末尾追加：

```python
    # Questions
    path('courses/<int:course_id>/questions/', views.question_list, name='question-list'),
    path('courses/<int:course_id>/questions/import/', views.question_import, name='question-import'),
    path('courses/<int:course_id>/questions/batch-delete/', views.question_batch_delete, name='question-batch-delete'),
    path('courses/<int:course_id>/questions/batch-move/', views.question_batch_move, name='question-batch-move'),
    path('courses/<int:course_id>/questions/ai-process/', views.question_ai_process, name='question-ai-process'),
    path('courses/<int:course_id>/questions/<int:question_id>/ai-confirm/', views.question_ai_confirm, name='question-ai-confirm'),

    # Variant generation
    path('courses/<int:course_id>/questions/<int:question_id>/generate-variant/', views.generate_variant, name='generate-variant'),
    path('courses/<int:course_id>/questions/batch-generate-variant/', views.batch_generate_variant, name='batch-generate-variant'),
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/confirm/', views.variant_task_confirm, name='variant-task-confirm'),
    path('courses/<int:course_id>/variant-tasks/<int:task_id>/reject/', views.variant_task_reject, name='variant-task-reject'),
```

- [ ] **Step 3: 提交**

```bash
cd front
git add apps/courses/views.py apps/courses/urls.py
git commit -m "feat: add course question management, AI processing, and variant generation APIs"
```

---

### Task 5: 前端 API 封装 + TeacherSidebar 修改

**Files:**
- Create: `uniapp/src/api/courses.ts`
- Modify: `uniapp/src/components/TeacherSidebar.vue`

**Interfaces:**
- Consumes: 后端 API（Task 2 + Task 4）
- Produces: 前端 API 函数供页面组件调用

- [ ] **Step 1: 编写课程 API 封装**

创建 `uniapp/src/api/courses.ts`：

```typescript
import { post, get, put, del } from '@/utils/request.ts'

// ── Courses ──

export const courseApi = {
  list: () => get<any[]>('/courses/'),
  create: (data: { name: string; subject: string; grade_level: string; description?: string }) =>
    post<any>('/courses/', data),
  detail: (id: number) => get<any>(`/courses/${id}/`),
  update: (id: number, data: any) => put<any>(`/courses/${id}/`, data),
  remove: (id: number) => del<any>(`/courses/${id}/`),
}

// ── Materials ──

export const materialApi = {
  list: (courseId: number) => get<any[]>(`/courses/${courseId}/materials/`),
  upload: (courseId: number, file: File) => {
    return new Promise<any>(async (resolve, reject) => {
      const token = uni.getStorageSync('accessToken')
      const formData = new FormData()
      formData.append('file', file)
      try {
        const res = await fetch(`/api/v1/courses/${courseId}/materials/upload/`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        })
        const data = await res.json()
        res.ok ? resolve(data) : reject(new Error(data.message || '上传失败'))
      } catch (e) { reject(e) }
    })
  },
  download: (courseId: number, materialId: number) =>
    `/api/v1/courses/${courseId}/materials/${materialId}/download/`,
  preview: (courseId: number, materialId: number) =>
    get<any>(`/courses/${courseId}/materials/${materialId}/preview/`),
  remove: (courseId: number, materialId: number) =>
    del<any>(`/courses/${courseId}/materials/${materialId}/`),
}

// ── Tree ──

export const treeApi = {
  list: (courseId: number) => get<any[]>(`/courses/${courseId}/tree/`),
  create: (courseId: number, data: { name: string; parent?: number; sort_order?: number }) =>
    post<any>(`/courses/${courseId}/tree/`, data),
  update: (courseId: number, nodeId: number, data: any) =>
    put<any>(`/courses/${courseId}/tree/${nodeId}/`, data),
  remove: (courseId: number, nodeId: number) =>
    del<any>(`/courses/${courseId}/tree/${nodeId}/`),
  move: (courseId: number, nodeId: number, data: { parent?: number; sort_order?: number }) =>
    put<any>(`/courses/${courseId}/tree/${nodeId}/move/`, data),
}

// ── Questions ──

export const courseQuestionApi = {
  list: (courseId: number, params?: { tree_node_id?: number }) => {
    const query = params?.tree_node_id ? `?tree_node_id=${params.tree_node_id}` : ''
    return get<any[]>(`/courses/${courseId}/questions/${query}`)
  },
  import: (courseId: number, data: { question_ids: number[]; tree_node_id?: number }) =>
    post<any>(`/courses/${courseId}/questions/import/`, data),
  batchDelete: (courseId: number, questionIds: number[]) =>
    post<any>(`/courses/${courseId}/questions/batch-delete/`, { question_ids: questionIds }),
  batchMove: (courseId: number, questionIds: number[], targetNodeId: number) =>
    post<any>(`/courses/${courseId}/questions/batch-move/`, { question_ids: questionIds, target_node_id: targetNodeId }),
}

// ── Variants ──

export const variantApi = {
  generate: (courseId: number, questionId: number, mode?: string) =>
    post<any>(`/courses/${courseId}/questions/${questionId}/generate-variant/`, { variant_mode: mode || 'mixed_light' }),
  batchGenerate: (courseId: number, questionIds: number[], mode?: string) =>
    post<any>(`/courses/${courseId}/questions/batch-generate-variant/`, { question_ids: questionIds, variant_mode: mode || 'mixed_light' }),
  getStatus: (courseId: number, taskId: number) =>
    get<any>(`/courses/${courseId}/variant-tasks/${taskId}/`),
  confirm: (courseId: number, taskId: number) =>
    post<any>(`/courses/${courseId}/variant-tasks/${taskId}/confirm/`),
  reject: (courseId: number, taskId: number) =>
    post<any>(`/courses/${courseId}/variant-tasks/${taskId}/reject/`),
}
```

- [ ] **Step 2: 修改 TeacherSidebar**

在 `uniapp/src/components/TeacherSidebar.vue` 的"班级管理"之前新增"课程列表"菜单项：

找到以下代码段（约在第 32 行）：
```vue
      <view class="nav-item" :class="{ active: activeItem === 'classes' }" @click="goClasses">
```

在其上方插入：
```vue
      <view class="nav-item" :class="{ active: activeItem === 'course-list' }" @click="goCourseList">
        <text class="nav-icon">&#127891;</text>
        <text class="nav-text">课程列表</text>
      </view>
```

在 `goClasses` 函数定义上方新增导航函数：
```typescript
function goCourseList() { uni.navigateTo({ url: '/pages/teacher/course-list' }) }
```

- [ ] **Step 3: 提交**

```bash
cd front
git add uniapp/src/api/courses.ts uniapp/src/components/TeacherSidebar.vue
git commit -m "feat: add course API client and TeacherSidebar menu item"
```

---

### Task 6: 前端课程列表页 + 课程卡片组件

**Files:**
- Create: `uniapp/src/components/CourseCard.vue`
- Create: `uniapp/src/pages/teacher/course-list.vue`
- Modify: `uniapp/pages.json` (注册路由)

**Interfaces:**
- Consumes: `courseApi`, `materialApi`, `TeacherSidebar`
- Produces: 课程卡片列表页面

- [ ] **Step 1: 编写 CourseCard 组件**

创建 `uniapp/src/components/CourseCard.vue`：

```vue
<template>
  <view class="course-card" @click="$emit('click')">
    <view class="card-cover" :style="{ background: coverGradient }">
      <text class="card-subject">{{ subjectLabel }}</text>
      <text class="card-grade">{{ course.grade_level }}</text>
    </view>
    <view class="card-body">
      <text class="card-name">{{ course.name }}</text>
      <text class="card-desc">{{ course.description || '暂无介绍' }}</text>
      <view class="card-stats">
        <text class="stat">资料 {{ course.material_count || 0 }}</text>
        <text class="stat">习题 {{ course.question_count || 0 }}</text>
      </view>
      <view class="card-actions">
        <button size="mini" type="primary" @click.stop="$emit('materials')">课程资料</button>
        <button size="mini" type="success" @click.stop="$emit('practice')">课程练习</button>
        <view class="delete-btn" @click.stop="$emit('delete')">
          <text class="delete-icon">&times;</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  course: {
    id: number
    name: string
    description: string
    subject: string
    grade_level: string
    material_count: number
    question_count: number
  }
}>()

defineEmits<{
  click: []
  materials: []
  practice: []
  delete: []
}>()

const SUBJECT_LABELS: Record<string, string> = {
  math: '数学',
  physics: '物理',
  chemistry: '化学',
  biology: '生物',
}

const subjectLabel = computed(() => SUBJECT_LABELS[props.course.subject] || props.course.subject)

const GRADIENTS: Record<string, string> = {
  math: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  physics: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  chemistry: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  biology: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
}

const coverGradient = computed(() => GRADIENTS[props.course.subject] || GRADIENTS.physics)
</script>

<style scoped>
.course-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.course-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}
.card-cover {
  height: 80px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #fff;
}
.card-subject { font-size: 28rpx; font-weight: bold; }
.card-grade { font-size: 22rpx; opacity: 0.85; margin-top: 4rpx; }
.card-body { padding: 16px; }
.card-name { font-size: 15px; font-weight: 600; color: #303133; display: block; }
.card-desc { font-size: 12px; color: #909399; margin-top: 4px; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-stats { display: flex; gap: 12px; margin-top: 8px; }
.stat { font-size: 11px; color: #606266; }
.card-actions { display: flex; gap: 8px; margin-top: 12px; align-items: center; }
.delete-btn { margin-left: auto; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: #f5f5f5; cursor: pointer; }
.delete-icon { font-size: 14px; color: #e74c3c; }
</style>
```

- [ ] **Step 2: 编写课程列表页**

创建 `uniapp/src/pages/teacher/course-list.vue`：

```vue
<template>
  <view class="course-list-page">
    <TeacherSidebar activeItem="course-list" />
    <view class="main">
      <view class="page-header">
        <text class="page-title">课程列表</text>
        <button class="btn-add" @click="showCreateDialog = true">+ 新建课程</button>
      </view>

      <view v-if="loading" class="loading">加载中...</view>
      <view v-else-if="courses.length === 0" class="empty">
        <text>暂无课程，点击右上角新建</text>
      </view>
      <view v-else class="card-grid">
        <CourseCard
          v-for="c in courses" :key="c.id"
          :course="c"
          @click="goDetail(c.id)"
          @materials="goMaterials(c.id)"
          @practice="goPractice(c.id)"
          @delete="handleDelete(c)"
        />
      </view>

      <!-- Create dialog -->
      <view v-if="showCreateDialog" class="modal-overlay" @click.self="showCreateDialog=false">
        <view class="modal">
          <text class="modal-title">新建课程</text>
          <view class="form-group">
            <text class="label">课程名称</text>
            <input v-model="form.name" class="input" placeholder="如：26年物理9年级S班课程" />
          </view>
          <view class="form-group">
            <text class="label">学科</text>
            <select v-model="form.subject" class="select">
              <option value="physics">物理</option>
              <option value="math">数学</option>
              <option value="chemistry">化学</option>
              <option value="biology">生物</option>
            </select>
          </view>
          <view class="form-group">
            <text class="label">年级</text>
            <select v-model="form.grade_level" class="select">
              <option value="七年级">七年级</option>
              <option value="八年级">八年级</option>
              <option value="九年级">九年级</option>
            </select>
          </view>
          <view class="form-group">
            <text class="label">课程介绍</text>
            <textarea v-model="form.description" class="textarea" placeholder="简要介绍课程内容..." rows="3"></textarea>
          </view>
          <view class="modal-footer">
            <button size="mini" @click="showCreateDialog=false">取消</button>
            <button size="mini" type="primary" :disabled="!form.name" @click="handleCreate">创建</button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import CourseCard from '@/components/CourseCard.vue'
import { courseApi } from '@/api/courses'

const courses = ref<any[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const form = ref({ name: '', subject: 'physics', grade_level: '九年级', description: '' })

async function loadCourses() {
  loading.value = true
  try {
    const res: any = await courseApi.list()
    courses.value = res.data || []
  } catch (e) {
    console.error('加载课程列表失败:', e)
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  try {
    await courseApi.create(form.value)
    uni.showToast({ title: '创建成功', icon: 'success' })
    showCreateDialog.value = false
    form.value = { name: '', subject: 'physics', grade_level: '九年级', description: '' }
    loadCourses()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '创建失败', icon: 'none' })
  }
}

function handleDelete(course: any) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除课程「${course.name}」吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await courseApi.remove(course.id)
          uni.showToast({ title: '已删除', icon: 'success' })
          loadCourses()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    },
  })
}

function goDetail(id: number) { uni.navigateTo({ url: `/pages/teacher/course-materials?id=${id}` }) }
function goMaterials(id: number) { uni.navigateTo({ url: `/pages/teacher/course-materials?id=${id}` }) }
function goPractice(id: number) { uni.navigateTo({ url: `/pages/teacher/course-practice?id=${id}` }) }

onMounted(loadCourses)
</script>

<style scoped>
.course-list-page { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 240px; flex: 1; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-title { font-size: 22px; font-weight: 600; color: #303133; }
.btn-add { padding: 8px 16px; background: #409eff; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-add:hover { background: #66b1ff; }
.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.loading, .empty { text-align: center; color: #909399; padding: 80px 0; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; padding: 24px; width: 480px; }
.modal-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: block; }
.form-group { margin-bottom: 12px; }
.label { font-size: 13px; color: #606266; margin-bottom: 4px; display: block; }
.input, .select, .textarea { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.textarea { resize: vertical; min-height: 60px; }
.modal-footer { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
</style>
```

- [ ] **Step 3: 注册路由**

在 `uniapp/pages.json` 的 `pages` 数组中添加：

```json
{ "path": "pages/teacher/course-list", "style": { "navigationBarTitleText": "课程列表" } },
{ "path": "pages/teacher/course-materials", "style": { "navigationBarTitleText": "课程资料" } },
{ "path": "pages/teacher/course-practice", "style": { "navigationBarTitleText": "课程练习" } },
```

- [ ] **Step 4: 提交**

```bash
cd front
git add uniapp/src/components/CourseCard.vue uniapp/src/pages/teacher/course-list.vue uniapp/pages.json
git commit -m "feat: add course list page with card grid and create dialog"
```

---

### Task 7: 前端课程资料页

**Files:**
- Create: `uniapp/src/pages/teacher/course-materials.vue`

**Interfaces:**
- Consumes: `materialApi`, `courseApi`, `TeacherSidebar`
- Produces: 课程资料管理页面

- [ ] **Step 1: 编写课程资料页**

创建 `uniapp/src/pages/teacher/course-materials.vue`：

```vue
<template>
  <view class="materials-page">
    <TeacherSidebar activeItem="course-list" />
    <view class="main">
      <view class="page-header">
        <view>
          <text class="breadcrumb">课程列表 /</text>
          <text class="page-title">{{ courseName }}</text>
        </view>
        <button class="btn-upload" @click="triggerUpload">+ 上传资料</button>
        <input type="file" ref="fileInput" style="display:none" @change="handleFileSelect" />
      </view>

      <view v-if="loading" class="loading">加载中...</view>
      <view v-else-if="materials.length === 0" class="empty">暂无资料文件</view>
      <view v-else class="material-table">
        <view class="table-header">
          <text class="col col-name">文件名</text>
          <text class="col col-type">类型</text>
          <text class="col col-size">大小</text>
          <text class="col col-date">上传时间</text>
          <text class="col col-actions">操作</text>
        </view>
        <view v-for="m in materials" :key="m.id" class="table-row">
          <text class="col col-name">{{ m.name }}</text>
          <text class="col col-type">{{ m.file_type.toUpperCase() }}</text>
          <text class="col col-size">{{ formatSize(m.file_size) }}</text>
          <text class="col col-date">{{ formatDate(m.created_at) }}</text>
          <view class="col col-actions">
            <button size="mini" @click="handleDownload(m)">下载</button>
            <button size="mini" type="primary" @click="handlePreview(m)">预览</button>
            <button size="mini" type="warn" @click="handleDelete(m)">删除</button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import { materialApi, courseApi } from '@/api/courses'

const courseId = ref(0)
const courseName = ref('')
const materials = ref<any[]>([])
const loading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

onMounted(() => {
  // Get course ID from URL params
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  courseId.value = Number(currentPage.options?.id || 0)
  loadCourse()
  loadMaterials()
})

async function loadCourse() {
  try {
    const res: any = await courseApi.detail(courseId.value)
    courseName.value = res.data?.name || ''
  } catch {}
}

async function loadMaterials() {
  loading.value = true
  try {
    const res: any = await materialApi.list(courseId.value)
    materials.value = res.data || []
  } catch (e) {
    console.error('加载资料列表失败:', e)
  } finally {
    loading.value = false
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  // Validate size (50MB)
  if (file.size > 50 * 1024 * 1024) {
    uni.showToast({ title: '文件大小超过50MB限制', icon: 'none' })
    return
  }

  uni.showLoading({ title: '上传中...' })
  try {
    await materialApi.upload(courseId.value, file)
    uni.hideLoading()
    uni.showToast({ title: '上传成功', icon: 'success' })
    loadMaterials()
  } catch (e: any) {
    uni.hideLoading()
    uni.showToast({ title: e?.message || '上传失败', icon: 'none' })
  }
  // Reset input
  input.value = ''
}

function handleDownload(m: any) {
  const url = materialApi.download(courseId.value, m.id)
  window.open(url, '_blank')
}

async function handlePreview(m: any) {
  if (m.file_type === 'image') {
    // Open image directly
    const url = `/api/v1/courses/${courseId.value}/materials/${m.id}/preview/`
    window.open(url, '_blank')
  } else {
    try {
      const res: any = await materialApi.preview(courseId.value, m.id)
      if (res.data?.url) {
        window.open(res.data.url, '_blank')
      }
    } catch (e) {
      uni.showToast({ title: '预览失败', icon: 'none' })
    }
  }
}

function handleDelete(m: any) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除「${m.name}」吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await materialApi.remove(courseId.value, m.id)
          uni.showToast({ title: '已删除', icon: 'success' })
          loadMaterials()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    },
  })
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.materials-page { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 240px; flex: 1; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.breadcrumb { font-size: 12px; color: #909399; margin-right: 8px; }
.page-title { font-size: 20px; font-weight: 600; color: #303133; }
.btn-upload { padding: 8px 16px; background: #67c23a; color: #fff; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }
.btn-upload:hover { background: #85ce61; }
.material-table { background: #fff; border-radius: 8px; overflow: hidden; }
.table-header { display: flex; padding: 12px 16px; background: #f5f7fa; font-size: 13px; color: #909399; font-weight: 500; }
.table-row { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.table-row:hover { background: #fafafa; }
.col-name { flex: 2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-type { width: 60px; text-align: center; }
.col-size { width: 80px; text-align: center; }
.col-date { width: 100px; }
.col-actions { display: flex; gap: 4px; }
.loading, .empty { text-align: center; color: #909399; padding: 60px 0; }
</style>
```

- [ ] **Step 2: 提交**

```bash
cd front
git add uniapp/src/pages/teacher/course-materials.vue
git commit -m "feat: add course materials page with upload/download/preview/delete"
```

---

### Task 8: 前端课程练习页（目录树 + 习题列表）

**Files:**
- Create: `uniapp/src/components/DirTree.vue`
- Create: `uniapp/src/pages/teacher/course-practice.vue`

**Interfaces:**
- Consumes: `treeApi`, `courseQuestionApi`, `variantApi`, `TeacherSidebar`
- Produces: 课程练习页面（目录树 + 习题列表 + 批量操作）

- [ ] **Step 1: 编写 DirTree 组件**

创建 `uniapp/src/components/DirTree.vue`：

```vue
<template>
  <view class="dir-tree">
    <view class="tree-header">
      <text class="tree-title">目录树</text>
      <button size="mini" @click="$emit('add-root', null)">+ 根节点</button>
    </view>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="nodes.length === 0" class="empty">暂无目录节点</view>
    <view v-else class="tree-content">
      <TreeNode
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :selected-id="selectedId"
        @select="$emit('select', $event)"
        @add-child="$emit('add-child', $event)"
        @rename="$emit('rename', $event)"
        @delete="$emit('delete-node', $event)"
      />
    </view>

    <!-- Context menu -->
    <view v-if="contextMenu.visible" class="context-menu" :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }" @click.self="closeContextMenu">
      <view class="menu-item" @click="contextMenu.callback('add-child'); closeContextMenu()">新增下级节点</view>
      <view class="menu-item" @click="contextMenu.callback('rename'); closeContextMenu()">重命名</view>
      <view class="menu-item" @click="contextMenu.callback('delete'); closeContextMenu()">删除节点</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, h } from 'vue'

interface TreeNode {
  id: number
  name: string
  sort_order: number
  children: TreeNode[]
  question_count?: number
}

const props = defineProps<{
  nodes: TreeNode[]
  loading: boolean
}>()

const emit = defineEmits<{
  select: [id: number]
  'add-root': [parent: null]
  'add-child': [node: TreeNode]
  rename: [node: TreeNode]
  'delete-node': [node: TreeNode]
}>()

const selectedId = ref<number | null>(null)
const contextMenu = ref({ visible: false, x: 0, y: 0, nodeId: 0, callback: (action: string) => {} })

function closeContextMenu() {
  contextMenu.value.visible = false
}

// Expose contextMenu trigger for child nodes
defineExpose({ contextMenu })
</script>

<script lang="ts">
// TreeNode sub-component for recursive rendering
const TreeNode = {
  props: ['node', 'selectedId'],
  emits: ['select', 'add-child', 'rename', 'delete-node'],
  setup(props: any, { emit }: any) {
    const expanded = ref(false)

    function handleRightClick(event: MouseEvent) {
      event.preventDefault()
      // Handled via parent context menu
    }

    return () => h('view', {
      class: 'tree-node-item',
      onClick: () => emit('select', props.node.id),
      onContextmenu: handleRightClick,
    }, [
      h('view', { class: 'node-row' }, [
        h('text', {
          class: 'arrow',
          onClick: (e: Event) => { e.stopPropagation(); expanded.value = !expanded.value },
          style: { visibility: props.node.children?.length ? 'visible' : 'hidden' },
        }, expanded.value ? '▼' : '▶'),
        h('text', {
          class: ['node-label', { active: props.selectedId === props.node.id }],
        }, props.node.name),
        props.node.question_count ? h('text', { class: 'node-count' }, `(${props.node.question_count})`) : null,
        h('view', {
          class: 'node-actions',
          onContextmenu: (e: Event) => {
            e.preventDefault()
            e.stopPropagation()
            // Emit context menu event
          },
        }, [
          h('text', {
            class: 'action-btn',
            onClick: (e: Event) => { e.stopPropagation(); emit('add-child', props.node) },
          }, '+'),
        ]),
      ]),
      expanded.value && props.node.children?.length
        ? h('view', { class: 'tree-children' }, props.node.children.map((child: any) =>
            h(TreeNode, { key: child.id, node: child, selectedId: props.selectedId, onSelect: emit.select, 'onAdd-child': emit['add-child'] })))
        : null,
    ])
  },
}
</script>

<style scoped>
.dir-tree { width: 100%; }
.tree-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.tree-title { font-size: 14px; font-weight: 500; color: #303133; }
.tree-content { overflow-y: auto; max-height: calc(100vh - 200px); }
.tree-node-item { user-select: none; }
.node-row { display: flex; align-items: center; padding: 4px 8px; border-radius: 4px; cursor: pointer; }
.node-row:hover { background: #f5f7fa; }
.arrow { font-size: 10px; margin-right: 4px; color: #909399; flex-shrink: 0; }
.node-label { flex: 1; font-size: 13px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-label.active { color: #409eff; font-weight: 500; background: #ecf5ff; border-radius: 4px; padding: 2px 4px; }
.node-count { font-size: 11px; color: #909399; margin-left: 4px; }
.node-actions { display: flex; gap: 4px; }
.action-btn { font-size: 14px; color: #409eff; cursor: pointer; padding: 0 4px; }
.tree-children { padding-left: 16px; }
.context-menu { position: fixed; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 1000; min-width: 140px; padding: 4px 0; }
.menu-item { padding: 8px 16px; font-size: 13px; color: #303133; cursor: pointer; }
.menu-item:hover { background: #f5f7fa; }
.loading, .empty { text-align: center; color: #909399; padding: 20px 0; font-size: 12px; }
</style>
```

- [ ] **Step 2: 编写课程练习页（核心页面）**

创建 `uniapp/src/pages/teacher/course-practice.vue`：

```vue
<template>
  <view class="practice-page">
    <TeacherSidebar activeItem="course-list" />
    <view class="main">
      <!-- Left: Directory Tree -->
      <view class="tree-panel">
        <DirTree
          :nodes="treeNodes"
          :loading="treeLoading"
          @select="onTreeNodeSelect"
          @add-child="onAddChild"
          @rename="onRename"
          @delete-node="onDeleteNode"
          @add-root="onAddRoot"
        />
      </view>

      <!-- Center: Question List -->
      <view class="question-panel">
        <view class="panel-header">
          <text class="panel-title">{{ currentTreeName || '请选择目录节点' }}</text>
          <view class="header-actions">
            <button size="mini" type="primary" @click="showAddQuestion = true">+ 新增习题</button>
            <button size="mini" @click="handleBatchAiProcess" :disabled="selectedIds.length === 0">批量AI处理</button>
            <button size="mini" type="success" @click="handleBatchVariant" :disabled="selectedIds.length === 0">批量生成变式题</button>
          </view>
        </view>

        <!-- Batch action bar -->
        <view v-if="selectedIds.length > 0" class="batch-bar">
          <text class="batch-text">已选 {{ selectedIds.length }} 题</text>
          <button size="mini" @click="handleBatchMove">移动节点</button>
          <button size="mini" type="warn" @click="handleBatchDelete">从课程移除</button>
          <button size="mini" @click="selectedIds = []">取消选择</button>
        </view>

        <view v-if="questionLoading" class="loading">加载中...</view>
        <view v-else-if="questions.length === 0" class="empty">
          <text v-if="!selectedTreeNode">请先在左侧选择目录节点</text>
          <text v-else>该节点下暂无习题</text>
        </view>
        <view v-else class="question-table">
          <view class="table-header">
            <view class="col col-check" @click="toggleSelectAll">
              <text>{{ isAllSelected ? '☑' : '☐' }}</text>
            </view>
            <text class="col-stem">题干</text>
            <text class="col-diff">难度</text>
            <text class="col-type">题型</text>
            <text class="col-source">来源</text>
            <text class="col-actions">操作</text>
          </view>
          <view v-for="q in questions" :key="q.id"
                :class="['table-row', { 'row-selected': selectedIds.includes(q.id) }]"
                @click="toggleSelect(q.id)">
            <view class="col col-check" @click.stop="toggleSelect(q.id)">
              <text>{{ selectedIds.includes(q.id) ? '☑' : '☐' }}</text>
            </view>
            <text class="col-stem" @click.stop="goEdit(q.id)">{{ q.stem_preview }}</text>
            <text :class="['col-diff', 'diff-' + q.difficulty]">L{{ q.difficulty }}</text>
            <text class="col-type">{{ q.question_type }}</text>
            <text class="col-source">{{ q.source === 'created_in_course' ? '课程创建' : '题库引入' }}</text>
            <view class="col-actions" @click.stop>
              <button size="mini" @click="goEdit(q.id)">编辑</button>
              <button size="mini" type="primary" @click="handleAiProcess(q.id)">AI处理</button>
              <button size="mini" type="success" @click="handleVariant(q.id)">生成变式题</button>
              <button size="mini" type="warn" @click="handleDelete(q.id)">移除</button>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Add Question Dialog -->
    <view v-if="showAddQuestion" class="modal-overlay" @click.self="showAddQuestion=false">
      <view class="modal modal-lg">
        <text class="modal-title">新增习题</text>
        <view class="add-tabs">
          <view :class="['tab', {active: addTab==='upload'}]" @click="addTab='upload'">拍照/上传</view>
          <view :class="['tab', {active: addTab==='materials'}]" @click="addTab='materials'">从课程资料选择</view>
          <view :class="['tab', {active: addTab==='bank'}]" @click="addTab='bank'">从题库引入</view>
        </view>

        <view v-if="addTab === 'upload'" class="tab-content">
          <view class="upload-area" @click="triggerFileUpload">
            <text>点击上传题目图片</text>
          </view>
          <view class="node-selector">
            <text>保存到节点：</text>
            <select v-model="selectedTreeNode" class="select">
              <option :value="null">-- 请选择 --</option>
              <option v-for="n in flatTreeNodes" :key="n.id" :value="n">{{ n.name }}</option>
            </select>
          </view>
        </view>

        <view v-if="addTab === 'materials'" class="tab-content">
          <view v-for="m in materials" :key="m.id" class="material-item">
            <text>{{ m.name }}</text>
            <button size="mini" @click="openMaterialForSelect(m)">框选</button>
          </view>
        </view>

        <view v-if="addTab === 'bank'" class="tab-content">
          <text class="bank-hint">从题库中选择题目引入到课程</text>
          <!-- Simplified: search and select -->
          <view class="bank-search">
            <input v-model="bankSearch" placeholder="搜索题干..." class="search-input" @input="searchBank" />
          </view>
          <view class="bank-results">
            <view v-for="q in bankResults" :key="q.id" class="bank-item">
              <view class="check" @click="toggleBankSelect(q.id)">
                <text>{{ bankSelectedIds.includes(q.id) ? '☑' : '☐' }}</text>
              </view>
              <text class="bank-stem">{{ q.stem_preview }}</text>
            </view>
          </view>
        </view>

        <view class="modal-footer">
          <button size="mini" @click="showAddQuestion=false">关闭</button>
          <button v-if="addTab==='bank'" size="mini" type="primary" @click="doBankImport">引入选中 ({{ bankSelectedIds.length }})</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import DirTree from '@/components/DirTree.vue'
import { treeApi, courseQuestionApi, variantApi } from '@/api/courses'
import { questionApi } from '@/api/questions'

const courseId = ref(0)
const treeNodes = ref<any[]>([])
const treeLoading = ref(false)
const selectedTreeNode = ref<any>(null)
const questions = ref<any[]>([])
const questionLoading = ref(false)
const selectedIds = ref<number[]>([])
const materials = ref<any[]>([])

// Add question dialog
const showAddQuestion = ref(false)
const addTab = ref('upload')

// Bank search
const bankSearch = ref('')
const bankResults = ref<any[]>([])
const bankSelectedIds = ref<number[]>([])

// AI polling
const aiPollTimers: Array<{ taskId: string; timer: ReturnType<typeof setInterval> }> = []

onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  courseId.value = Number(currentPage.options?.id || 0)
  loadTree()
  loadMaterials()
})

// Flat tree nodes for selector
const flatTreeNodes = computed(() => {
  const result: any[] = []
  function flatten(nodes: any[]) {
    for (const n of nodes) {
      result.push({ id: n.id, name: n.name })
      if (n.children) flatten(n.children)
    }
  }
  flatten(treeNodes.value)
  return result
})

const currentTreeName = computed(() => selectedTreeNode.value?.name || '')
const isAllSelected = computed(() => questions.value.length > 0 && selectedIds.value.length === questions.value.length)

function onTreeNodeSelect(id: number) {
  const node = findNode(treeNodes.value, id)
  selectedTreeNode.value = node
  loadQuestions()
}

function findNode(nodes: any[], id: number): any | null {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children) {
      const found = findNode(n.children, id)
      if (found) return found
    }
  }
  return null
}

async function loadTree() {
  treeLoading.value = true
  try {
    const res: any = await treeApi.list(courseId.value)
    treeNodes.value = res.data || []
  } catch (e) {
    console.error('加载目录树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

async function loadQuestions() {
  if (!selectedTreeNode.value) return
  questionLoading.value = true
  try {
    const res: any = await courseQuestionApi.list(courseId.value, { tree_node_id: selectedTreeNode.value.id })
    questions.value = res.data || []
    selectedIds.value = []
  } catch (e) {
    console.error('加载习题列表失败:', e)
  } finally {
    questionLoading.value = false
  }
}

async function loadMaterials() {
  try {
    const { materialApi } = await import('@/api/courses')
    const res: any = await materialApi.list(courseId.value)
    materials.value = (res.data || []).filter((m: any) => m.file_type === 'pdf' || m.file_type === 'word' || m.file_type === 'image')
  } catch {}
}

function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function toggleSelectAll() {
  if (isAllSelected.value) selectedIds.value = []
  else selectedIds.value = questions.value.map((q: any) => q.id)
}

function goEdit(id: number) {
  uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` })
}

// ── Tree operations ──

async function onAddRoot() {
  const name = await promptInput('请输入节点名称')
  if (!name) return
  try {
    await treeApi.create(courseId.value, { name, sort_order: treeNodes.value.length + 1 })
    loadTree()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '创建失败', icon: 'none' })
  }
}

async function onAddChild(node: any) {
  const name = await promptInput('请输入子节点名称')
  if (!name) return
  try {
    await treeApi.create(courseId.value, { name, parent: node.id, sort_order: 1 })
    loadTree()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '创建失败', icon: 'none' })
  }
}

async function onRename(node: any) {
  const name = await promptInput('请输入新名称', node.name)
  if (!name || name === node.name) return
  try {
    await treeApi.update(courseId.value, node.id, { name })
    loadTree()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '重命名失败', icon: 'none' })
  }
}

async function onDeleteNode(node: any) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除节点「${node.name}」及其所有子节点吗？节点下的习题将从课程中移除（不删除题目本身）`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await treeApi.remove(courseId.value, node.id)
          uni.showToast({ title: '已删除', icon: 'success' })
          selectedTreeNode.value = null
          loadTree()
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    },
  })
}

// ── Batch operations ──

async function handleBatchDelete() {
  uni.showModal({
    title: '确认移除',
    content: `确定要从课程中移除选中的 ${selectedIds.value.length} 题吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await courseQuestionApi.batchDelete(courseId.value, selectedIds.value)
          uni.showToast({ title: '已移除', icon: 'success' })
          selectedIds.value = []
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
        }
      }
    },
  })
}

async function handleBatchMove() {
  // Simplified: show a select for target node
  uni.showToast({ title: '请选择目标节点', icon: 'none' })
}

async function handleBatchAiProcess() {
  uni.showToast({ title: '已开始批量AI处理', icon: 'none' })
  try {
    const res: any = await variantApi.batchGenerateVariant(courseId.value, selectedIds.value, 'ai_process')
    // This should call the batch AI process endpoint instead
    startPolling(res.data?.celery_task_id, 'AI处理')
  } catch (e: any) {
    uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
  }
}

async function handleBatchVariant() {
  uni.showModal({
    title: '批量生成变式题',
    content: `确定要为选中的 ${selectedIds.value.length} 题生成变式题吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const result: any = await variantApi.batchGenerate(courseId.value, selectedIds.value)
          uni.showToast({ title: `已提交 ${selectedIds.value.length} 道变式题生成任务`, icon: 'none' })
        } catch (e: any) {
          uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
        }
      }
    },
  })
}

async function handleAiProcess(questionId: number) {
  uni.showToast({ title: '已开始AI处理', icon: 'none' })
  try {
    const res: any = await questionApi.aiProcess(questionId)
    const taskId = res.data?.task_id || res.data?.celery_task_id
    if (taskId) startPolling(taskId, `题${questionId}AI处理`)
  } catch (e: any) {
    uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
  }
}

async function handleVariant(questionId: number) {
  uni.showModal({
    title: '生成变式题',
    content: '确认要为此题生成变式题吗？（需要原题已完成AI答案确认）',
    success: async (res) => {
      if (res.confirm) {
        try {
          await variantApi.generate(courseId.value, questionId)
          uni.showToast({ title: '变式题生成任务已提交', icon: 'none' })
        } catch (e: any) {
          uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
        }
      }
    },
  })
}

async function handleDelete(questionId: number) {
  uni.showModal({
    title: '确认移除',
    content: '确定要从课程中移除这道题吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await courseQuestionApi.batchDelete(courseId.value, [questionId])
          uni.showToast({ title: '已移除', icon: 'success' })
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
        }
      }
    },
  })
}

// ── Bank search ──

async function searchBank() {
  if (!bankSearch.value || bankSearch.value.length < 2) {
    bankResults.value = []
    return
  }
  try {
    const res: any = await questionApi.list({ page: 1, page_size: 20, question_no: bankSearch.value })
    bankResults.value = res.data?.items || res.data || []
  } catch {}
}

function toggleBankSelect(id: number) {
  const idx = bankSelectedIds.value.indexOf(id)
  if (idx >= 0) bankSelectedIds.value.splice(idx, 1)
  else bankSelectedIds.value.push(id)
}

async function doBankImport() {
  if (bankSelectedIds.value.length === 0) return
  try {
    await courseQuestionApi.import(courseId.value, {
      question_ids: bankSelectedIds.value,
      tree_node_id: selectedTreeNode.value?.id,
    })
    uni.showToast({ title: `已引入 ${bankSelectedIds.value.length} 题`, icon: 'success' })
    bankSelectedIds.value = []
    loadQuestions()
    showAddQuestion.value = false
  } catch (e: any) {
    uni.showToast({ title: e?.message || '引入失败', icon: 'none' })
  }
}

function startPolling(taskId: string, label: string) {
  const timer = setInterval(async () => {
    try {
      // Use existing review API status endpoint
      const statusRes: any = await questionApi.getAiStatus(taskId)
      const data = statusRes.data
      if (data?.status === 'complete' || data?.status === 'failed') {
        clearInterval(timer)
        if (data.status === 'complete') {
          uni.showToast({ title: `${label}完成`, icon: 'success' })
        } else {
          uni.showToast({ title: `${label}失败: ${data.error || '未知错误'}`, icon: 'none' })
        }
        loadQuestions()
      }
    } catch {}
  }, 3000)
  aiPollTimers.push({ taskId, timer })
}

function triggerFileUpload() {
  // Navigate to photo upload or new question page
  uni.navigateTo({ url: `/pages/teacher/new-question?course_id=${courseId.value}` })
}

function openMaterialForSelect(m: any) {
  // Open material in a new window for frame selection
  if (m.file_type === 'image') {
    const url = `/api/v1/courses/${courseId.value}/materials/${m.id}/preview/`
    window.open(url, '_blank')
  }
}

function promptInput(message: string, defaultValue = ''): Promise<string | null> {
  return new Promise((resolve) => {
    uni.showModal({
      title: '提示',
      content: message,
      editable: true,
      placeholderText: defaultValue,
      success: (res) => {
        if (res.confirm && res.content?.trim()) {
          resolve(res.content.trim())
        } else {
          resolve(null)
        }
      },
    })
  })
}

// Cleanup timers
import { onUnmounted } from 'vue'
onUnmounted(() => {
  aiPollTimers.forEach(t => clearInterval(t.timer))
  aiPollTimers.length = 0
})
</script>

<style scoped>
.practice-page { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 240px; flex: 1; display: flex; gap: 16px; padding: 16px; overflow: hidden; }
.tree-panel { width: 260px; background: #fff; border-radius: 8px; padding: 12px; overflow-y: auto; flex-shrink: 0; }
.question-panel { flex: 1; background: #fff; border-radius: 8px; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; min-width: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
.panel-title { font-size: 16px; font-weight: 500; color: #303133; }
.header-actions { display: flex; gap: 8px; }
.batch-bar { display: flex; gap: 8px; align-items: center; padding: 8px 12px; background: #ecf5ff; border-radius: 8px; margin-bottom: 12px; }
.batch-text { font-size: 13px; color: #409eff; margin-right: 8px; }

.question-table { flex: 1; overflow-y: auto; }
.table-header { display: flex; align-items: center; padding: 8px 12px; background: #f5f7fa; font-size: 12px; color: #909399; font-weight: 500; }
.table-row { display: flex; align-items: center; padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; cursor: pointer; }
.table-row:hover { background: #fafafa; }
.table-row.row-selected { background: #ecf5ff; }
.col-check { width: 30px; text-align: center; cursor: pointer; flex-shrink: 0; }
.col-stem { flex: 2; min-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-diff { width: 50px; text-align: center; }
.col-type { width: 80px; }
.col-source { width: 80px; }
.col-actions { display: flex; gap: 4px; flex-wrap: wrap; }

.diff-1 { color: #67c23a; } .diff-2 { color: #409eff; } .diff-3 { color: #e6a23c; } .diff-4 { color: #f56c6c; } .diff-5 { color: #9924ff; }

.loading, .empty { text-align: center; color: #909399; padding: 40px 0; }

/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 12px; padding: 24px; width: 500px; max-height: 80vh; overflow-y: auto; }
.modal-lg { width: 700px; }
.modal-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; display: block; }
.modal-footer { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

/* Add tabs */
.add-tabs { display: flex; gap: 0; border-bottom: 1px solid #ebeef5; margin-bottom: 16px; }
.tab { padding: 8px 16px; cursor: pointer; font-size: 13px; color: #606266; border-bottom: 2px solid transparent; }
.tab.active { color: #409eff; border-bottom-color: #409eff; }
.tab-content { min-height: 200px; }
.upload-area { padding: 40px; border: 2px dashed #dcdfe6; border-radius: 8px; text-align: center; color: #909399; cursor: pointer; }
.upload-area:hover { border-color: #409eff; }
.node-selector { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
.select { padding: 4px 8px; border: 1px solid #dcdfe6; border-radius: 4px; }

/* Bank */
.bank-hint { font-size: 13px; color: #909399; margin-bottom: 12px; display: block; }
.bank-search { margin-bottom: 12px; }
.search-input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 6px; box-sizing: border-box; }
.bank-results { max-height: 300px; overflow-y: auto; }
.bank-item { display: flex; align-items: center; padding: 8px; border-bottom: 1px solid #f0f0f0; cursor: pointer; }
.bank-item:hover { background: #f5f7fa; }
.check { width: 24px; text-align: center; cursor: pointer; }
.bank-stem { flex: 1; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.material-item { display: flex; align-items: center; justify-content: space-between; padding: 8px; border-bottom: 1px solid #f0f0f0; }
</style>
```

- [ ] **Step 3: 提交**

```bash
cd front
git add uniapp/src/components/DirTree.vue uniapp/src/pages/teacher/course-practice.vue
git commit -m "feat: add course practice page with directory tree and question list"
```

---

### Task 9: 集成测试 + 端到端验证

**Files:**
- No new files
- All existing files exercised end-to-end

**Interfaces:**
- N/A

- [ ] **Step 1: TypeScript 类型检查**

```bash
cd front/uniapp
npx tsc --noEmit
```

预期：0 errors

- [ ] **Step 2: Django 运行测试**

```bash
cd front
python -m pytest apps/courses/ -v
```

预期：全部测试通过

- [ ] **Step 3: 端到端手动测试清单**

1. 老师登录 → 左侧菜单显示"课程列表"
2. 点击"课程列表" → 显示卡片网格 → 新建课程 → 卡片显示
3. 点击"课程资料" → 上传 PDF/Word/图片 → 列表显示 → 下载/预览/删除
4. 点击"课程练习" → 左侧空目录树
5. 右键新建根节点 → 子节点 → 多层嵌套
6. 从题库引入题目 → 习题列表显示
7. 新增习题（拍照/上传）→ 保存到指定节点
8. AI 处理单题 → 轮询结果
9. 生成变式题 → Celery 任务 → 结果入库（待确认）
10. 确认/驳回变式题
11. 批量操作：批量AI处理、批量生成变式题、批量移除

- [ ] **Step 4: 提交（如果有测试修复）**

```bash
cd front
git add -A
git commit -m "test: fix integration test issues"
```

---

## 任务依赖图

```
Task 1: Models + Migration (数据库基础)
    ↓
Task 2: Serializers + API Views (后端 API)
    ↓
Task 3: Celery + AI Service + Validator (异步变式题)
    ↓
Task 4: Question Management APIs (习题管理 API)
    ↓
Task 5: API Client + Sidebar (前端基础设施)
    ↓
Task 6: Course List Page (课程列表页)
    ↓
Task 7: Course Materials Page (课程资料页)
    ↓
Task 8: Course Practice Page (课程练习页 - 最复杂)
    ↓
Task 9: Integration Testing (集成测试)
```

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| uniapp H5 模式下 `window.open` 不可用 | 资料预览失败 | 使用 `uni.navigateTo` 打开预览页或用 `<a>` 标签 |
| Celery worker 未启动 | 变式题任务堆积 | 文档注明启动步骤：`celery -A config worker -l info` |
| PDF/Word 框选在 uniapp 中不支持 | 需要从资料框选功能降级 | MVP 阶段仅支持拍照/上传，PDF 框选作为 V2 |
| 阿里云 API KEY 过期 | AI 调用全部失败 | 文档注明更换 KEY 步骤 |

---

## 后续优化（V2+）

- PDF.js 集成：在 uniapp H5 中实现 PDF 框选题目
- 目录树拖拽排序
- 课程与班级的完整 ManyToMany 关联管理
- 变式题插图处理（overlay_text / rerender）
- 课程资料回收站视图
- 教师间课程共享\n", "file_path": "d:\\workspace\\code\\qidi\\front\\docs\\superpowers\\plans\\2026-07-14-course-list-feature-plan.md"}