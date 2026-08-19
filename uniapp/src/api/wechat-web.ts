import { get, post } from '@/utils/request'

export interface WechatWebSession {
  web_session_id: string
  authorization_url: string
  expires_in: number
}

export interface WechatWebBindingStatus {
  bound: boolean
  ticket: string | null
}

export interface WechatWebLoginSession {
  access_token: string
  refresh_token: string
  user: any
}

export const wechatWebApi = {
  createSession: (requestedRole: string) =>
    post<WechatWebSession>('/auth/wechat-web/session', {
      requested_role: requestedRole,
    }),
  bindingStatus: (webSessionId: string) =>
    get<WechatWebBindingStatus>(
      '/auth/wechat-web/binding-status',
      { web_session_id: webSessionId },
      { silentError: true },
    ),
  complete: (ticket: string, requestedRole: string) =>
    post<WechatWebLoginSession>('/auth/wechat-web/binding-complete', {
      ticket,
      requested_role: requestedRole,
    }),
}
