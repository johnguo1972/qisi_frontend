# 文档审查报告 — Bug、错误与遗漏清单

> **审查日期**: 2026-07-27 | **审查范围**: 8份方案文档全部交叉验证

---

## 审查结果汇总

| 严重程度 | 数量 | 说明 |
|----------|------|------|
| 🔴 严重Bug | 4 | 会导致代码无法运行 |
| 🟡 重要遗漏 | 5 | 会导致前后端联调失败 |
| 🟢 改进建议 | 4 | 不影响功能但影响体验 |

---

## 🔴 严重Bug（必须修复）

### Bug #1: ImportModal.vue 中 `emit` 未定义就使用

**位置**: `02_前端实现代码.md` 第1290-1307行

**问题**: `onJsonChange` 函数（1303行）使用了 `emit()`，但 `const emit = defineEmits(...)` 在1307行才声明。且1277行和1307行有**两次** `defineEmits` 调用。

**影响**: 代码运行时报 `emit is not defined`

**修复**:
```vue
<script setup lang="ts">
import { ref } from 'vue'

// ✅ 修复: 只保留一次 defineEmits，放在最前面
const emit = defineEmits(['close', 'photo-import', 'file-import', 'json-import'])

const fileInputRef = ref<HTMLInputElement>()
const jsonInputRef = ref<HTMLInputElement>()

function selectFile() { fileInputRef.value?.click() }
function selectJson() { jsonInputRef.value?.click() }

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    emit('file-import', file)  // ✅ 通过emit传递文件
  }
}

function onJsonChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) {
    emit('json-import', file)
  }
}
// ❌ 删除重复的 defineEmits 行
</script>
```

---

### Bug #2: `importJsonPackage` 在非H5平台无法工作

**位置**: `02_前端实现代码.md` 第1417-1440行 + `01_完整实现方案.md` 第428-455行

**问题**: APP端的 `uni.uploadFile` 使用了 `(formData as any).__file_path__`，但 `FormData` 对象没有 `__file_path__` 属性。

**影响**: APP端JSON导入完全无法工作

**修复**:
```typescript
export function importJsonPackage(file: File) {
  return new Promise<any>((resolve, reject) => {
    const token = uni.getStorageSync('accessToken')

    // #ifdef H5
    const formData = new FormData()
    formData.append('file', file)
    fetch(`${UPLOAD_BASE}/questions/import-json-package`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    })
      .then(res => res.json())
      .then(data => data.code === 0 ? resolve(data) : reject(new Error(data.message || '导入失败')))
      .catch(reject)
    // #endif

    // #ifndef H5
    // APP端: 需要将 File 转为临时文件路径
    // 方案: 将 blob 写入临时文件，再用 uni.uploadFile
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result as string
      // 使用 uni.saveFile 或写入临时目录
      // H5环境通常不需要此分支
      reject(new Error('APP端暂不支持JSON导入，请在H5端使用'))
    }
    reader.readAsArrayBuffer(file)
    // #endif
  })
}
```

---

### Bug #3: 01文档的json_import_views.py 缺少 `shutil` 导入

**位置**: `01_完整实现方案.md` 第649行附近（json_import_views.py）

**问题**: 代码使用了 `shutil.rmtree` 和 `shutil.copy2`，但 import 列表中只有 `zipfile`，没有 `shutil`。

**影响**: 运行时报 `NameError: name 'shutil' is not defined`

**修复**: 在文件头部添加 `import shutil`

```python
import os
import json
import uuid
import zipfile
import shutil    # ✅ 添加此行
import logging
```

**注**: `03_后端实现代码.md` 中的版本已正确包含 `import shutil`，两个文档不一致。

---

### Bug #4: basket路由与question_detail路由冲突

**位置**: `03_后端实现代码.md` 第596-623行

**问题**: `basket/<str:question_id>/` 和 `<int:question_id>` 在同一 urlpatterns 中，但 basket 路由在 question_id 路由**之后**注册。Django按顺序匹配，`<int:question_id>` 会先匹配到 `basket` 等字符串导致404。

实际上更严重的问题是：`basket/<str:question_id>/` 的路径模式可能与未来的路由冲突。

**影响**: basket的remove路由可能无法正确匹配

**修复**: 将 basket 路由放在 `<int:question_id>` 之前：

```python
urlpatterns = [
    # 现有路由
    path('', question_views.question_list, name='question-list'),
    path('create/', create_views.create_question, name='create-question'),
    ...

    # ✅ 新增路由放在 <int:question_id> 之前
    # 标签管理
    path('tags/', tag_views.tag_list, name='tag-list'),
    path('tags/create/', tag_views.tag_create, name='tag-create'),

    # JSON导入
    path('import-json-package', json_import_views.import_json_package, name='import-json-package'),
    path('import-json-task/<str:task_id>/status/', json_import_views.import_json_task_status, name='import-json-task-status'),
    path('json-import-history/', json_import_views.json_import_history, name='json-import-history'),

    # 篮子
    path('basket/', basket_views.basket_list, name='basket-list'),
    path('basket/add/', basket_views.basket_add, name='basket-add'),
    path('basket/<str:question_id>/', basket_views.basket_remove, name='basket-remove'),
    path('basket/clear/', basket_views.basket_clear, name='basket-clear'),

    # 条形码
    path('<str:question_id>/barcode/', barcode_views.question_barcode, name='question-barcode'),
    path('barcode/scan/', barcode_views.barcode_scan, name='barcode-scan'),

    # 批量操作
    path('batch-update/', batch_views.batch_update, name='batch-update'),

    # ️ 这些必须放在最后（通配路由）
    path('<int:question_id>', question_views.question_detail, name='question-detail'),
    path('<int:question_id>/publish', question_views.question_publish, name='question-publish'),
    path('<str:question_id>/tags/', tag_views.question_tags, name='question-tags'),
    path('<str:question_id>/tags/add/', tag_views.question_add_tag, name='question-add-tag'),
    path('<str:question_id>/tags/<str:tag_id>/remove/', tag_views.question_remove_tag, name='question-remove-tag'),
]
```

---

##  重要遗漏（影响联调）

### 遗漏 #1: AddMenuModal.vue 组件未提供代码

**位置**: 所有文档

**问题**: `question-bank.vue` 中 import 并使用了 `AddMenuModal`，但没有任何文档提供该组件的代码。

**影响**: 前端开发时该组件缺失

**修复**: 需要在 `02_前端实现代码.md` 中补充 `AddMenuModal.vue` 组件代码（参见下方补充代码）

---

### 遗漏 #2: RightActionPanel.vue 组件未提供代码

**位置**: 所有文档

**问题**: `question-bank.vue` 模板中使用了 `RightActionPanel`，但没有提供任何文档中的实现代码。

**影响**: 右侧操作面板无法实现

**修复**: 需要在 `02_前端实现代码.md` 中补充 `RightActionPanel.vue` 组件代码

---

### 遗漏 #3: 题目列表API不返回图片和选项数据

**位置**: `01_完整实现方案.md` 附录A + 现有 `QuestionListSerializer`

**问题**: 前端 `QuestionDetailCard` 需要 `question.images` 和 `question.options` 来展示图片和选项，但现有 `question_views.question_list` API 使用的 `QuestionListSerializer` 不包含这些字段。前端会显示空图片和空选项。

**影响**: 题目卡片无图片、无选项

**修复**: 需要扩展 `QuestionListSerializer` 或在前端对每道题单独请求详情

**方案A（推荐）**: 扩展序列化器
```python
class QuestionListSerializer(serializers.ModelSerializer):
    # ... 现有字段 ...
    images = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    tags = serializers.JSONField(required=False, default=list)
    source_collection = serializers.CharField(required=False, default='')
    creator_name = serializers.CharField(required=False, default='')
    collected_at = serializers.DateTimeField(required=False)

    class Meta:
        model = ExamQuestion
        fields = [
            # ... 现有字段 ...
            'images', 'options', 'tags', 'source_collection',
            'creator_name', 'collected_at',
        ]

    def get_images(self, obj):
        return [
            {'file_path': img.file_path, 'description': img.description, 'image_type': img.image_type}
            for img in obj.images.all()[:5]  # 最多5张
        ]

    def get_options(self, obj):
        return [
            {'label': opt.option_label, 'content': opt.content}
            for opt in obj.options.all()
        ]
```

**方案B**: 前端额外请求（不推荐，N+1问题）

---

### 遗漏 #4: 标签API路由未注册到urls.py

**位置**: `06_补充实现方案_标签_知识点_ID_条形码.md`

**问题**: `06` 文档中提供了 `tag_views.py` 代码和API端点列表，但**没有提供**将这些路由注册到 `apps/study/urls.py` 的完整代码。

**影响**: 标签API无法访问

**修复**: 需要在 `urls.py` 中添加（已在Bug #4的修复中一并解决）

---

### 遗漏 #5: 前端标签API封装缺失

**位置**: `02_前端实现代码.md`

**问题**: `06` 文档提供了标签后端API，但 `02` 文档中的 `questions.ts` 没有封装标签相关的API函数（获取标签列表、创建标签、添加/移除题目标签等）。

**影响**: 前端无法调用标签API

**修复**: 需要在 `questions.ts` 中添加：
```typescript
// === 标签管理 ===
export function getTagList(params?: { search?: string }) {
  return get<any>('/questions/tags/', params)
}

export function createTag(data: { name: string; color?: string }) {
  return post<any>('/questions/tags/create/', data)
}

export function updateTag(tagId: string, data: { name?: string; color?: string }) {
  return put<any>(`/questions/tags/${tagId}/update/`, data)
}

export function deleteTag(tagId: string) {
  return del(`/questions/tags/${tagId}/delete/`)
}

export function getQuestionTags(questionId: string) {
  return get<any>(`/questions/${questionId}/tags/`)
}

export function addQuestionTag(questionId: string, data: { tag_id?: string; tag_name?: string }) {
  return post<any>(`/questions/${questionId}/tags/add/`, data)
}

export function removeQuestionTag(questionId: string, tagId: string) {
  return del(`/questions/${questionId}/tags/${tagId}/remove/`)
}

// === 条形码 ===
export function getQuestionBarcode(questionId: string) {
  return `${UPLOAD_BASE}/questions/${questionId}/barcode/`  // 返回图片URL
}

export function scanBarcode(barcodeData: string) {
  return post<any>('/questions/barcode/scan/', { barcode_data: barcodeData })
}
```

---

## 🟢 改进建议

### 建议 #1: JSON导入临时文件未清理

**位置**: `01_完整实现方案.md` 第727行

**问题**: `finally` 块中的 `shutil.rmtree` 被注释掉了，临时文件会累积。

**建议**: 取消注释，或改为异步清理
```python
finally:
    shutil.rmtree(temp_dir, ignore_errors=True)  # ✅ 取消注释
```

---

### 建议 #2: 题目详情页需要返回标签数据

**位置**: `QuestionDetailSerializer`

**问题**: 编辑题目时需要看到当前标签，但 `QuestionDetailSerializer` 不包含 `tags` 字段。

**建议**: 添加 `tags` 到序列化器字段列表

---

### 建议 #3: `handleFileImport` 跳转逻辑不完整

**位置**: `02_前端实现代码.md` 第458-462行

**问题**: `handleFileImport` 只跳转到import页面，没有传递文件。用户在ImportModal中选了文件，结果跳过去后还要重新选。

**建议**: 两种方案：
- 方案A: 在ImportModal中直接上传文件（推荐）
- 方案B: 通过路由参数传递文件名

---

### 建议 #4: 文档间版本不一致

**问题**:
- `01` 文档的 `json_import_views.py` 缺少 `import shutil`
- `03` 文档的同一文件有 `import shutil`
- `01` 文档的 `QUESTION_TYPE_MAP` 中 `'solution': 'solution'`，而 `03` 文档中是 `'solution': 'short_answer'`

**建议**: 以 `03` 文档为准（03更详细更准确），统一所有文档

---

## 补充代码

### AddMenuModal.vue（遗漏组件）

```vue
<template>
  <view class="modal-overlay" @click.self="$emit('close')">
    <view class="modal-content">
      <view class="modal-header">
        <text class="modal-title">新增题目</text>
        <text class="modal-close" @click="$emit('close')">×</text>
      </view>
      <view class="modal-body">
        <view class="menu-item" @click="$emit('photo')">
          <text class="menu-icon"></text>
          <view class="menu-info">
            <text class="menu-name">拍照识别</text>
            <text class="menu-desc">拍照或选图，AI自动识别</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('file')">
          <text class="menu-icon"></text>
          <view class="menu-info">
            <text class="menu-name">PDF/Word导入</text>
            <text class="menu-desc">上传文档自动解析</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('json')">
          <text class="menu-icon"></text>
          <view class="menu-info">
            <text class="menu-name">JSON数据包导入</text>
            <text class="menu-desc">上传ZIP压缩包批量导入</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('manual')">
          <text class="menu-icon">️</text>
          <view class="menu-info">
            <text class="menu-name">手动创建</text>
            <text class="menu-desc">手动填写题目信息</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineEmits(['close', 'photo', 'file', 'json', 'manual'])
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #fff; border-radius: 12px;
  width: 400px; max-width: 90vw; overflow: hidden;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #f0f0f0;
}
.modal-title { font-size: 16px; font-weight: 600; color: #303133; }
.modal-close { font-size: 24px; color: #909399; cursor: pointer; }
.modal-body { padding: 8px 0; }
.menu-item {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px; cursor: pointer;
}
.menu-item:hover { background: #f5f7fa; }
.menu-icon { font-size: 24px; }
.menu-info { flex: 1; }
.menu-name { font-size: 14px; font-weight: 500; color: #303133; display: block; }
.menu-desc { font-size: 12px; color: #909399; display: block; margin-top: 2px; }
</style>
```

### RightActionPanel.vue（遗漏组件）

```vue
<template>
  <view class="right-panel">
    <button class="action-btn btn-primary" @click="$emit('random')">随机选题</button>
    <button class="action-btn" @click="$emit('query-params')">查询参数</button>
    <button class="action-btn" @click="$emit('refresh')">刷新题目</button>
    <button class="action-btn btn-success" @click="$emit('toggle-answer')">
      {{ allShown ? '关闭答案' : '显示答案' }}
    </button>
    <button class="action-btn" @click="$emit('share-multiple')">分享多题</button>
    <button class="action-btn" @click="$emit('share-history')">分享历史</button>
    <button class="action-btn btn-warning" @click="$emit('basket')">加入篮子</button>
    <view class="basket-count" v-if="basketCount > 0">
      🗑 篮子: {{ basketCount }}题
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  basketCount?: number
  allShown?: boolean
}>()

defineEmits(['random', 'query-params', 'refresh', 'toggle-answer', 'share-multiple', 'share-history', 'basket'])
</script>

<style scoped>
.right-panel {
  width: 160px; background: #fff;
  border-left: 1px solid #e4e7ed;
  padding: 16px 12px;
  display: flex; flex-direction: column; gap: 10px;
  flex-shrink: 0;
}
.action-btn {
  width: 100%; padding: 10px; border-radius: 6px;
  font-size: 13px; border: 1px solid #dcdfe6;
  background: #fff; color: #606266; cursor: pointer;
}
.action-btn:hover { background: #f5f7fa; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-success { background: #67c23a; color: #fff; border-color: #67c23a; }
.btn-warning { background: #e6a23c; color: #fff; border-color: #e6a23c; }
.basket-count {
  font-size: 12px; color: #409eff; text-align: center;
  padding: 6px; background: #ecf5ff; border-radius: 4px;
}
</style>
```

---

## 修复优先级

| 优先级 | 修复项 | 负责 |
|--------|--------|------|
| **P0 立即修复** | Bug #1-4 | 前端/后端 |
| **P0 立即修复** | 遗漏 #1-2（补充组件代码） | 前端 |
| **P0 立即修复** | 遗漏 #3-5（API联调） | 前后端 |
| **P1 开发时修复** | 建议 #1-4 | 开发中 |

---

## 真实数据推演发现的新问题（2026-07-27 补充）

使用 `深圳中学共同体八年级物理期中试题_JSON解析` 真实数据推演后，额外发现以下问题并已修复：

| # | 严重程度 | 问题 | 影响 | 修复状态 | 修复文档 |
|---|----------|------|------|----------|----------|
| 5 |  严重 | `QUESTION_TYPE_MAP` 缺少 `calculation`/`experiment`/`reading_comprehension` | 5道题题型变为unknown | ✅ 已修复 | 01 + 03 |
| 6 | 🔴 严重 | `ExamPaper.subject` 传字母代码导致 `paper_code` 生成失败（X80001） | 试卷编号错误 | ✅ 已修复 | 01 + 03 |
| 7 |  重要 | `generate_question_system_id` 收到中文subject导致计数器key不一致 | 题目编号可能重复 | ✅ 已修复 | 01 + 03 |
| 8 |  低 | 填空题 `answer.normalized` 结构化数据丢失 | 只存raw字符串 | 后续增强 | — |

### 问题6详细分析

```
代码: ExamPaper.objects.create(subject='P', ...)  ← 字母代码
Signal: pre_save → generate_paper_code('P', '八年级')
内部: SUBJECT_FIRST_LETTER.get('P', 'X') → 'X'  ← key是中文'物理'，不是'P'
结果: paper_code = 'X80001'  ←  错误！应该是 'P80001'
```

**修复**: `ExamPaper.objects.create(subject='物理', ...)` ← 存中文名称
- signal 中 `SUBJECT_FIRST_LETTER.get('物理')` → `'P'` ✅
- `grade_char`: `GRADE_CHAR_MAP['八年级']` → `'8'` ✅
- 最终 `paper_code = 'P80001'` ✅

### 问题7详细分析

```
修复后 paper.subject = '物理'
system_id = generate_question_system_id('物理')
→ _resolve_subject_letter('物理') → 'P'  ← 字母前缀正确 ✅
→ QuestionIDCounter.get_or_create(subject='物理', ...)  ← 但counter的subject是中文
→ 与现有 counter(subject='P') 不一致 → 可能重复编号
```

**修复**: `generate_question_system_id(SUBJECT_MAP.get(paper.subject, 'P'))`
- `SUBJECT_MAP.get('物理')` → `'P'`
- `QuestionIDCounter.get_or_create(subject='P', ...)` ✅ 与现有数据一致
