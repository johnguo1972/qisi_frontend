import { post, get, put, patch, del } from '@/utils/request.ts'

export const questionApi = {
  // GET /api/v1/questions
  list: (params?: { page?: number; page_size?: number; question_no?: string; status?: string }) =>
    get<any>('/questions', params),

  // GET /api/v1/questions/{id}
  detail: (id: number) => get<any>(`/questions/${id}`),

  // PUT /api/v1/questions/{id}
  update: (id: number, data: any) => put<any>(`/questions/${id}`, data),

  // POST /api/v1/questions/{id}/publish
  publish: (id: number) => post(`/questions/${id}/publish`),

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
        const res = await fetch('/api/v1/questions/import-batches', {
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
  importBatchDetail: (batchId: number) => get<any>(`/questions/import-batches/${batchId}`),

  // Dictionaries
  dictSubjects: () => get<any[]>('/dicts/subjects'),
  dictKnowledgePoints: () => get<any[]>('/dicts/knowledge-points'),
  dictQuestionTypes: () => get<any[]>('/dicts/question-types'),
  dictDifficultyLevels: () => get<any[]>('/dicts/difficulty-levels'),

  // DELETE /api/v1/questions/{id}
  delete: (id: number) => post<any>(`/questions/${id}/delete`),

  // AI status & confirm (review API)
  getAiStatus: (questionId: number) =>
    get<any>(`/review/question/${questionId}/ai-status/`),
  aiConfirm: (questionId: number, mode: string) =>
    post<any>(`/review/question/${questionId}/ai-confirm/${mode}/`),

  // AI process (review API)
  aiProcess: (questionId: number, data?: { model?: string }) =>
    post<any>(`/review/question/${questionId}/ai-process/`, data),

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
        url: `/api/v1/questions/camera-paper/${paperId}/upload-page/`,
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
      url: `/api/v1/papers/${paperId}/`,
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

export function aiProcessQuestion(questionId: number) {
  return post<any>(`/review/question/${questionId}/ai-process/`)
}

export function getAiTaskStatus(taskId: string) {
  return get<any>(`/review/ai-task/${taskId}/status/`)
}

export function aiProcessSingleMode(questionId: number, mode: string) {
  return post<any>(`/review/question/${questionId}/ai-process-mode/${mode}/`)
}

// Question edit page APIs
export function getQuestionDetail(questionId: number) {
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

export function deleteQuestionImage(questionId: number, imageId: number) {
  return del<any>(`/review/questions/${questionId}/images/${imageId}/`)
}

export function getQuestionAssets(questionId: number) {
  return get<any>(`/review/questions/${questionId}/assets/`)
}

// Manual question creation
export function createQuestion(data: any) {
  return post<any>('/questions/create/', data)
}

export function uploadQuestionImage(questionId: number, imageFile: File) {
  return new Promise<any>((resolve, reject) => {
    uni.uploadFile({
      url: '/api/v1/questions/upload-image/',
      filePath: imageFile as any,
      name: 'image',
      formData: { question_id: String(questionId) },
      header: {
        'Authorization': `Bearer ${uni.getStorageSync('accessToken')}`,
      },
      success: (res) => {
        const data = JSON.parse(res.data)
        resolve(data)
      },
      fail: (err) => reject(err),
    })
  })
}

export function photoListQuestions(params?: any) {
  return get('/questions/photo-list/', params)
}

export function getKnowledgeTree() {
  return get('/dicts/knowledge-points')
}
