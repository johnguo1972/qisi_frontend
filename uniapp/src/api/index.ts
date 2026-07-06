import { get, post } from '@/utils/request.ts'

export const authApi = {
  login: (mobile: string, verifyCode: string, roleType?: string) => {
    const data: Record<string, any> = { mobile, verify_code: verifyCode }
    if (roleType) data.role_type = roleType
    return post<{ access_token: string; refresh_token: string; user: any }>('/auth/login', data)
  },
  sendCode: (mobile: string, scene: string = 'login') => post('/auth/send-code', { mobile, scene }),
  logout: () => post('/auth/logout'),
  getProfile: () => get<any>('/profile/me'),
}

export { institutionApi, classApi, studentClassApi, teacherApi } from './institutions'
export { questionApi } from './questions'
export { missionApi } from './missions'
