# Task 8 Fix Report

## Status: DONE

## 修改文件

| 文件 | 修复项 |
|------|--------|
| `uniapp/src/pages/teacher/course-practice.vue` | I1, I2 |
| `uniapp/src/components/DirTree.vue` | I3 |
| `uniapp/src/components/TreeNodeItem.vue` | I3 |

## 修复详情

### I1. courseName 从 API 获取真实课程名称
- 新增 `loadCourseInfo()` 函数，调用 `courseApi.detail(courseId)` 获取课程详情
- 提取 `res.data.name` 或 `res.name` 作为课程名称
- 失败时回退显示 `课程 #${id}`
- `onMounted()` 中改为异步调用 `loadCourseInfo()`

### I2. loadMaterials 缓存
- 添加 `materialsLoaded` 布尔标志
- `loadMaterials()` 首次调用后设置标志，后续调用直接返回
- 避免每次切换"从课程资料选择" tab 时重复请求 API

### I3. window API H5-only 注释
- 在 `DirTree.vue` 的 `onMounted/onUnmounted` 处添加注释，说明 `window.addEventListener` 仅适用于 H5 环境
- 在 `TreeNodeItem.vue` 的 `onRightClick()` 处添加注释，说明 `window.dispatchEvent` 仅适用于 H5 环境
- 注释中注明了小程序适配方案（`@longpress` + event bus）

## 编译验证

```
npm run build:h5 → DONE Build complete. ✅
```
