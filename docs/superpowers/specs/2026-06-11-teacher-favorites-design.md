# 教师端题库管理与我的精选功能设计文档

**日期**: 2026-06-11
**状态**: 待实施

## 1. 需求概述

在 uni-app 教师端（`./front/uniapp`）中，对左侧菜单和页面进行以下改造：

1. 左侧菜单"题库导入"更名为"题库管理"
2. 题库管理下新增"我的精选"子功能
3. 题库管理界面：左侧知识点树 + 右侧题目列表
4. 我的精选界面：显示已精选的试题列表
5. 后端（tiku Django）新增精选模型、API 端点、教师学段字段

## 2. 需求明细

### 2.1 左侧菜单结构

修改所有 teacher 页面的 sidebar：
- "题库导入" → "题库管理"
- 题库管理下新增子项：题库列表（默认）、我的精选
- 点击"题库列表"跳转到 `bank.vue`
- 点击"我的精选"跳转到 `favorites.vue`

### 2.2 题库列表页（`bank.vue`）

**左侧 — 知识点树**：
- 按教师所教科目 + 学段过滤
- 层级结构：年级 → 学期 → 知识点
- 知识点名称右侧显示题目数量 `(N)`
- 点击知识点，右侧加载对应题目列表

**右侧 — 题目列表**：
- 表格列：题目编号 | 来源（试卷名称） | 难度 | 知识点数量 | 练习次数 | 出错次数 | 操作
- 练习次数和出错次数初始为 0，后续有学生数据后自动更新
- "操作"列显示"加入精选"按钮
- 点击"加入精选"调用 `POST /api/v1/teacher/favorites`，成功后按钮变为"已精选"（灰色不可点击）

### 2.3 我的精选页（`favorites.vue`）

- 无知识点树，纯表格
- 列：题目编号 | 来源 | 难度 | 知识点数量 | 操作
- "操作"列显示"取消精选"按钮
- 点击"取消精选"调用 `DELETE /api/v1/teacher/favorites/{id}`

### 2.4 后端新增（tiku Django）

**教师学段字段**：
- 在教师模型中新增 `stage` 字段（CharField: '小学'/'初中'/'高中'）
- 管理员新增/编辑教师时可设置

**精选模型**：
```python
class TeacherFavorite(models.Model):
    id = BigAutoField
    user = ForeignKey(User, related_name='favorites')
    question = ForeignKey(ExamQuestion, related_name='favorited_by')
    created_at = DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['user', 'question']]
        db_table = 'tiku_teacher_favorite'
```

**新增 API 端点**（`apps/review/urls.py` 或新 app）：
- `GET /api/v1/teacher/favorites` — 获取当前教师的精选列表
- `POST /api/v1/teacher/favorites` — 加入精选（body: `{question_id}`）
- `DELETE /api/v1/teacher/favorites/{id}` — 取消精选
- `GET /api/v1/teacher/knowledge-tree` — 获取知识点树（按教师科目+学段过滤）

**知识点树 API 返回格式**：
```json
{
  "grades": [
    {
      "name": "一年级",
      "semesters": [
        {
          "name": "上学期",
          "knowledge_points": [
            { "id": 1, "name": "集合", "question_count": 5 }
          ]
        }
      ]
    }
  ]
}
```

### 2.5 前端新增文件

| 文件 | 职责 |
|------|------|
| `src/api/favorites.ts` | 精选 API 封装 |
| `src/api/knowledge.ts` | 知识点树 API 封装 |
| `src/pages/teacher/bank.vue` | 题库列表页 |
| `src/pages/teacher/favorites.vue` | 我的精选页 |

### 2.6 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/pages.json` | 新增 bank 和 favorites 页面路由 |
| `src/pages/teacher/workbench.vue` | sidebar 菜单更新 |
| `src/pages/teacher/import.vue` | sidebar 菜单更新 |
| `src/pages/teacher/audit.vue` | sidebar 菜单更新 |
| `src/pages/teacher/my-classes.vue` | sidebar 菜单更新 |
| `src/pages/teacher/class-create.vue` | sidebar 菜单更新 |
| `src/pages/teacher/class-detail.vue` | sidebar 菜单更新 |
| `src/pages/teacher/class-requests.vue` | sidebar 菜单更新 |
| `src/pages/teacher/question-edit.vue` | sidebar 菜单更新 |
| `src/pages/teacher/mission-create.vue` | sidebar 菜单更新 |
| `src/pages/teacher/mission-detail.vue` | sidebar 菜单更新 |
| `src/pages/teacher/class-edit.vue` | sidebar 菜单更新 |
| `src/store/index.ts` | 可选：新增 teacher.stage 字段 |

## 3. 架构设计

### 3.1 数据流

```
教师登录 → 获取 userInfo (含 subject, stage)
    ↓
点击"题库管理 → 题库列表"
    ↓
bank.vue 加载
    ├─ GET /api/v1/teacher/knowledge-tree → 渲染左侧知识点树
    └─ (无选中知识点时，右侧显示空状态)
    ↓
用户点击知识点
    ↓
GET /api/v1/questions?knowledge_point_id=X → 渲染右侧题目列表
    ↓
用户点击"加入精选"
    ↓
POST /api/v1/teacher/favorites {question_id}
    ↓
按钮变为"已精选"
    ↓
点击"我的精选"
    ↓
favorites.vue 加载
    ↓
GET /api/v1/teacher/favorites → 渲染精选列表
```

### 3.2 组件职责

| 组件 | 职责 |
|------|------|
| `bank.vue` | 知识点树 + 题目列表 + 加入精选操作 |
| `favorites.vue` | 精选列表 + 取消精选操作 |
| `favorites.ts` | 封装精选相关的 HTTP 请求 |
| `knowledge.ts` | 封装知识点树 HTTP 请求 |
| tiku 后端 | 精选模型 CRUD、知识点树查询 |

## 4. 测试策略

### 4.1 前端测试
- bank.vue：知识点树正确加载、题目列表正确显示、加入精选按钮状态切换
- favorites.vue：精选列表正确显示、取消精选后列表更新
- sidebar：菜单跳转正确、active 状态正确

### 4.2 后端测试
- 精选模型：重复加入同一题目应返回 409 Conflict
- 取消精选：不存在的精选 ID 应返回 404
- 知识点树：按科目+学段正确过滤

### 4.3 手动测试
- 教师登录 → 进入题库管理 → 知识点树显示正确
- 点击知识点 → 题目列表加载
- 加入精选 → 我的精选中显示
- 取消精选 → 我的精选中移除
