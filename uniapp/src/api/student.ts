import { get, post } from '@/utils/request.ts'

export const studentApi = {
  home: (params?: { class_id?: number; scope?: string }) => get('/student/home', params),
  missionDetail: (id: number) => get(`/student/missions/${id}`),
  levelDetail: (id: number) => get(`/student/levels/${id}`),
  submitAnswer: (data: { question_id: number; answer_content: object; mission_id?: number; level_id?: number }) =>
    post('/student/attempts', data),
  retryAnswer: (attemptId: number, data: object) =>
    post(`/student/attempts/${attemptId}/retry`, data),
  startGuidance: (data: { question_id: number; mode_type: string }) =>
    post('/student/guidance/sessions', data),
  guidanceReply: (sessionId: number, reply: string) =>
    post(`/student/guidance/sessions/${sessionId}/reply`, { reply }),
  getModeA: (questionId: number) => get(`/student/questions/${questionId}/mode-a`),
  growth: () => get('/student/growth'),
  knowledgeMastery: () => get('/student/knowledge-mastery'),
}

export const wrongbookApi = {
  list: () => get('/student/wrong-book'),
  detail: (id: number) => get(`/student/wrong-book/${id}`),
  variants: (id: number) => get(`/student/wrong-book/${id}/variants`),
  variantSubmit: (itemId: number, data: { question_id: number; answer_content: object }) =>
    post(`/student/wrong-book/${itemId}/variant-submit`, data),
}

export const exportApi = {
  exportPdf: (data: {
    export_type: string
    item_ids: number[]
    include_answers: boolean
    watermark_text?: string
  }) =>
    post<{ download_url?: string; url?: string }>('/student/export/pdf', data),
}
