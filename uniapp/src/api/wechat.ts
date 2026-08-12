import { post } from '@/utils/request'

export const wechatApi = {
  login: (code: string) => post<any>('/auth/wechat-login', { code }),
  bind: (data: { bind_token: string; mobile: string; verify_code: string; role_type: string }) => post<any>('/auth/wechat-bind', data),
}
