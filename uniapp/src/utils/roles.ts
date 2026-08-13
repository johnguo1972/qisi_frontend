export type AppRole = 'admin' | 'teacher' | 'parent' | 'student'

export function routeForRole(role: AppRole): string {
  if (role === 'admin') return '/pages/admin/home'
  if (role === 'teacher') return '/pages/teacher/layout'
  let studentRoute = '/pages/student/layout'
  // #ifdef MP-WEIXIN
  studentRoute = '/pages/student/mp-home'
  // #endif
  return studentRoute
}

export function currentSessionRole(): AppRole | undefined {
  const userInfo = uni.getStorageSync('userInfo')
  const role = userInfo?.active_role || userInfo?.role_type
  return role === 'admin' || role === 'teacher' || role === 'parent' || role === 'student'
    ? role
    : undefined
}

export function ensurePageRole(expectedRole: AppRole): boolean {
  const currentRole = currentSessionRole()
  if (!currentRole) return false
  if (currentRole === expectedRole) return true
  uni.reLaunch({ url: routeForRole(currentRole) })
  return false
}

export function persistSession(data: any): void {
  uni.setStorageSync('accessToken', data.access_token)
  uni.setStorageSync('refreshToken', data.refresh_token)
  uni.setStorageSync('userInfo', data.user)
}
