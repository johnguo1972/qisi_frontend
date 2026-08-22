import { wechatApi } from '@/api/index'
export async function wxLogin(roleType: string = 'student'): Promise<{ needBindPhone: boolean; token?: string; userInfo?: any; bindToken?: string }> {
  // #ifdef MP-WEIXIN
  const code = await new Promise<string>((resolve, reject) => wx.login({ success: r => resolve(r.code), fail: reject }))
  const res: any = await wechatApi.login(code, roleType)
  if (res.code === 1001 || res.data?.need_bind_phone) return { needBindPhone: true, bindToken: res.data.bind_token }
  if (res.code !== 0) throw new Error(res.message || '微信登录失败')
  uni.setStorageSync('accessToken', res.data.access_token); uni.setStorageSync('refreshToken', res.data.refresh_token); uni.setStorageSync('userInfo', res.data.user)
  return { needBindPhone: false, token: res.data.access_token, userInfo: res.data.user }
  // #endif
  // #ifndef MP-WEIXIN
  return { needBindPhone: true }
  // #endif
}
