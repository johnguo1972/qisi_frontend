import { post, get, put, patch, del } from '@/utils/request'
import type { UUID } from '@/types/uuid'

export type QuestionRelationItem = {
  id: UUID
  question_no: string
  stem_preview: string
  difficulty: string | number | null
  knowledge_points_display: Array<{ id?: string; name: string }>
  common_knowledge_point_names?: string[]
}

// #ifdef APP-PLUS
const UPLOAD_BASE = 'https://qisi.chengxuelu.com/api/v1'
// #endif
// #ifndef APP-PLUS
const UPLOAD_BASE = '/api/v1'
// #endif

export const questionApi = {
  // GET /api/v1/questions
  list: (params?: { page?: number; page_size?: number; keyword?: string; question_no?: string; status?: string; question_type?: string; difficulty?: string; knowledge_point_id?: string | number; stages?: string; tag?: string; uuid?: string; subject?: string }) =>
    get<any>('/questions/', params),

  // GET /api/v1/questions/{id}
  detail: (id: UUID) => get<any>(`/questions/${id}`),

  // PUT /api/v1/questions/{id}
  update: (id: UUID, data: any) => put<any>(`/questions/${id}`, data),

  // POST /api/v1/questions/{id}/publish
  publish: (id: UUID) => post(`/questions/${id}/publish`),

  // POST /api/v1/questions/import-batches (upload file via FormData)
  importFile: (filePath: string, fileName?: string) => {
    return new Promise<any>(async (resolve, reject) => {
      const token = uni.getStorageSync('accessToken')
      const formData = new FormData()

      // H5 platform: filePath is a blob URL
      try {
        const response = await fetch(filePath)
        const blob = await response.blob()
        // Create a File object with the original name (not just a plain Blob)
        const file = new File([blob], fileName || 'upload.docx', { type: blob.type })
        formData.append('file', file)
      } catch (e) {
        reject(new Error('无法读取文件'))
        return
      }

      try {
        const res = await fetch(`${UPLOAD_BASE}/questions/import-batches`, {
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

  // GET /api/v1/questions/import-batches
  importBatches: () => get<any[]>('/questions/import-batches'),

  // GET /api/v1/questions/import-batches/{batch_id}
  importBatchDetail: (batchId: UUID) => get<any>(`/questions/import-batches/${batchId}`),

  // Dictionaries
  dictSubjects: () => get<any[]>('/dicts/subjects'),
  dictKnowledgePoints: () => get<any[]>('/dicts/knowledge-points'),
  dictQuestionTypes: () => get<any[]>('/dicts/question-types'),
  dictDifficultyLevels: () => get<any[]>('/dicts/difficulty-levels'),

  // DELETE /api/v1/questions/{id}
  delete: (id: UUID) => post<any>(`/questions/${id}/delete`),

  // AI status & confirm (review API)
  getAiStatus: (questionId: UUID) =>
    get<any>(`/review/question/${questionId}/ai-status/`),
  aiConfirm: (questionId: UUID, mode: string) =>
    post<any>(`/review/question/${questionId}/ai-confirm/${mode}/`),
  aiUpdateAnswer: (questionId: UUID, mode: string, editedContent: Record<string, any>) =>
    patch<any>(`/review/question/${questionId}/ai-answer/${mode}/`, { edited_content: editedContent }),

  // AI process (review API)
  aiProcess: (questionId: UUID, data?: { model?: string }) =>
    post<any>(`/review/question/${questionId}/ai-process/`, data),
  aiProcessMode: (questionId: UUID, mode: string) =>
    post<any>(`/review/question/${questionId}/ai-process-mode/${mode}/`),
  batchAi: (questionIds: UUID[], model?: string) =>
    post<any>('/review/batch-ai-process/', { question_ids: questionIds, model }),
  getAiJobStatus: (jobId: string) =>
    get<any>(`/review/ai-jobs/${jobId}/`),
  similar: (questionId: UUID) => get<any>(`/questions/${questionId}/similar/`),
  relations: (questionId: UUID, params?: { page?: number; page_size?: number }) =>
    get<any>(`/questions/${questionId}/relations/`, params),
  relationCandidates: (questionId: UUID, params?: { page?: number; page_size?: number }) =>
    get<any>(`/questions/${questionId}/relation-candidates/`, params),
  createRelations: (questionId: UUID, questionIds: UUID[]) =>
    post<any>(`/questions/${questionId}/relations/`, { question_ids: questionIds }),
  removeRelation: (questionId: UUID, relatedId: UUID) =>
    del<any>(`/questions/${questionId}/relations/${relatedId}/`),

  // AI task status polling
  getTaskStatus: (taskId: string) =>
    get<any>(`/review/ai-task/${taskId}/status/`),

  // Camera paper operations
  cameraCreate: (data: { subject: string }) =>
    post<any>('/questions/camera-paper/create/', data),
  cameraUploadPage: (paperId: number, pageNo: number, filePath: string) => {
    return new Promise<any>((resolve, reject) => {
      // @ts-ignore
      uni.uploadFile({
        url: `${UPLOAD_BASE}/questions/camera-paper/${paperId}/upload-page/`,
        filePath: filePath,
        name: 'file',
        formData: { page_no: String(pageNo) },
        header: {
          // @ts-ignore
          Authorization: `Bearer ${uni.getStorageSync('accessToken')}`,
        },
        success: (res: any) => {
          const data = JSON.parse(res.data);
          resolve(data);
        },
        fail: (err: any) => reject(err),
      });
    });
  },
  cameraParse: (paperId: number) =>
    post<any>(`/questions/camera-paper/${paperId}/parse/`),
}

export function stopParse(paperId: number) {
  return post(`/papers/${paperId}/stop-parse/`)
}

export function reparsePaper(paperId: number) {
  return post(`/papers/${paperId}/reparse/`)
}

export function getParseProgress(paperId: number) {
  return get<any>(`/papers/${paperId}/progress/`)
}

export function deletePaper(paperId: number) {
  const token = uni.getStorageSync('accessToken')
  return new Promise<any>((resolve, reject) => {
    uni.request({
      url: `${UPLOAD_BASE}/papers/${paperId}/`,
      method: 'DELETE',
      header: {
        'Authorization': `Bearer ${token}`,
      },
      success: (res) => {
        resolve(res.data)
      },
      fail: (err) => reject(err),
    })
  })
}

// Review list page APIs
export function getReviewPapers() {
  return get<any>('/review/papers/')
}

export function getPaperQuestions(paperId: number, status?: string) {
  const params = status && status !== 'all' ? { status } : {}
  return get<any>(`/review/papers/${paperId}/questions/`, params)
}

export function confirmAiAnswer(questionId: number, mode: string) {
  return post<any>(`/review/question/${questionId}/ai-confirm/${mode}/`)
}

export function aiProcessQuestion(questionId: string | number) {
  return post<any>(`/review/question/${questionId}/ai-process/`)
}

export function aiProcessProbe(questionId: string | number) {
  return post<any>(`/review/question/${questionId}/ai-process-probe/`)
}

export function getAiTaskStatus(taskId: string) {
  return get<any>(`/review/ai-task/${taskId}/status/`)
}

export function aiProcessSingleMode(questionId: string | number, mode: string) {
  return post<any>(`/review/question/${questionId}/ai-process-mode/${mode}/`)
}

// Question edit page APIs
export function getQuestionDetail(questionId: string) {
  return get<any>(`/review/questions/${questionId}/`)
}

export function updateQuestion(questionId: number, data: any) {
  return patch<any>(`/review/questions/${questionId}/update/`, data)
}

export function rejectQuestion(questionId: number) {
  return post<any>(`/review/questions/${questionId}/reject/`)
}

export function confirmQuestion(questionId: number) {
  return post<any>(`/review/questions/${questionId}/confirm/`)
}

export function cropQuestionImage(questionId: number, bbox: { x1: number; y1: number; x2: number; y2: number }, pageNo: number) {
  return post<any>(`/review/questions/${questionId}/images/crop/`, { ...bbox, page_no: pageNo })
}

export function deleteQuestionImage(questionId: string | number, imageId: string | number) {
  return del<any>(`/review/questions/${questionId}/images/${imageId}/`)
}

export function restoreQuestionImageOriginal(questionId: string | number, imageId: string | number) {
  return post<any>(`/review/questions/${questionId}/images/${imageId}/restore-original/`)
}

export function updateQuestionImageLayout(questionId: string | number, imageId: string | number, data: { placement: 'stem' | 'options'; display_width: number; description?: string }) {
  return patch<any>(`/review/questions/${questionId}/images/${imageId}/layout/`, data)
}

export function getQuestionAssets(questionId: string | number) {
  return get<any>(`/review/questions/${questionId}/assets/`)
}

// Manual question creation
export function createQuestion(data: any) {
  return post<any>('/questions/create/', data)
}

export function uploadQuestionImage(questionId: string | number, imageFile: File | Blob | string, fileName = 'question-image.png', sourceImageId?: string | number) {
  const token = uni.getStorageSync('accessToken')

  // #ifdef H5
  const formData = new FormData()
  formData.append('image', imageFile instanceof Blob ? imageFile : String(imageFile), fileName)
  formData.append('question_id', String(questionId))
  if (sourceImageId) formData.append('source_image_id', String(sourceImageId))
  return fetch(`${UPLOAD_BASE}/questions/upload-image/`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  }).then(async (res) => {
    const data = await res.json()
    if (!res.ok) throw new Error(data.message || '图片上传失败')
    return data
  })
  // #endif

  // #ifndef H5
  return new Promise<any>((resolve, reject) => {
    uni.uploadFile({
      url: `${UPLOAD_BASE}/questions/upload-image/`,
      filePath: imageFile as string,
      name: 'image',
      formData: { question_id: String(questionId), ...(sourceImageId ? { source_image_id: String(sourceImageId) } : {}) },
      header: { Authorization: `Bearer ${token}` },
      success: (res) => {
        try { resolve(JSON.parse(res.data)) } catch { reject(new Error('上传响应无效')) }
      },
      fail: (err) => reject(err),
    })
  })
  // #endif
}

export function photoListQuestions(params?: any) {
  return get('/questions/photo-list/', params)
}

export function getKnowledgeTree() {
  return get('/dicts/knowledge-points')
}

// === JSON 数据包导入 ===

export function importJsonPackage(file: File) {
  return new Promise<any>((resolve, reject) => {
    const token = uni.getStorageSync('accessToken')
    const formData = new FormData()
    formData.append('file', file)

    // #ifdef H5
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
    // APP端暂不支持JSON导入，请在H5端使用
    reject(new Error('APP端暂不支持JSON导入，请在H5端使用'))
    // #endif
  })
}

export function getImportTaskStatus(taskId: string) {
  return get<any>(`/questions/import-json-task/${taskId}/status/`)
}

export function getJsonImportHistory() {
  return get<any>('/questions/json-import-history/')
}

// === 题目篮子 ===

export function getBasket() {
  return get<any>('/questions/basket/')
}

export function addToBasket(questionId: string) {
  return post<any>('/questions/basket/add/', { question_id: questionId })
}

export function removeFromBasket(questionId: string) {
  return del(`/questions/basket/${questionId}/`)
}

export function clearBasket() {
  return del('/questions/basket/clear/')
}

// === 批量操作 ===

export function batchUpdateQuestions(data: {
  ids: string[]
  action: string
  value?: any
}) {
  return post<any>('/questions/batch-update/', data)
}

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

export function getQuestionBarcodeUrl(questionId: string): string {
  return `${UPLOAD_BASE}/questions/${questionId}/barcode/`
}

export function scanBarcode(barcodeData: string) {
  return post<any>('/questions/barcode/scan/', { barcode_data: barcodeData })
}
