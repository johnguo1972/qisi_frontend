import { get, post } from '@/utils/request'

export const classroomFeedbackApi = {
  detail: (missionId: string, params?: { class_id?: string }) =>
    get<any>(`/missions/${missionId}/classroom-feedback`, params),
  generate: (missionId: string, data: {
    class_id: string
    matrix_version: number
    idempotency_key: string
    force?: boolean
  }) => post<any>(`/missions/${missionId}/classroom-feedback/generate`, data),
  exportPdf: (missionId: string, data: { class_id: string; report_id: string }) =>
    post<any>(`/missions/${missionId}/classroom-feedback/export-pdf`, data),
}
