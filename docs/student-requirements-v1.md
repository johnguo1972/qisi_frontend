# 学生端功能重构 — 需求与实施方案

> 文档版本: v1.1
> 创建日期: 2026-06-28
> 更新日期: 2026-06-28
> 状态: ✅ 用户已确认，可开始实施

---

## 用户确认事项

| # | 问题 | 决策 |
|---|------|------|
| 1 | 目标平台 | **H5 浏览器**（无需兼容小程序） |
| 2 | 任务截止日期 | **创建任务时设置 `end_at`**，数据一定存在 |
| 3 | PDF 导出优先级 | **必须有的功能**，需在 Phase 2 实现 |
| 4 | 知识图谱占位页 | **仅显示"开发中"文字** |
| 5 | 退出班级后数据 | **完全隐藏**（非软删除，直接清除关联） |
| 6 | 登录入口 | **保持现状**（登录页 Tab 切换角色） |

---

## 目标 TabBar（4项）

```
[首页]  [错题本]  [图谱]  [成长]
```

---

## 实施阶段

### Phase 1: MVP（首页 + 班级 + 退出）

| 步骤 | 任务 | 类型 | 文件 |
|------|------|------|------|
| 1.1 | `LearningMission` 增加 `class_obj` FK (`null=True`) | 后端迁移 | `apps/missions/migrations/0002_*.py` |
| 1.2 | `GET /student/home` 增强：返回 `class_label`、`deadline`，支持 `?class_id=N&scope=today\|week` | 后端 | `apps/study/student_views.py` |
| 1.3 | `GET /student/my-classes` 增强：返回 `subject`、`student_count` | 后端 | `apps/institutions/student_views.py` + `serializers.py` |
| 1.4 | `POST /student/classes/{id}/quit` 新 API：退出班级，完全隐藏数据 | 后端 | `apps/institutions/student_views.py` + `urls.py` |
| 1.5 | 前端 `studentApi.home()` 增加参数 | 前端 | `api/student.ts` |
| 1.6 | 前端新增 `ClassSelector.vue` 组件 | 前端 | `components/ClassSelector.vue` |
| 1.7 | 前端新增 `TimeFilterBar.vue` 组件 | 前端 | `components/TimeFilterBar.vue` |
| 1.8 | 前端改造 `home.vue`：班级选择器 + 时间筛选 + 任务排序 + 班级标签 | 前端 | `pages/student/home.vue` |
| 1.9 | 前端改造 `join-class.vue`：新增"我的班级"Tab + 退出功能 | 前端 | `pages/student/join-class.vue` |
| 1.10 | 前端新增 `quitClass` API 方法 | 前端 | `api/institutions.ts` |

### Phase 2: 错题本增强 + PDF 导出

| 步骤 | 任务 | 类型 | 文件 |
|------|------|------|------|
| 2.1 | `POST /student/export/pdf` 新 API：PDF 生成 | 后端 | `apps/study/student_views.py` + `urls.py` |
| 2.2 | 前端新增 `export.vue` 页面 | 前端 | `pages/student/export.vue` |
| 2.3 | 错题本增加"练同类题"按钮 + 同类题页面 | 前端 | `pages/student/wrongbook.vue` + `wrongbook-variants.vue` |
| 2.4 | PDF 导出入口：关卡页 + 错题本页 | 前端 | `pages/student/mission.vue` + `wrongbook.vue` |

### Phase 3: 拍照上传

| 步骤 | 任务 | 类型 | 文件 |
|------|------|------|------|
| 3.1 | `POST /student/attempts/{id}/upload-image` 新 API | 后端 | `apps/study/student_views.py` + `urls.py` |
| 3.2 | 前端新增 `image-upload.ts` 工具 | 前端 | `utils/image-upload.ts` |
| 3.3 | 做题页主观题区域增加拍照按钮 | 前端 | `pages/student/answer.vue` |

### Phase 4: 知识图谱占位页

| 步骤 | 任务 | 类型 | 文件 |
|------|------|------|------|
| 4.1 | 前端新增 `knowledge-graph.vue` 页面 | 前端 | `pages/student/knowledge-graph.vue` |
| 4.2 | `pages.json` 增加 TabBar 项 + 新页面路由 | 前端 | `pages.json` |

---

## 关键设计决策

### 退出班级策略
- 直接删除 `ClassStudent` 记录（`status='active'` → 物理删除）
- 清理该学生的 `StudentMissionProgress` 和 `StudentLevelProgress` 记录
- 清理错题本中该班级相关的题目
- 退出后该班级的任务、关卡、错题对学生完全不可见

### PDF 导出方案
- 后端生成（`weasyprint` 或 `reportlab`）
- 同步返回下载 URL
- 限制：max 50题/PDF，max 3次/小时
- 前端通过 `window.open(url)` 下载

### H5 拍照上传
- 使用 `<input type="file" accept="image/*" capture="environment">`
- 桌面端提示"请使用手机访问以使用拍照功能"

---

## 关键文件清单

### 新建（9个）
```
front/uniapp/src/components/ClassSelector.vue
front/uniapp/src/components/TimeFilterBar.vue
front/uniapp/src/pages/student/knowledge-graph.vue
front/uniapp/src/pages/student/wrongbook-variants.vue
front/uniapp/src/pages/student/export.vue
front/uniapp/src/utils/image-upload.ts
front/apps/missions/migrations/0002_add_class_to_mission.py
```

### 修改（15个）
```
front/uniapp/src/pages.json
front/uniapp/src/pages/student/home.vue
front/uniapp/src/pages/student/join-class.vue
front/uniapp/src/pages/student/wrongbook.vue
front/uniapp/src/pages/student/answer.vue
front/uniapp/src/pages/student/mission.vue
front/uniapp/src/api/student.ts
front/uniapp/src/api/institutions.ts
front/apps/study/student_views.py
front/apps/study/student_urls.py
front/apps/institutions/student_views.py
front/apps/institutions/urls.py
front/apps/institutions/serializers.py
front/apps/knowledge/views.py (可能需要新建)
front/apps/knowledge/urls.py
```
