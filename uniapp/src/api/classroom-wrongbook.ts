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
  wrongDrillSources: (missionId: string, params?: ClassroomWrongbookQuery) =>
    get<any>(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/sources`, params),
  uploadWrongDrill: (missionId: string, filePath: string, data: {
    class_id: string
    source_node_id?: string
  }) => new Promise<any>((resolve, reject) => {
    const token = uni.getStorageSync('accessToken')
    uni.uploadFile({
      url: getApiUrl(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/sources`),
      filePath, name: 'wrongbook_file',
      formData: { class_id: data.class_id, source_node_id: data.source_node_id || '' },
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (response) => {
        let body: any = response.data
        if (typeof body === 'string') { try { body = JSON.parse(body) } catch { /* handled below */ } }
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) resolve(body)
        else { const error: any = new Error(body?.message || '错题练习题导入失败'); error.data = body; reject(error) }
      }, fail: reject,
    })
  }),
  uploadWrongDrillMapping: (missionId: string, sourceSetId: string, filePath: string, classId: string) => new Promise<any>((resolve, reject) => {
    const token = uni.getStorageSync('accessToken')
    uni.uploadFile({
      url: getApiUrl(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/sources/${sourceSetId}/mapping`),
      filePath, name: 'mapping_file', formData: { class_id: classId },
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (response) => {
        let body: any = response.data
        if (typeof body === 'string') { try { body = JSON.parse(body) } catch { /* handled below */ } }
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) resolve(body)
        else { const error: any = new Error(body?.message || '映射表导入失败'); error.data = body; reject(error) }
      }, fail: reject,
    })
  }),
  generateWrongDrill: (missionId: string, data: { class_id: string; version: number; source_set_id: string; student_ids?: string[] }) =>
    post<any>(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/generate`, data),
  preflightWrongDrill: (missionId: string, params: any) =>
    get<any>(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/preflight`, params),
  wrongDrillBatch: (missionId: string, batchId: string, classId?: string) =>
    get<any>(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/batches/${batchId}`, classId ? { class_id: classId } : undefined),
  bulkExportWrongDrill: (missionId: string, batchId: string, data: { class_id: string; student_ids?: string[] }) =>
    post<any>(`/missions/${missionId}/classroom-wrongbook-statistics/wrong-drill/batches/${batchId}/bulk-export`, data),
}
