import { post, get, put, del } from '@/utils/request.ts'

// ============================================================
// 课程 CRUD
// ============================================================
export const courseApi = {
  list: () => get<any[]>('/courses/'),
  create: (data: { name: string; subject: string; grade_level: string; description?: string }) =>
    post<any>('/courses/', data),
  detail: (id: number) => get<any>(`/courses/${id}/`),
  update: (id: number, data: any) => put<any>(`/courses/${id}/`, data),
  remove: (id: number) => del<any>(`/courses/${id}/`),
}

// ============================================================
// 课程资料
// ============================================================
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
    `/api/v1/courses/${courseId}/materials/${materialId}/download/`,
  preview: (courseId: number, materialId: number) =>
    get<any>(`/courses/${courseId}/materials/${materialId}/preview/`),
  remove: (courseId: number, materialId: number) =>
    del<any>(`/courses/${courseId}/materials/${materialId}/`),
}

// ============================================================
// 目录树
// ============================================================
export const treeApi = {
  list: (courseId: number) => get<any[]>(`/courses/${courseId}/tree/`),
  create: (courseId: number, data: { name: string; parent?: number }) =>
    post<any>(`/courses/${courseId}/tree/`, data),
  update: (courseId: number, nodeId: number, data: any) =>
    put<any>(`/courses/${courseId}/tree/${nodeId}/`, data),
  remove: (courseId: number, nodeId: number) =>
    del<any>(`/courses/${courseId}/tree/${nodeId}/`),
  move: (courseId: number, nodeId: number, data: { parent?: number }) =>
    put<any>(`/courses/${courseId}/tree/${nodeId}/move/`, data),
}

// ============================================================
// 课程习题
// ============================================================
export const courseQuestionApi = {
  list: (courseId: number, params?: { tree_node_id?: number }) =>
    get<any[]>(`/courses/${courseId}/questions/`, params),
  import: (courseId: number, data: { question_ids: number[]; tree_node_id?: number }) =>
    post<any>(`/courses/${courseId}/questions/import/`, data),
  batchDelete: (courseId: number, questionIds: number[]) =>
    post<any>(`/courses/${courseId}/questions/batch-delete/`, { question_ids: questionIds }),
  batchMove: (courseId: number, questionIds: number[], targetNodeId: number) =>
    post<any>(`/courses/${courseId}/questions/batch-move/`, {
      question_ids: questionIds,
      target_node_id: targetNodeId,
    }),
}

// ============================================================
// 变式题
// ============================================================
export const variantApi = {
  generate: (courseId: number, questionId: number, mode?: string) =>
    post<any>(`/courses/${courseId}/questions/${questionId}/generate-variant/`, {
      variant_mode: mode,
    }),
  batchGenerate: (courseId: number, questionIds: number[], mode?: string) =>
    post<any>(`/courses/${courseId}/questions/batch-generate-variant/`, {
      question_ids: questionIds,
      variant_mode: mode,
    }),
  getStatus: (courseId: number, taskId: number) =>
    get<any>(`/courses/${courseId}/variant-tasks/${taskId}/`),
  confirm: (courseId: number, taskId: number) =>
    post<any>(`/courses/${courseId}/variant-tasks/${taskId}/confirm/`),
  reject: (courseId: number, taskId: number) =>
    post<any>(`/courses/${courseId}/variant-tasks/${taskId}/reject/`),
}
