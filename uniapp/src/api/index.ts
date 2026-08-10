import { get, post, put } from '@/utils/request'

export const authApi = {
  login: (mobile: string, verifyCode: string, roleType?: string) => {
    const data: Record<string, any> = { mobile, verify_code: verifyCode }
    if (roleType) data.role_type = roleType
    return post<{ access_token: string; refresh_token: string; user: any }>('/auth/login', data)
  },
  sendCode: (mobile: string, scene: string = 'login') => post('/auth/send-code', { mobile, scene }),
  logout: () => post('/auth/logout'),
  getProfile: () => get<any>('/profile/me'),
  updateProfile: (data: { display_name?: string; grade_level?: string | null }) => put<any>('/profile/me', data),
}

export { institutionApi, classApi, studentClassApi, teacherApi } from './institutions'
export { questionApi } from './questions'
export { missionApi } from './missions'
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
  wechatLogin: (code: string) => post<any>('/auth/wechat-login', { code }),
  wechatBind: (data: any) => post<any>('/auth/wechat-bind', data),
}
export { courseApi, materialApi, treeApi, courseQuestionApi, variantApi } from './courses'
