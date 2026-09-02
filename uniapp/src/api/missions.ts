import { post, get, put, patch, del } from '@/utils/request'
import type { UUID } from '@/types/uuid'

export interface Mission {
  id: UUID
  mission_no: string
  mission_name: string
  goal_text?: string
  start_at?: string
  end_at?: string
  status: string
  assignment_mode?: 'flat' | 'levels'
  mission_kind?: 'regular' | 'drill' | 'wrongbook_personal'
  source_type?: string
  class_ids?: UUID[]
  class_names?: string[]
  level_count?: number
  class_name?: string
  question_count?: number
  unfinished_count?: number
  completion_progress?: {
    completed: number
    total: number
    unfinished: number
    percent: number
  }
  subject?: string
  creator_teacher_id?: UUID
}

export const missionApi = {
  // GET /api/v1/missions/
  list: (params?: { class_id?: UUID; subject?: string; unfinished?: boolean }) => get<Mission[]>('/missions/', params),

  // POST /api/v1/missions/
  create: (data: { mission_name: string; goal_text?: string; start_at?: string; end_at?: string; class_id?: UUID | null; class_ids?: UUID[]; course_id?: UUID | null; target_student_ids?: UUID[]; mission_kind?: string; source_type?: string }) =>
    post<{ id: UUID }>('/missions/', data),

  // GET /api/v1/missions/{id}/
  detail: (id: UUID) => get<any>(`/missions/${id}/`),

  // PUT /api/v1/missions/{id}/
  update: (id: UUID, data: any) => put<any>(`/missions/${id}/`, data),

  // DELETE /api/v1/missions/{id}/delete/
  remove: (id: UUID) => del<any>(`/missions/${id}/delete/`),

  // GET /api/v1/missions/{id}/levels/
  levels: (id: UUID) => get<any[]>(`/missions/${id}/levels/`),

  // GET /api/v1/missions/{id}/questions/
  questions: (id: UUID) => get<any[]>(`/missions/${id}/questions/`),

  // POST /api/v1/missions/{id}/questions/ - replace the flat question order
  saveQuestions: (id: UUID, question_ids: UUID[]) =>
    post<{ question_count: number }>(`/missions/${id}/questions/`, { question_ids }),
  replaceQuestions: (id: UUID, question_ids: UUID[], source_type = 'manual_select') =>
    post<{ question_count: number }>(`/missions/${id}/questions/replace/`, { question_ids, source_type }),
  setKind: (id: UUID, kind: 'regular' | 'drill' | 'wrongbook_personal') =>
    post<any>(`/missions/${id}/kind/${kind}/`),

  // GET /api/v1/missions/{id}/levels/<level_id>/
  levelDetail: (id: UUID, levelId: UUID) => get<any>(`/missions/${id}/levels/${levelId}/`),

  // POST /api/v1/missions/{id}/levels/
  addLevel: (id: UUID, data: { level_name: string; level_type: string; mode_policy: string }) =>
    post<{ id: UUID }>(`/missions/${id}/levels/`, data),

  // POST /api/v1/missions/{id}/levels/batch/
  addLevelsBatch: (id: UUID, data: { levels: Array<{
      name: string; type: string; mode: string; questionIds: UUID[];
  }>}) =>
    post<{ level_ids: UUID[] }>(`/missions/${id}/levels/batch/`, data),

  // POST /api/v1/missions/{id}/questions/
  addQuestions: (id: UUID, data: { level_id: UUID; question_ids: UUID[] }) =>
    post(`/missions/${id}/questions/`, data),

  addFavorites: (id: UUID, question_ids: UUID[]) =>
    post(`/missions/${id}/favorites/`, { question_ids }),

  exportPdf: (id: UUID) => get<any>(`/missions/${id}/export-pdf/`),

  grading: (id: UUID) => get<any>(`/missions/${id}/grading/`),
  progress: (id: UUID, params?: { class_id?: UUID }) => get<any>(`/missions/${id}/progress/`, params),
  statistics: (id: UUID, params?: { class_id?: UUID }) => get<any>(`/missions/${id}/statistics/`, params),
  learningStats: (id: UUID, params?: { class_id?: UUID }) => get<any>(`/missions/${id}/learning-stats/`, params),
  gradeAttempt: (id: UUID, attemptId: UUID, data: { score: number; feedback?: string }) =>
    patch<any>(`/missions/${id}/grading/attempts/${attemptId}/`, data),
  generateVariant: (id: UUID, data: { question_id: UUID; level_id: UUID; student_id: UUID; variant_mode?: string }) =>
    post<any>(`/missions/${id}/grading/generate-variant/`, data),

  // POST /api/v1/missions/{id}/publish/
  publish: (id: UUID) => post(`/missions/${id}/publish/`),

  qrcodeInfo: (id: UUID) => get<any>(`/missions/${id}/qrcode/info`),
  qrcodeImageUrl: (id: UUID) => `/api/v1/missions/${id}/qrcode`,

  // POST /api/v1/missions/{id}/clone/
  clone: (id: UUID) => post<{ id: UUID }>(`/missions/${id}/clone/`),

  // POST /api/v1/missions/{id}/clone-with-class/
  cloneWithClass: (id: UUID, data: { class_id: UUID; start_at?: string; end_at: string }) =>
    post<{ id: UUID; mission_no: string }>(`/missions/${id}/clone-with-class/`, data),

  // Teacher B/C guidance
  startGuidance: (data: { question_id: UUID; mode: string }) =>
    post<any>('/missions/guidance/start/', data),
  guidanceReply: (sessionId: UUID, data: { user_answer: string }) =>
    post<any>(`/missions/guidance/reply/${sessionId}/`, data),

  // Phase 4 teacher wrong-book matrix. New writes intentionally omit a slash.
  wrongbookMatrix: (id: UUID, params?: { class_id?: UUID }) => get<any>(`/missions/${id}/wrongbook-matrix`, params),
  saveWrongbookMatrix: (id: UUID, data: { version: number; cells: Array<{ student_id: UUID; source_question_id: UUID; wrong: boolean }> }) => patch<any>(`/missions/${id}/wrongbook-matrix`, data),
  generateWrongbook: (id: UUID, data: { version: number; idempotency_key: string; cell_ids?: UUID[]; related_limit?: number }) => post<any>(`/missions/${id}/wrongbook-matrix/generate`, data),
  // AI-first teacher selection fallback. The legacy generator above remains unchanged.
  generateTeacherWrongbook: (id: UUID, data: { version: number; idempotency_key: string; cell_ids?: UUID[]; class_id?: UUID }) => post<any>(`/missions/${id}/wrongbook-matrix/teacher-generate`, data),
  wrongbookGeneration: (id: UUID, batchId: UUID) => get<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}`),
  wrongbookHistory: (id: UUID) => get<any>(`/missions/${id}/wrongbook-matrix/history`),
  wrongbookStudentHistory: (id: UUID, studentId: UUID) => get<any>(`/missions/${id}/wrongbook-matrix/students/${studentId}`),
  wrongbookSummary: (id: UUID, params?: { class_id?: UUID }) => get<any>(`/missions/${id}/wrongbook-matrix/summary`, params),
  refreshWrongbookScope: (id: UUID, data?: { class_id?: UUID }) => post<any>(`/missions/${id}/wrongbook-matrix/refresh-scope`, data || {}),
  closeWrongbookMatrix: (id: UUID) => post<any>(`/missions/${id}/wrongbook-matrix/close`),
  retryWrongbookGeneration: (id: UUID, batchId: UUID) => post<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/retry`),
  wrongbookRecommendations: (id: UUID, batchId: UUID, data?: { limit?: number }) => data ? post<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/recommendations`, data) : get<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/recommendations`),
  confirmWrongbookRecommendations: (id: UUID, batchId: UUID, data: { recommendation_ids: UUID[]; idempotency_key: string }) => post<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/recommendations/confirm`, data),
  teacherWrongbookCandidateGroups: (id: UUID, batchId: UUID) => get<any[]>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/candidate-groups`),
  teacherWrongbookCandidateGroupNext: (id: UUID, batchId: UUID, itemId: UUID, data: { excluded_question_ids: string[] }) => post<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/candidate-groups/${itemId}/next`, data),
  confirmTeacherWrongbookCandidateGroups: (id: UUID, batchId: UUID, data: { groups: Array<{ student_id: UUID; source_wrong_book_item_id: UUID; candidate_question_ids: UUID[] }>; idempotency_key: string }) => post<any>(`/missions/${id}/wrongbook-matrix/generation/${batchId}/candidate-groups/confirm`, data),
}
