import { del, get, post } from '@/utils/request'
import type { UUID } from '@/types/uuid'

export const studentApi = {
  home: (params?: { class_id?: UUID; scope?: string; subject?: string }, refreshKey?: number) =>
    get('/student/home', refreshKey ? { ...params, _t: refreshKey } : params),
  missionDetail: (id: UUID, refreshKey?: number) =>
    get(`/student/missions/${id}`, refreshKey ? { _t: refreshKey } : undefined),
  levelDetail: (id: UUID) => get(`/student/levels/${id}`),
  submitAnswer: (data: { question_id: UUID; answer_content: object; mission_id?: UUID; level_id?: UUID; idempotency_key?: string }) =>
    post('/student/attempts', data),
  submitMission: (id: UUID, data?: { answers?: Array<{
    question_id: UUID
    level_id?: UUID
    answer_content: object
    attempt_id?: UUID
    idempotency_key?: string
    submitted?: boolean
  }> }) => post<any>(`/student/missions/${id}/submit`, data),
  missionResults: (id: UUID) => get<any>(`/student/missions/${id}/results`),
  relatedQuestions: (questionId: UUID) => get<any[]>(`/student/questions/${questionId}/related`),
  startAttempt: (data: { question_id: UUID; mission_id?: UUID; level_id?: UUID }) =>
    post<{ attempt_id: UUID }>('/student/attempts/start', data),
  submitDraftAttempt: (attemptId: UUID, answer_content: object) =>
    post(`/student/attempts/${attemptId}/submit`, { answer_content }),
  retryAnswer: (attemptId: UUID, data: object) =>
    post(`/student/attempts/${attemptId}/retry`, data),
  startGuidance: (data: { question_id: UUID; mode_type: string }) =>
    post('/student/guidance/sessions', data),
  guidanceReply: (sessionId: UUID, reply: string) =>
    post(`/student/guidance/sessions/${sessionId}/reply`, { reply }),
  getModeA: (questionId: UUID) => get(`/student/questions/${questionId}/mode-a`),
  growth: () => get('/student/growth'),
  knowledgeMastery: (params?: { subject?: string }) => get('/student/knowledge-mastery', params),
}

export const wrongbookApi = {
  list: (params?: { status?: string; subject?: string; class_id?: string }) => get('/student/wrong-book/', params),
  detail: (id: UUID) => get(`/student/wrong-book/${id}/`),
  variants: (id: UUID) => get(`/student/wrong-book/${id}/variants/`),
  variantSubmit: (itemId: UUID, data: { question_id: UUID; answer_content: object }) =>
    post(`/student/wrong-book/${itemId}/variant-submit/`, data),
}

export const practiceApi = {
  wrongbookCandidates: (wrongItemId: UUID) => get(`/practice/wrong-book/${wrongItemId}/candidates/`),
  pool: (status = 'active') => get('/practice/pool', { status }),
  addPoolItems: (data: any) => post('/practice/pool/items', data),
  removePoolItem: (id: UUID) => del(`/practice/pool/items/${id}`),
  sets: (status?: string) => get('/practice/sets', status ? { status } : undefined),
  createSet: (data: any) => post('/practice/sets/create', data),
  detail: (id: UUID) => get(`/practice/sets/${id}/`),
  questions: (id: UUID) => get(`/practice/sets/${id}/questions`),
  progress: (id: UUID) => get(`/practice/sets/${id}/progress`),
  activate: (id: UUID) => post(`/practice/sets/${id}/activate`),
  submitSet: (id: UUID) => post(`/practice/sets/${id}/submit`),
  submit: (setId: UUID, itemId: UUID, data: any) => post(`/practice/sets/${setId}/items/${itemId}/attempts`, data),
  createPhotoDraft: (setId: UUID, itemId: UUID, data: any = {}) => post(`/practice/sets/${setId}/items/${itemId}/attempts/draft`, data),
  submitPhoto: (attemptId: UUID, data: any = {}) => post(`/practice/attempts/${attemptId}/submit`, data),
  exportPdf: (setId: UUID, data: any = {}) => post(`/practice/sets/${setId}/export-pdf`, data),
  pdf: (setId: UUID) => get(`/practice/sets/${setId}/pdf`),
}

export const exportApi = {
  exportPdf: (data: {
    export_type: string
    item_ids: Array<string | number>
    source_wrong_item_id?: string
    include_answers: boolean
    watermark_text?: string
  }) =>
    post<{ download_url?: string; url?: string }>('/student/export/pdf', data),
}
