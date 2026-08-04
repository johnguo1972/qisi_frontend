import { post, get, put, del } from '@/utils/request'

export interface Mission {
  id: string | number
  mission_no: string
  mission_name: string
  goal_text?: string
  end_at?: string
  status: string
  level_count?: number
  creator_teacher_id?: number
}

export const missionApi = {
  // GET /api/v1/missions/
  list: (params?: { class_id?: number | string }) => get<Mission[]>('/missions/', params),

  // POST /api/v1/missions/
  create: (data: { mission_name: string; goal_text?: string; end_at?: string; class_id?: string; course_id?: string; target_student_ids?: string[] }) =>
    post<{ id: number }>('/missions/', data),

  // GET /api/v1/missions/{id}/
  detail: (id: string | number) => get<any>(`/missions/${id}/`),

  // PUT /api/v1/missions/{id}/
  update: (id: string | number, data: any) => put<any>(`/missions/${id}/`, data),

  // DELETE /api/v1/missions/{id}/delete/
  remove: (id: string | number) => del<any>(`/missions/${id}/delete/`),

  // GET /api/v1/missions/{id}/levels/
  levels: (id: string | number) => get<any[]>(`/missions/${id}/levels/`),

  // GET /api/v1/missions/{id}/questions/
  questions: (id: string | number) => get<any[]>(`/missions/${id}/questions/`),

  // GET /api/v1/missions/{id}/levels/<level_id>/
  levelDetail: (id: string | number, levelId: string | number) => get<any>(`/missions/${id}/levels/${levelId}/`),

  // POST /api/v1/missions/{id}/levels/
  addLevel: (id: string | number, data: { level_name: string; level_type: string; mode_policy: string }) =>
    post<{ id: number }>(`/missions/${id}/levels/`, data),

  // POST /api/v1/missions/{id}/levels/batch/
  addLevelsBatch: (id: string | number, data: { levels: Array<{
    name: string; type: string; mode: string; questionIds: number[];
  }>}) =>
    post<{ level_ids: number[] }>(`/missions/${id}/levels/batch/`, data),

  // POST /api/v1/missions/{id}/questions/
  addQuestions: (id: string | number, data: { level_id: string | number; question_ids: Array<string | number> }) =>
    post(`/missions/${id}/questions/`, data),

  addFavorites: (id: string | number, question_ids: Array<string | number>) =>
    post(`/missions/${id}/favorites/`, { question_ids }),

  exportPdf: (id: string | number) => get<any>(`/missions/${id}/export-pdf/`),

  // POST /api/v1/missions/{id}/publish/
  publish: (id: string | number) => post(`/missions/${id}/publish/`),

  // POST /api/v1/missions/{id}/clone/
  clone: (id: string | number) => post<{ id: string | number }>(`/missions/${id}/clone/`),

  // POST /api/v1/missions/{id}/clone-with-class/
  cloneWithClass: (id: number, data: { class_id: number; start_at?: string; end_at: string }) =>
    post<{ id: number; mission_no: string }>(`/missions/${id}/clone-with-class/`, data),

  // Teacher B/C guidance
  startGuidance: (data: { question_id: number; mode: string }) =>
    post<any>('/missions/guidance/start/', data),
  guidanceReply: (sessionId: string, data: { user_answer: string }) =>
    post<any>(`/missions/guidance/reply/${sessionId}/`, data),
}
