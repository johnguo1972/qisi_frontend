<template>
  <view class="entry-page">
    <view class="entry-card">
      <text class="entry-title">优途AI辅学系统</text>
      <text class="entry-hint">正在进入登录页面...</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { routeForRole, type AppRole } from '@/utils/roles'

function goLogin() {
  const pages = getCurrentPages()
  const currentRoute = pages[pages.length - 1]?.route || ''
  if (currentRoute && currentRoute !== 'pages/index/index') return

  const token = uni.getStorageSync('accessToken')
  const userInfo = uni.getStorageSync('userInfo')

  if (!token) {
    uni.reLaunch({ url: '/pages/login/index' })
    return
  }

  const role = (userInfo?.active_role || userInfo?.role_type || 'student') as AppRole
  uni.reLaunch({ url: routeForRole(role) })
}

onMounted(() => {
  // 留出首屏渲染时间，避免部分微信基础库在 App 启动阶段调用 reLaunch 被忽略。
  setTimeout(goLogin, 0)
})
</script>

<style scoped>
.entry-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.entry-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48rpx;
  background: #fff;
  border-radius: 16rpx;
}
.entry-title {
  color: #303133;
  font-size: 32rpx;
  font-weight: 600;
}
.entry-hint {
  margin-top: 18rpx;
  color: #909399;
  font-size: 24rpx;
}
</style>
