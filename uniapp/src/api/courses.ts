// Course API - 使用完整 URL 绕过 request.ts 的 /study 前缀
// 因为后端 courses API 路径是 /api/v1/courses/ 而非 /study/api/v1/courses/
const COURSE_BASE = '/api/v1'

// Helper: 直接使用 fetch 绕过 request.ts 的 BASE_URL
function courseFetch<T>(url: string, options?: RequestInit): Promise<T> {
  return fetch(COURSE_BASE + url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${uni.getStorageSync('accessToken')}`,
      ...options?.headers,
    },
  }).then(res => res.json())
}

export const courseApi = {
  list: () => courseFetch<any[]>('/courses/'),
  create: (data: { name: string; subject: string; grade_level: string; description?: string }) =>
    courseFetch<any>('/courses/', { method: 'POST', body: JSON.stringify(data) }),
  detail: (id: number) => courseFetch<any>(`/courses/${id}/`),
  update: (id: number, data: any) => courseFetch<any>(`/courses/${id}/`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id: number) => courseFetch<any>(`/courses/${id}/`, { method: 'DELETE' }),
}

// ============================================================
// 课程资料
// ============================================================
export const materialApi = {
  list: (courseId: number) => courseFetch<any[]>(`/courses/${courseId}/materials/`),
  upload: (courseId: number, file: File) => {
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
  download: (courseId: number, materialId: number) =>
    `${COURSE_BASE}/courses/${courseId}/materials/${materialId}/download/`,
  preview: (courseId: number, materialId: number) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/preview/`),
  remove: (courseId: number, materialId: number) =>
    courseFetch<any>(`/courses/${courseId}/materials/${materialId}/`, { method: 'DELETE' }),
}

// ============================================================
// 目录树
// ============================================================
export const treeApi = {
  list: (courseId: number) => courseFetch<any[]>(`/courses/${courseId}/tree/`),
  create: (courseId: number, data: { name: string; parent?: number }) =>
    courseFetch<any>(`/courses/${courseId}/tree/`, { method: 'POST', body: JSON.stringify(data) }),
  update: (courseId: number, nodeId: number, data: any) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (courseId: number, nodeId: number) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/`, { method: 'DELETE' }),
  move: (courseId: number, nodeId: number, data: { parent?: number }) =>
    courseFetch<any>(`/courses/${courseId}/tree/${nodeId}/move/`, { method: 'PUT', body: JSON.stringify(data) }),
}

// ============================================================
// 课程习题
// ============================================================
export const courseQuestionApi = {
  list: (courseId: number, params?: { tree_node_id?: number }) => {
    const qs = params?.tree_node_id ? `?tree_node_id=${params.tree_node_id}` : ''
    return courseFetch<any[]>(`/courses/${courseId}/questions/${qs}`)
  },
  import: (courseId: number, data: { question_ids: number[]; tree_node_id?: number }) =>
    courseFetch<any>(`/courses/${courseId}/questions/import/`, { method: 'POST', body: JSON.stringify({ question_ids: data.question_ids, tree_node_id: data.tree_node_id }) }),
  batchDelete: (courseId: number, questionIds: number[]) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-delete/`, { method: 'POST', body: JSON.stringify({ question_ids: questionIds }) }),
  batchMove: (courseId: number, questionIds: number[], targetNodeId: number) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-move/`, {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds, target_node_id: targetNodeId }),
    }),
}

// ============================================================
// 变式题
// ============================================================
export const variantApi = {
  generate: (courseId: number, questionId: number, mode?: string) =>
    courseFetch<any>(`/courses/${courseId}/questions/${questionId}/generate-variant/`, {
      method: 'POST',
      body: JSON.stringify({ variant_mode: mode }),
    }),
  batchGenerate: (courseId: number, questionIds: number[], mode?: string) =>
    courseFetch<any>(`/courses/${courseId}/questions/batch-generate-variant/`, {
      method: 'POST',
      body: JSON.stringify({ question_ids: questionIds, variant_mode: mode }),
    }),
  getStatus: (courseId: number, taskId: number) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/`),
  confirm: (courseId: number, taskId: number) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/confirm/`, { method: 'POST' }),
  reject: (courseId: number, taskId: number) =>
    courseFetch<any>(`/courses/${courseId}/variant-tasks/${taskId}/reject/`, { method: 'POST' }),
}
