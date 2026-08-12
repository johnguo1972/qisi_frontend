import { post, get, del } from '@/utils/request'

export interface Favorite {
  id: string | number
  question_id: string | number
  question_no: string
  paper_title: string
  difficulty: number | null
  question_type: string
  question_type_text: string
  knowledge_points_count: number
  stem_preview: string
  created_at: string
}

export const favoriteApi = {
  // GET /api/v1/teacher/favorites
  list: (params?: { subject?: string; question_type?: string; search?: string; knowledge_point_id?: string | number }) => get<Favorite[]>('/teacher/favorites/', params || {}),

  // POST /api/v1/teacher/favorites/add
  add: (question_id: string | number) => post<{ id: number }>('/teacher/favorites/add/', { question_id }),

  // DELETE /api/v1/teacher/favorites/{question_id}
  remove: (question_id: string | number) => del(`/teacher/favorites/${question_id}/`),
}
