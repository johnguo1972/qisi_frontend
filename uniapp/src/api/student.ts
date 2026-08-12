import { get, post } from '@/utils/request'
import type { UUID } from '@/types/uuid'

export const studentApi = {
  home: (params?: { class_id?: UUID; scope?: string }, refreshKey?: number) =>
    get('/student/home', refreshKey ? { ...params, _t: refreshKey } : params),
  missionDetail: (id: UUID, refreshKey?: number) =>
    get(`/student/missions/${id}`, refreshKey ? { _t: refreshKey } : undefined),
  levelDetail: (id: UUID) => get(`/student/levels/${id}`),
  submitAnswer: (data: { question_id: UUID; answer_content: object; mission_id?: UUID; level_id?: UUID }) =>
    post('/student/attempts', data),
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
  knowledgeMastery: () => get('/student/knowledge-mastery'),
}

export const wrongbookApi = {
  list: () => get('/student/wrong-book/'),
  detail: (id: UUID) => get(`/student/wrong-book/${id}/`),
  variants: (id: UUID) => get(`/student/wrong-book/${id}/variants/`),
  variantSubmit: (itemId: UUID, data: { question_id: UUID; answer_content: object }) =>
    post(`/student/wrong-book/${itemId}/variant-submit/`, data),
}

export const exportApi = {
  exportPdf: (data: {
    export_type: string
    item_ids: Array<string | number>
    include_answers: boolean
    watermark_text?: string
  }) =>
    post<{ download_url?: string; url?: string }>('/student/export/pdf', data),
}
