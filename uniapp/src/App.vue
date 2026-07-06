<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  console.log('App launched')

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
      // 未过期，根据角色跳转
      const userInfo = uni.getStorageSync('userInfo')
      const role = userInfo?.role_type || 'student'
      navigateByRole(role)
    }
  }
})

function navigateByRole(role: string) {
  switch (role) {
    case 'teacher':
      uni.reLaunch({ url: '/pages/teacher/workbench' })
      break
    case 'student':
      uni.reLaunch({ url: '/pages/student/home' })
      break
    case 'parent':
      uni.reLaunch({ url: '/pages/student/home' })
      break
    case 'admin':
      uni.reLaunch({ url: '/pages/admin/home' })
      break
    default:
      uni.reLaunch({ url: '/pages/student/home' })
  }
}
</script>

<template>
  <view id="app-container" />
</template>

<style>
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
