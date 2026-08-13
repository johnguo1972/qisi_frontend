<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'
import { routeForRole, type AppRole } from '@/utils/roles'

onLaunch(() => {
  console.log('App launched')

  // #ifdef MP-WEIXIN
  // 使用微信原生导航栏，避免自定义导航栏与状态栏重叠。
  uni.setNavigationBarColor({ frontColor: '#ffffff', backgroundColor: '#409EFF' })
  // #endif

  // H5 直接打开扫码入口时，不能被登录态角色跳转覆盖。
  // 例如二维码/短码链接会落到 pages/student/scan-entry。
  const pages = getCurrentPages()
  const currentRoute = pages[pages.length - 1]?.route || ''
  const browserRoute = typeof window !== 'undefined' ? window.location.hash : ''
  if (currentRoute.includes('student/scan-entry') || browserRoute.includes('/pages/student/scan-entry')) return

  // 检查保持登录状态
  const token = uni.getStorageSync('accessToken')
  const tokenExpiry = uni.getStorageSync('tokenExpiry')

  if (token) {
    // 如果有有效期标记，检查是否过期
    if (tokenExpiry) {
      const expiry = parseInt(tokenExpiry, 10)
      if (Date.now() > expiry) {
        // 已过期，清除登录状态
        uni.removeStorageSync('accessToken')
        uni.removeStorageSync('refreshToken')
        uni.removeStorageSync('tokenExpiry')
        uni.removeStorageSync('userInfo')
        return
      }
    }
    // 没有 tokenExpiry 的微信登录态同样视为有效登录态，避免冷启动停留在入口页。
    const userInfo = uni.getStorageSync('userInfo')
    const role = userInfo?.active_role as AppRole | undefined
    if (role) uni.reLaunch({ url: routeForRole(role) })
  } else if (!currentRoute.includes('login/index') && !currentRoute.includes('pages/index/index')) {
    // 通过外部入口进入受保护页面时，未登录用户必须先进入登录页。
    uni.reLaunch({ url: '/pages/login/index' })
  }
})
</script>
