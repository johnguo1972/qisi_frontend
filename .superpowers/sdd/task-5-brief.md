# Task 5: 前端 API 封装 + TeacherSidebar 修改

**位置**: `uniapp/src/` 前端代码

## 新建文件

### `uniapp/src/api/courses.ts`

封装所有课程相关 API 调用：

```typescript
import { post, get, put, del } from '@/utils/request.ts'

// 课程 CRUD
export const courseApi = {
  list: () => get<any[]>('/courses/'),
  create: (data: { name: string; subject: string; grade_level: string; description?: string }) => post<any>('/courses/', data),
  detail: (id: number) => get<any>(`/courses/${id}/`),
  update: (id: number, data: any) => put<any>(`/courses/${id}/`, data),
  remove: (id: number) => del<any>(`/courses/${id}/`),
}

// 资料
export const materialApi = {
  list: (courseId: number) => get<any[]>(`/courses/${courseId}/materials/`),
  upload: (courseId: number, file: File) => { /* FormData POST to /courses/{id}/materials/upload/ */ },
  download: (courseId: number, materialId: number) => `/api/v1/courses/${courseId}/materials/${materialId}/download/`,
  preview: (courseId: number, materialId: number) => get<any>(`/courses/${courseId}/materials/${materialId}/preview/`),
  remove: (courseId: number, materialId: number) => del<any>(`/courses/${courseId}/materials/${materialId}/`),
}

// 目录树
export const treeApi = {
  list: (courseId: number) => get<any[]>(`/courses/${courseId}/tree/`),
  create: (courseId: number, data: { name: string; parent?: number }) => post<any>(`/courses/${courseId}/tree/`, data),
  update: (courseId: number, nodeId: number, data: any) => put<any>(`/courses/${courseId}/tree/${nodeId}/`, data),
  remove: (courseId: number, nodeId: number) => del<any>(`/courses/${courseId}/tree/${nodeId}/`),
  move: (courseId: number, nodeId: number, data: { parent?: number }) => put<any>(`/courses/${courseId}/tree/${nodeId}/move/`, data),
}

// 习题
export const courseQuestionApi = {
  list: (courseId: number, params?: { tree_node_id?: number }) => get<any[]>(`/courses/${courseId}/questions/`, params),
  import: (courseId: number, data: { question_ids: number[]; tree_node_id?: number }) => post<any>(`/courses/${courseId}/questions/import/`, data),
  batchDelete: (courseId: number, questionIds: number[]) => post<any>(`/courses/${courseId}/questions/batch-delete/`, { question_ids: questionIds }),
  batchMove: (courseId: number, questionIds: number[], targetNodeId: number) => post<any>(`/courses/${courseId}/questions/batch-move/`, { question_ids: questionIds, target_node_id: targetNodeId }),
}

// 变式题
export const variantApi = {
  generate: (courseId: number, questionId: number, mode?: string) => post<any>(`/courses/${courseId}/questions/${questionId}/generate-variant/`, { variant_mode: mode }),
  batchGenerate: (courseId: number, questionIds: number[], mode?: string) => post<any>(`/courses/${courseId}/questions/batch-generate-variant/`, { question_ids: questionIds, variant_mode: mode }),
  getStatus: (courseId: number, taskId: number) => get<any>(`/courses/${courseId}/variant-tasks/${taskId}/`),
  confirm: (courseId: number, taskId: number) => post<any>(`/courses/${courseId}/variant-tasks/${taskId}/confirm/`),
  reject: (courseId: number, taskId: number) => post<any>(`/courses/${courseId}/variant-tasks/${taskId}/reject/`),
}
```

## 修改文件

### `uniapp/src/components/TeacherSidebar.vue`

在"班级管理"之前新增菜单项：
```vue
<view class="nav-item" :class="{ active: activeItem === 'course-list' }" @click="goCourseList">
  <text class="nav-icon">&#127891;</text>
  <text class="nav-text">课程列表</text>
</view>
```

新增导航函数：`function goCourseList() { uni.navigateTo({ url: '/pages/teacher/course-list' }) }`

### `uniapp/pages.json`

注册三个新页面路由：
```json
{ "path": "pages/teacher/course-list", "style": { "navigationBarTitleText": "课程列表" } },
{ "path": "pages/teacher/course-materials", "style": { "navigationBarTitleText": "课程资料" } },
{ "path": "pages/teacher/course-practice", "style": { "navigationBarTitleText": "课程练习" } },
```

## 约束
- 仅修改 ./front 目录
- 复用现有 `@/utils/request.ts` 中的 get/post/put/del 函数
- 文件上传使用 FormData（参考 `uniapp/src/api/questions.ts` 中的 importFile 模式）
