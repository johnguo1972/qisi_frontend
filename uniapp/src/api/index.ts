import { get, post, put } from '@/utils/request'
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
export const wechatLogin = (code: string) => post<any>('/auth/wechat-login', { code })
export const wechatBind = (data: any) => post<any>('/auth/wechat-bind', data)
export const parentApi = {
  children: () => get<any[]>('/parent/children'),
  setContext: (childId: string) => post('/parent/context', { student_id: childId }),
}
export { courseApi, materialApi, treeApi, courseQuestionApi, variantApi } from './courses'
