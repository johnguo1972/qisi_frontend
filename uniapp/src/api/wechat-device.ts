import { get, post } from '@/utils/request'

export interface WechatDeviceSession {
  web_session_id: string
  qrcode_url: string
  expires_in: number
}

export interface WechatDeviceStatus {
  status: 'pending' | 'phone_authorization_required' | 'login_confirmed' | 'failed'
  bound: boolean
  ticket?: string
  error_code?: string
}

export interface WechatDeviceLoginSession {
  access_token: string
  refresh_token: string
  user: any
}

/** The H5 browser receives only an opaque completion ticket. */
export const wechatDeviceApi = {
  createSession: (requestedRole: string) =>
    post<WechatDeviceSession>('/auth/wechat-device/session', { requested_role: requestedRole }),
  status: (webSessionId: string) =>
    get<WechatDeviceStatus>(
      '/auth/wechat-device/status',
      { web_session_id: webSessionId },
      { silentError: true },
    ),
  complete: (ticket: string, requestedRole: string) =>
    post<WechatDeviceLoginSession>('/auth/wechat-device/complete', {
      ticket,
      requested_role: requestedRole,
    }),
}
