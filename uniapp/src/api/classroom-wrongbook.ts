import { get, patch } from '@/utils/request'
import { getApiUrl } from '@/utils/api-config'

export interface ClassroomWrongbookQuery {
  class_id?: string
}

export const classroomWrongbookApi = {
  statistics: (missionId: string, params?: ClassroomWrongbookQuery) =>
    get<any>(`/missions/${missionId}/classroom-wrongbook-statistics`, params),
  save: (missionId: string, data: {
    class_id: string
    version: number
    cells: Array<{ student_id: string; source_question_id: string; wrong: boolean }>
  }) => patch<any>(`/missions/${missionId}/classroom-wrongbook-statistics`, data),
  upload: (missionId: string, filePath: string, data: {
    class_id: string
    version: number
    replace_scope?: string
  }) => new Promise<any>((resolve, reject) => {
    const token = uni.getStorageSync('accessToken')
    uni.uploadFile({
      url: getApiUrl(`/missions/${missionId}/classroom-wrongbook-statistics/import`),
      filePath,
      name: 'file',
      formData: {
        class_id: data.class_id,
        version: String(data.version),
        replace_scope: data.replace_scope || 'offline_students_in_uploaded_nodes',
      },
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (response) => {
        let body: any = response.data
        if (typeof body === 'string') {
          try { body = JSON.parse(body) } catch { /* handled below */ }
        }
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) {
          resolve(body)
        } else {
          const error: any = new Error(body?.message || 'Excel 导入失败')
          error.data = body
          reject(error)
        }
      },
      fail: reject,
    })
  }),
}
