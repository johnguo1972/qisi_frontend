import { del, get, post, put } from '@/utils/request'
export { qrcodeApi } from './qrcode'
export { wechatApi } from './wechat'

export const authApi = {
  login: (mobile: string, verifyCode: string, roleType?: string) => {
    const data: Record<string, any> = { mobile, verify_code: verifyCode }
    if (roleType) data.role_type = roleType
    return post<{ access_token: string; refresh_token: string; user: any }>('/auth/login', data)
  },
  sendCode: (mobile: string, scene: string = 'login') => post('/auth/send-code', { mobile, scene }),
  switchRole: (role: string) => post<{ access_token: string; refresh_token: string; user: any }>('/auth/switch-role', { role }),
  logout: () => post('/auth/logout'),
  getProfile: () => get<any>('/profile/me'),
  updateProfile: (data: { display_name?: string; grade_level?: string | null }) => put<any>('/profile/me', data),
}

export { institutionApi, classApi, studentClassApi, teacherApi } from './institutions'
export { questionApi } from './questions'
export { missionApi } from './missions'
export { practiceApi } from './student'
export const wechatLogin = (code: string) => post<any>('/auth/wechat-login', { code })
export const wechatBind = (data: any) => post<any>('/auth/wechat-bind', data)
export const parentApi = {
  children: () => get<any[]>('/parent/children'),
  setContext: (childId: string) => post('/parent/context', { student_id: childId }),
  overview: () => get<any>('/parent/overview'),
  missions: (params?: { scope?: string; class_id?: string }) => get<any>('/parent/missions', params),
  missionDetail: (missionId: string) => get<any>(`/parent/missions/${missionId}`),
  createBindRequest: (bindCode: string, relationType: string = 'guardian') =>
    post('/parent/bind-requests', { bind_code: bindCode, relation_type: relationType }),
  pendingRequests: () => get<any[]>('/parent/bind-requests/pending'),
  removeBind: (bindId: string) => del(`/parent/binds/${bindId}`),
}

export const studentParentApi = {
  createBindCode: () => post<{ bind_code: string; expires_in: number }>('/student/parent-bind-codes'),
  pendingRequests: () => get<any[]>('/student/parent-bind-requests'),
  decide: (bindId: string, decision: 'approve' | 'reject') =>
    post(`/student/parent-bind-requests/${bindId}/decision`, { decision }),
}
export { courseApi, materialApi, treeApi, courseQuestionApi, variantApi } from './courses'
