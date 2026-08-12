import { get, post } from '@/utils/request'

export const qrcodeApi = {
  info: (shortCode: string) => get<any>(`/hw/${shortCode}`),
  enter: (shortCode: string) => post<any>(`/hw/${shortCode}/enter`),
  urlLink: (shortCode: string) => get<any>(`/hw/${shortCode}/url-link`),
  paperEntry: (studentCode: string, missionCode: string, pageNo: number) => get<any>(`/paper/${studentCode}/${missionCode}/p${pageNo}`),
  createPracticeSheet: (data: any) => post<any>('/practice-sheets', data),
  practiceSheetInfo: (sheetCode: string) => get<any>(`/practice-sheets/${sheetCode}`),
  submitPracticeSheet: (sheetCode: string, data: any) => post<any>(`/practice-sheets/${sheetCode}/submit`, data),
  missionPaperPdf: (missionId: string) => `/api/v1/missions/${missionId}/paper-pdf`,
  wxacodeUrl: (missionId: string) => `/api/v1/missions/${missionId}/wxacode`,
}
