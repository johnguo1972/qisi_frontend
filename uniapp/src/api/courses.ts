// Course API - 后端 courses API 路径是 /api/v1/courses/
import type { UUID } from '@/types/uuid'
import { serializeCourseQuestionQuery, type CourseQuestionListQuery } from '@/pages/teacher/course-practice-list'

const COURSE_BASE = '/api/v1'

// Helper: 直接使用 fetch 绕过 request.ts 的 BASE_URL
function courseFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const token = uni.getStorageSync('accessToken')
  console.log(`[courseFetch] ${options?.method || 'GET'} ${COURSE_BASE + url}`, { hasToken: !!token })
  return fetch(COURSE_BASE + url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  }).then(res => {
    if (res.status === 401) {
      // Token 过期，清除并跳转登录
      uni.removeStorageSync('accessToken')
      uni.removeStorageSync('refreshToken')
      uni.reLaunch({ url: '/pages/login/index' })
      throw new Error('登录已过期，请重新登录')
    }
    if (!res.ok) {
      return res.text().then(text => {
        const error: any = new Error(`HTTP ${res.status}: ${text || res.statusText}`)
        error.status = res.status
        throw error
      })
    }
    return res.json()
  })
}

export const courseApi = {
  list: (institutionId?: UUID) => courseFetch<any[]>(`/courses/${institutionId ? `?institution_id=${institutionId}` : ''}`),
  create: (data: { name: string; subject: string; grade_level: string; description?: string; institution_id?: UUID }) =>
    courseFetch<any>('/courses/', { method: 'POST', body: JSON.stringify(data) }),
  detail: (id: UUID) => courseFetch<any>(`/courses/${id}/`),
  update: (id: UUID, data: any) => courseFetch<any>(`/courses/${id}/`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id: UUID) => courseFetch<any>(`/courses/${id}/`, { method: 'DELETE' }),
  collaborators: (id: UUID) => courseFetch<any>(`/courses/${id}/collaborators/`),
  grantCollaborator: (id: UUID, data: { user_id: UUID; role: 'viewer' | 'editor' }) =>
    courseFetch<any>(`/courses/${id}/collaborators/`, { method: 'POST', body: JSON.stringify(data) }),
  revokeCollaborator: (id: UUID, userId: UUID) =>
    courseFetch<any>(`/courses/${id}/collaborators/${userId}/`, { method: 'DELETE' }),
}

// ============================================================
// 课程资料
// ============================================================
export const materialApi = {
  list: (courseId: UUID) => courseFetch<any[]>(`/courses/${courseId}/materials/`),
  upload: (courseId: UUID, file: File) => {
    return new Promise<any>(async (resolve, reject) => {
      const token = uni.getStorageSync('accessToken')
      const formData = new FormData()
      formData.append('file', file)

      try {
        const res = await fetch(`${COURSE_BASE}/courses/${courseId}/materials/upload/`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          body: formData,
        })
        const data = await res.json()
        if (res.ok) {
          resolve(data)
        } else {
          reject(new Error(data.message || `上传失败 (${res.status})`))
        }
      } catch (e) {
        reject(e)
      }
    })
  },
  // 返回下载链接 URL（非请求）
  download: (courseId: UUID, materialId: UUID) =>
    `${COURSE_BASE}/courses/${courseId}/materials/${materialId}/download/`,
  preview: (courseId: UUID, materialId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/preview/`),
  remove: (courseId: UUID, materialId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/`, { method: 'DELETE' }),
  // 获取文档页面图片列表
  pages: (courseId: UUID, materialId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/pages/`),
  // AI 识别框选区域
  aiRecognize: (courseId: UUID, materialId: UUID, data: { image_url: string; page?: number }) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/ai-recognize/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// ============================================================
// 题目导入
// ============================================================
export const importApi = {
  // 保存从课程资料导入的题目
  saveQuestion: (courseId: UUID, data: { question: any; tree_node_id?: UUID }) =>
    courseFetch<any>(`/courses/${courseId}/import-question/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// ============================================================
// 目录树
// ============================================================
export const treeApi = {
  list: (courseId: UUID) => courseFetch<any[]>(`/courses/${courseId}/tree/`),
  create: (courseId: UUID, data: { name: string; parent?: UUID }) =>
    courseFetch<any>(`/courses/${courseId}/tree/`, { method: 'POST', body: JSON.stringify(data) }),
  update: (courseId: UUID, nodeId: UUID, data: any) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (courseId: UUID, nodeId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/`, { method: 'DELETE' }),
  move: (courseId: UUID, nodeId: UUID, data: { parent?: UUID; sort_order?: number }) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/move/`, { method: 'PUT', body: JSON.stringify(data) }),
}

// ============================================================
// 课程习题
// ============================================================
export const courseQuestionApi = {
  list: (courseId: UUID, params: CourseQuestionListQuery) => {
    const query = serializeCourseQuestionQuery(params)
    return courseFetch<any>(`/courses/${courseId}/questions/?${query.toString()}`)
  },
  import: (courseId: UUID, data: { question_ids: UUID[]; tree_node_id?: UUID }) =>
    courseFetch<any>(`/courses/${courseId}/questions/import/`, { method: 'POST', body: JSON.stringify({ question_ids: data.question_ids, tree_node_id: data.tree_node_id }) }),
  batchDelete: (courseId: UUID, questionIds: UUID[], sourceNodeId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-delete/`, { method: 'POST', body: JSON.stringify({ question_ids: questionIds, tree_node_id: sourceNodeId }) }),
  batchMove: (courseId: UUID, questionIds: UUID[], sourceNodeId: UUID, targetNodeId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-move/`, {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds, tree_node_id: sourceNodeId, target_node_id: targetNodeId }),
    }),
}

// ============================================================
// 变式题
// ============================================================
export const variantApi = {
  generate: (courseId: UUID, questionId: UUID, mode?: string) =>
    courseFetch<any>(`/courses/${courseId}/questions/${questionId}/generate-variant/`, {
      method: 'POST',
      body: JSON.stringify({ variant_mode: mode }),
    }),
  batchGenerate: (courseId: UUID, questionIds: UUID[], mode?: string) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-generate-variant/`, {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds, variant_mode: mode }),
    }),
  getStatus: (courseId: UUID, taskId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/`),
  confirm: (courseId: UUID, taskId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/confirm/`, { method: 'POST' }),
  reject: (courseId: UUID, taskId: UUID) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/reject/`, { method: 'POST' }),
}
