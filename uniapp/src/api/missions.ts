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
  level_count?: number
  class_name?: string
  question_count?: number
  subject?: string
  creator_teacher_id?: UUID
}

export const missionApi = {
  // GET /api/v1/missions/
  list: (params?: { class_id?: UUID; subject?: string }) => get<Mission[]>('/missions/', params),

  // POST /api/v1/missions/
  create: (data: { mission_name: string; goal_text?: string; start_at?: string; end_at?: string; class_id?: UUID | null; course_id?: UUID | null; target_student_ids?: UUID[] }) =>
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
  gradeAttempt: (id: UUID, attemptId: UUID, data: { score: number; feedback?: string }) =>
    patch<any>(`/missions/${id}/grading/attempts/${attemptId}/`, data),
  generateVariant: (id: UUID, data: { question_id: UUID; level_id: UUID; student_id: UUID; variant_mode?: string }) =>
    post<any>(`/missions/${id}/grading/generate-variant/`, data),

  // POST /api/v1/missions/{id}/publish/
  publish: (id: UUID) => post(`/missions/${id}/publish/`),

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
}
