import { post } from '@/utils/request'

export const wechatApi = {
  login: (code: string, roleType: string = 'student') =>
    post<any>('/auth/wechat-login', { code, role_type: roleType }),
  bind: (data: { bind_token: string; mobile: string; verify_code: string; role_type: string }) => post<any>('/auth/wechat-bind', data),
}
