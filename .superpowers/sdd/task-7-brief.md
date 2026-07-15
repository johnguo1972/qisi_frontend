# Task 7: 前端课程资料页

**位置**: `uniapp/src/pages/teacher/course-materials.vue`

## 新建文件

课程资料管理页面：
- 左侧 TeacherSidebar
- 顶部面包屑导航 + 「+ 上传资料」按钮
- 文件列表表格：文件名 | 类型 | 大小 | 上传时间 | 操作（下载/预览/删除）
- 上传：支持 PDF/Word/图片（50MB 限制）
- 下载：触发浏览器下载
- 预览：图片直出，PDF/Word 新窗口打开
- 删除：软删除确认弹窗

## 依赖
- Task 5 的 `materialApi`（list, upload, download, preview, remove）
- Task 5 的 `courseApi.detail`（获取课程名称用于面包屑）
- `@/components/TeacherSidebar.vue`

## 约束
- 仅修改 ./front 目录
- 文件上传参考 `uniapp/src/api/questions.ts` 中的 `importFile` 模式（FormData + fetch）
- 页面参数从 URL 获取：`/pages/teacher/course-materials?id=1`
