<script setup lang="ts">
import { ref } from 'vue'
import { onLaunch } from '@dcloudio/uni-app'

const showDebug = ref(false)
const requestLogs = ref<Array<{url: string; method: string; status: string; detail: string}>>([])

// 定时从全局变量读取请求日志
setInterval(() => {
  const logs = (globalThis as any).__requestLogs
  if (logs) {
    requestLogs.value = [...logs].reverse()
  }
}, 1000)

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
      uni.reLaunch({ url: '/pages/teacher/layout' })
      break
    case 'student':
      uni.reLaunch({ url: '/pages/student/layout' })
      break
    case 'parent':
      uni.reLaunch({ url: '/pages/student/layout' })
      break
    case 'admin':
      uni.reLaunch({ url: '/pages/admin/home' })
      break
    default:
      uni.reLaunch({ url: '/pages/student/layout' })
  }
}
</script>

<template>
  <view id="app-container">
    <!-- 调试浮层：点击右上角 🐛 按钮查看请求日志 -->
    <view class="debug-trigger" @click.stop="showDebug = !showDebug">
      <text class="debug-icon">🐛</text>
    </view>
    <scroll-view v-if="showDebug" class="debug-panel" scroll-y @click.stop>
      <view class="debug-header">
        <text class="debug-title">请求日志</text>
        <text class="debug-close" @click.stop="showDebug = false">✕</text>
      </view>
      <view v-for="(log, i) in requestLogs" :key="i" class="debug-item">
        <text class="debug-method">{{ log.method }}</text>
        <text class="debug-status">{{ log.status }}</text>
        <text class="debug-url">{{ log.url }}</text>
        <text class="debug-detail">{{ log.detail }}</text>
      </view>
      <view v-if="requestLogs.length === 0" class="debug-empty">暂无请求日志</view>
    </scroll-view>
  </view>
</template>

<style>
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* 调试面板 */
.debug-trigger {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 99999;
  width: 44px;
  height: 44px;
  background: rgba(0,0,0,0.6);
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.debug-icon {
  font-size: 22px;
}
.debug-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 85%;
  max-width: 400px;
  z-index: 99998;
  background: rgba(0,0,0,0.9);
  padding: 16px;
}
.debug-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.2);
}
.debug-title {
  color: #fff;
  font-size: 16px;
  font-weight: bold;
}
.debug-close {
  color: #ff6b6b;
  font-size: 20px;
  padding: 4px 8px;
}
.debug-item {
  background: rgba(255,255,255,0.08);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.debug-method {
  display: inline-block;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 6px;
}
.debug-status {
  display: inline-block;
  background: #e6a23c;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-right: 6px;
}
.debug-url {
  display: block;
  color: #a8d8ff;
  font-size: 12px;
  word-break: break-all;
  margin: 4px 0;
}
.debug-detail {
  display: block;
  color: #ff9999;
  font-size: 11px;
  word-break: break-all;
}
.debug-empty {
  color: #999;
  text-align: center;
  padding: 40px 0;
  font-size: 14px;
}
</style>
