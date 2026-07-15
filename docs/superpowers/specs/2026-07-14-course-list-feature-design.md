# 课程列表功能 - 设计文档

**日期**: 2026-07-14  
**范围**: 仅限 `./front` 目录，不修改 backend/miniprogram  
**技术栈**: Django + uniapp (H5) + Celery + MySQL  
**AI 模型**: qwen3.7-flash, qwen3.7-plus, deepseek-v4-pro（复用同一阿里云 API KEY/URL）

---

## 1. 需求概述

为教师端新增"课程列表"一级功能菜单，包含三大子模块：

| 子模块 | 说明 |
|--------|------|
| 课程列表 | 卡片式展示课程，支持增删，每张卡片含"课程资料"和"课程练习"入口 |
| 课程资料 | 文件上传/下载/预览/软删除（支持 PDF/Word/图片，存储于本地 media/） |
| 课程练习 | 左侧自定义多级目录树 + 右侧习题列表，支持新增/编辑/AI处理/变式题生成 |

**核心约束**：
- 课程是班级的上层概念，一个课程可关联多个班级，跨班级共享
- 课程练习目录树完全由用户自定义（任意层级和名称），与知识树无关
- 习题双向打通：课程中创建的题目在题库列表可见，题库中的题目可引入课程
- 变式题生成后直接入库，标记"待确认"，老师可手动确认/驳回
- 变式题以初中物理为核心实现，架构保留其他学科扩展能力

---

## 2. 总体架构

### 2.1 后端结构

```
apps/courses/
├── models.py          # Course, CourseMaterial, CourseTree, CourseQuestionLink, VariantTask
├── views.py           # REST API Views
├── serializers.py     # DRF Serializers
├── urls.py            # URL 路由
├── ai_service.py      # 变式题 AI 服务（qwen3.7 + deepseek）
├── validator.py       # 变式题程序化校验器
├── tasks.py           # Celery 异步变式题任务
├── prompts.py         # 变式题 System Prompt 模板
├── apps.py            # Django app config
└── __init__.py
```

### 2.2 前端结构

```
uniapp/src/
├── pages/teacher/
│   ├── course-list.vue       # 课程卡片列表
│   ├── course-materials.vue  # 课程资料管理
│   └── course-practice.vue   # 课程练习（目录树 + 习题列表）
├── components/
│   ├── CourseCard.vue        # 课程卡片组件
│   └── DirTree.vue           # 可编辑目录树（右键菜单）
├── api/
│   └── courses.ts            # 课程 API 封装
└── components/
    └── TeacherSidebar.vue    # 修改：新增"课程列表"菜单项
```

### 2.3 数据流

```
课程卡片列表
├── "课程资料" → 文件上传/下载/预览/软删除
└── "课程练习" → 左侧 DirTree + 右侧 QuestionList
      ├── 新增习题 → 拍照/上传/PDF框选/Word框选 → qwen3.7-plus 识别 → 指定节点保存
      ├── AI处理 → qwen3.7-flash/plus → Celery 异步 → 轮询结果
      └── 变式题 → 原题确认后 → Celery → qwen3.7-plus 生成 → deepseek 验证 → 待确认入库
```

---

## 3. 数据库模型

### 3.1 Course 表

```python
class Course(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200)           # "26年物理9年级S班课程"
    description = models.TextField(null=True)          # 课程介绍
    subject = models.CharField(max_length=50)          # math/physics
    grade_level = models.CharField(max_length=50)      # 七年级/八年级/九年级
    cover_image = models.CharField(max_length=500, null=True)
    teacher = models.ForeignKey(UserAccount, on_delete=models.PROTECT)
    classes = models.ManyToManyField('institutions.Class', blank=True)
    is_deleted = models.BooleanField(default=False)    # 软删除
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course'
```

### 3.2 CourseMaterial 表

```python
class CourseMaterial(models.Model):
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    name = models.CharField(max_length=255)            # 文件名
    file_path = models.CharField(max_length=500)       # media/courses/{id}/filename
    file_type = models.CharField(max_length=20)        # pdf/word/image
    file_size = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)    # 软删除
    uploaded_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_material'
```

### 3.3 CourseTree 表

```python
class CourseTree(models.Model):
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='tree_nodes')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    name = models.CharField(max_length=200)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_tree'
        ordering = ['sort_order']
```

### 3.4 CourseQuestionLink 表

```python
class CourseQuestionLink(models.Model):
    SOURCE_CHOICES = [
        ('created_in_course', '课程中创建'),
        ('imported_from_bank', '从题库引入'),
    ]
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    tree_node = models.ForeignKey(CourseTree, on_delete=models.SET_NULL, null=True, blank=True)
    question = models.ForeignKey('parser.ExamQuestion', on_delete=models.CASCADE)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    source_course_name = models.CharField(max_length=200, null=True)
    is_deleted = models.BooleanField(default=False)    # 软删除（仅移除关联）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_question_link'
        unique_together = ('course', 'question')
```

### 3.5 VariantTask 表

```python
class VariantTask(models.Model):
    STATUS_CHOICES = [
        ('pending', '待处理'), ('running', '处理中'),
        ('success', '成功'), ('failed', '失败'),
    ]
    id = models.BigAutoField(primary_key=True)
    original_question = models.ForeignKey('parser.ExamQuestion', on_delete=models.CASCADE)
    variant_mode = models.CharField(max_length=30)     # numeric_change/condition_change/context_change/mixed_light
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    generator_result = models.JSONField(null=True)     # qwen3.7-plus 生成结果
    verifier_result = models.JSONField(null=True)      # deepseek v4 pro 验证结果
    generated_question = models.JSONField(null=True)   # 最终结构化题目
    error_message = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        db_table = 'course_variant_task'
```

---

## 4. API 端点

### 4.1 课程管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses/` | 课程列表（卡片数据） |
| POST | `/api/courses/` | 创建课程 |
| GET | `/api/courses/{id}/` | 课程详情 |
| PUT | `/api/courses/{id}/` | 修改课程 |
| DELETE | `/api/courses/{id}/` | 软删除课程 |

### 4.2 课程资料

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses/{id}/materials/` | 资料列表（排除软删除） |
| POST | `/api/courses/{id}/materials/upload/` | 上传资料文件 |
| GET | `/api/courses/{id}/materials/{mid}/download/` | 下载资料 |
| GET | `/api/courses/{id}/materials/{mid}/preview/` | 预览资料 |
| DELETE | `/api/courses/{id}/materials/{mid}/` | 软删除资料 |

### 4.3 课程目录树

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses/{id}/tree/` | 获取目录树（嵌套结构） |
| POST | `/api/courses/{id}/tree/` | 新增节点 |
| PUT | `/api/courses/{id}/tree/{nid}/` | 修改节点 |
| DELETE | `/api/courses/{id}/tree/{nid}/` | 删除节点（含子节点） |
| PUT | `/api/courses/{id}/tree/{nid}/move/` | 移动节点 |

### 4.4 课程习题

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/courses/{id}/questions/` | 习题列表（按 tree_node 筛选） |
| POST | `/api/courses/{id}/questions/import/` | 从题库引入习题 |
| POST | `/api/courses/{id}/questions/batch-delete/` | 批量从课程移除 |
| POST | `/api/courses/{id}/questions/batch-move/` | 批量移动所属节点 |
| POST | `/api/courses/{id}/questions/ai-process/` | AI处理（qwen3.7） |
| POST | `/api/courses/{id}/questions/batch-ai-process/` | 批量AI处理 |
| POST | `/api/courses/{id}/questions/{qid}/ai-confirm/` | AI答案确认 |
| POST | `/api/courses/{id}/questions/box-select-recognize/` | 框选AI识别 |

### 4.5 变式题

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/courses/{id}/questions/{qid}/generate-variant/` | 发起变式题任务 |
| POST | `/api/courses/{id}/questions/batch-generate-variant/` | 批量生成变式题 |
| GET | `/api/courses/{id}/variant-tasks/{vtid}/` | 查询任务状态 |
| POST | `/api/courses/{id}/variant-tasks/{vtid}/confirm/` | 确认入库 |
| POST | `/api/courses/{id}/variant-tasks/{vtid}/reject/` | 驳回 |

---

## 5. 前端页面

### 5.1 课程列表页 (course-list.vue)

- 卡片网格布局（每行 3 张）
- 卡片内容：名称、学科、年级、简介、关联班级数
- 卡片操作：「课程资料」「课程练习」按钮 + 删除图标
- 新建课程弹窗：名称/学科/年级/简介

### 5.2 课程资料页 (course-materials.vue)

- 文件列表表格：文件名 | 类型 | 大小 | 上传时间 | 操作
- 上传：支持 PDF/Word/图片
- 下载：触发浏览器下载
- 预览：图片直出，PDF/Word 新窗口
- 删除：软删除

### 5.3 课程练习页 (course-practice.vue)

**三栏布局**：

| 左侧 (240px) | 中间 (flex) | 右侧 (可选) |
|---|---|---|
| DirTree 目录树 | 习题列表 + 批量操作栏 | 新增习题面板 |

**DirTree 组件**：
- 多级展开/折叠
- 右键菜单：新增下级、重命名、删除、移动

**习题列表**（复用 bank.vue 样式）：
- 多选框 + 批量操作
- 操作列：删除/移动节点/编辑/生成变式题/AI处理/AI答案确认
- 右上方按钮：新增习题 | 批量AI处理 | 批量生成变式题

**新增习题面板**：
- 选项卡 1：拍照/上传图片（复用 new-question.vue 流程）
- 选项卡 2：从课程资料选 PDF/Word → PDF.js 渲染框选 → qwen3.7-plus 识别 → 指定节点保存
- 选项卡 3：从题库引入 → 搜索筛选 → 批量关联

### 5.4 TeacherSidebar 修改

在"班级管理"前新增"课程列表"一级菜单项，图标使用 `&#127891;`（毕业帽）。

### 5.5 H5 条件编译优化

```vue
<!-- #ifdef H5 -->
<!-- 教师端使用更宽布局 -->
<!-- #endif -->
```

---

## 6. AI 处理与变式题生成

### 6.1 AI 模型配置 (.env 新增)

```
AI_MODEL_QWEN_37_FLASH=qwen3.7-flash
AI_MODEL_QWEN_37_PLUS=qwen3.7-plus
DEEPSEEK_MODEL=deepseek-v4-pro
```

复用现有 `QWEN_API_KEY`。

### 6.2 变式题 5 步流程

1. **完整性检查**：获取原题完整信息，缺项自动调用 qwen3.7-plus 补全
2. **生成**：qwen3.7-plus + 固定 System Prompt（缓存）+ 动态 User Prompt → 结构化 JSON
3. **程序校验**：JSON 合法性、知识点保持、题型保持、答案数量、单位、数值范围、图片依赖
4. **验证**：deepseek v4 pro 验证 → 通过/不通过 + 原因
5. **结果处理**：通过 → 保存 ExamQuestion（review_status='need_review'）；失败 → 重试一次

### 6.3 Celery 异步任务

```python
# apps/courses/tasks.py
@app.task(bind=True, max_retries=2)
def generate_variant_task(self, question_id, variant_mode, tree_node_id):
    # 1. 获取原题 + 完整性检查
    # 2. qwen3.7-plus 生成
    # 3. 程序化校验
    # 4. deepseek v4 pro 验证
    # 5. 保存到 VariantTask + ExamQuestion
    pass

@app.task(bind=True, max_retries=2)
def batch_generate_variants_task(self, question_ids, variant_mode, tree_node_id):
    for qid in question_ids:
        generate_variant_task.delay(qid, variant_mode, tree_node_id)
```

### 6.4 模型路由策略

| 题目类型 | 生成模型 | 验证策略 |
|---------|---------|---------|
| 简单数值题 | qwen3.7-flash | 程序复算 |
| 普通概念题 | qwen3.7-flash | 规则校验 |
| 复杂电路/浮力 | qwen3.7-plus | 程序 + deepseek 验证 |
| 实验/复杂插图 | qwen3.7-plus | 程序 + deepseek 验证 |
| 校验失败重试 | qwen3.7-plus | deepseek 验证 |

### 6.5 变式题失败状态码

```python
FAILURE_CODES = {
    'INSUFFICIENT_DATA': '原题信息不完整',
    'FIGURE_NOT_EDITABLE': '插图参与解题但无法安全修改',
    'VALIDATION_FAILED': '程序校验未通过',
    'VERIFIER_REJECTED': '验证模型判定不合格',
    'MODEL_ERROR': 'AI 模型调用失败',
    'OUT_OF_SCOPE': '超出初中课程范围',
}
```

### 6.6 程序化校验器 (validator.py)

```python
class VariantValidator:
    def validate(self, variant_json, original_question):
        errors = []
        self._check_json_schema(variant_json, errors)
        self._check_knowledge_preserved(variant_json, original_question, errors)
        self._check_question_type(variant_json, original_question, errors)
        self._check_answer_count(variant_json, original_question, errors)
        self._check_units(variant_json, errors)
        self._check_value_ranges(variant_json, errors)
        self._check_figure_consistency(variant_json, original_question, errors)
        return errors  # 空列表 = 通过
```

---

## 7. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 网络请求超时 | toast 提示 + 重试按钮 |
| 文件上传过大 (>50MB) | 前端拦截提示 |
| PDF/Word 解析失败 | 显示错误详情 + 重新上传 |
| AI 处理失败 | 显示具体错误码 + 重试 |
| 变式题生成失败 | 显示失败原因 + 降级人工审核 |
| 目录树节点有子题删除 | 确认弹窗 |
| AI 模型调用失败 | 指数退避重试 3 次 → failed |
| deepseek 验证超时 | 降级程序校验 + 人工确认 |

---

## 8. 权限控制

- 仅课程创建者可管理该课程
- 学生不可见课程相关页面
- 班级关联的老师可浏览但不可编辑

---

## 9. 软删除恢复

- 课程资料删除后可在"回收站"查看和恢复
- 课程删除后可在管理员后台恢复
- 习题从课程中移除 ≠ 删除题目本身

---

## 10. 约束与约定

- **修改范围**：仅限 `./front` 目录
- **数据库**：PostgreSQL（与现有保持一致）
- **文件存储**：Django `media/` 目录
- **AI 服务**：复用同一阿里云 API KEY 和 URL
- **通信语言**：中文
