<template>
  <view class="login-page">
    <view class="login-container">
      <!-- 左侧品牌区 -->
      <view class="brand-side">
        <view class="logo">A自习室</view>
        <text class="brand-desc">AI 智能学习辅导系统</text>
        <view class="feature-list">
          <view class="feature-item">
            <text class="feature-icon">📚</text>
            <text class="feature-text">苏格拉底式引导教学</text>
          </view>
          <view class="feature-item">
            <text class="feature-icon">📊</text>
            <text class="feature-text">智能错题追踪分析</text>
          </view>
          <view class="feature-item">
            <text class="feature-icon">👨‍👩‍👧</text>
            <text class="feature-text">家长实时进度同步</text>
          </view>
        </view>
      </view>
      <!-- 右侧表单区 -->
      <view class="form-side">
        <view class="form">
          <!-- Tab 导航 -->
          <view class="tab-bar">
            <view v-for="tab in tabs" :key="tab.role"
                  class="tab-item"
                  :class="{ active: activeTab === tab.role }"
                  @click.stop="activeTab = tab.role">
              <text class="tab-icon">{{ tab.icon }}</text>
              <text class="tab-text">{{ tab.label }}</text>
            </view>
          </view>

          <!-- 登录表单 -->
          <view class="form-content">
            <view class="form-title">{{ currentTabLabel }}登录</view>
            <view class="form-item">
              <text class="label">手机号</text>
              <input v-model="mobile" type="tel" placeholder="请输入手机号" maxlength="11" />
            </view>
            <view class="form-item">
              <text class="label">验证码</text>
              <view class="code-row">
                <input v-model="code" type="text" placeholder="请输入验证码" maxlength="6" />
                <button :disabled="countdown > 0" @click="sendCode" class="code-btn">
                  {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
                </button>
              </view>
            </view>
            <view class="remember-row">
              <view class="checkbox" :class="{ checked: rememberMe }" @click="rememberMe = !rememberMe">
                <view class="checkmark"></view>
              </view>
              <text class="remember-text" @click="rememberMe = !rememberMe">保持7天登录状态</text>
            </view>
            <button class="login-btn" :disabled="loading" @click="handleLogin">
              {{ loading ? '登录中...' : '登 录' }}
            </button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'

const tabs = [
  { role: 'student', label: '学生', icon: '🎓' },
  { role: 'teacher', label: '教师', icon: '👩‍🏫' },
  { role: 'parent', label: '家长', icon: '👨‍👩‍👧' },
  { role: 'admin', label: '管理员', icon: '⚙️' },
]

const activeTab = ref('student')
const currentTabLabel = computed(() => {
  const tab = tabs.find(t => t.role === activeTab.value)
  return tab ? tab.label : ''
})

const mobile = ref('')
const code = ref('')
const countdown = ref(0)
const loading = ref(false)
const rememberMe = ref(false)
const userStore = useUserStore()

async function sendCode() {
  if (!mobile.value || mobile.value.length !== 11) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  try {
    await authApi.sendCode(mobile.value)
    countdown.value = 60
    const timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
    uni.showToast({ title: '验证码已发送', icon: 'success' })
  } catch (e: any) {
    console.error('发送验证码失败:', e)
    uni.showToast({ title: '发送验证码失败，请重试', icon: 'none' })
  }
}

async function handleLogin() {
  if (loading.value) return
  if (!mobile.value || !code.value) {
    uni.showToast({ title: '请填写手机号和验证码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const res = await authApi.login(mobile.value, code.value, activeTab.value)
    if (res.code === 0) {
      uni.setStorageSync('accessToken', res.data.access_token)
      uni.setStorageSync('refreshToken', res.data.refresh_token)
      uni.setStorageSync('userInfo', res.data.user)
      userStore.setUserInfo(res.data.user)

      // 保持登录状态：写入7天后过期时间戳
      if (rememberMe.value) {
        const expiry = Date.now() + 7 * 24 * 60 * 60 * 1000
        uni.setStorageSync('tokenExpiry', expiry.toString())
      } else {
        uni.removeStorageSync('tokenExpiry')
      }

      const role = res.data.user.role_type
      navigateByRole(role)
    } else {
      uni.showToast({ title: res.message || '登录失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('登录失败:', e)
    const msg = e?.errMsg || e?.message || '网络异常，请重试'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    loading.value = false
  }
}

function navigateByRole(role: string) {
  switch (role) {
    case 'teacher':
      uni.reLaunch({ url: '/pages/teacher/layout' })
      break
    case 'student':
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

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40rpx;
}
.login-container {
  display: flex;
  width: 960px;
  max-width: 100%;
  min-height: 540px;
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

/* 左侧品牌区 */
.brand-side {
  flex: 1;
  background: linear-gradient(135deg, #409eff 0%, #6366f1 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60rpx;
  color: #fff;
}
.logo {
  font-size: 64rpx;
  font-weight: bold;
  margin-bottom: 20rpx;
}
.brand-desc {
  font-size: 28rpx;
  opacity: 0.85;
  margin-bottom: 60rpx;
}
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.feature-item {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.feature-icon {
  font-size: 36rpx;
}
.feature-text {
  font-size: 26rpx;
  opacity: 0.9;
}

/* 右侧表单区 */
.form-side {
  flex: 1.2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
}
.form {
  width: 100%;
  max-width: 420px;
}

/* Tab 导航 */
.tab-bar {
  display: flex;
  gap: 4rpx;
  margin-bottom: 40rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  padding: 4rpx;
}
.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16rpx 8rpx;
  border-radius: 8rpx;
  cursor: pointer;
  transition: all 0.2s;
}
.tab-item.active {
  background: #fff;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.08);
}
.tab-icon {
  font-size: 32rpx;
  margin-bottom: 6rpx;
}
.tab-text {
  font-size: 22rpx;
  color: #999;
  transition: color 0.2s;
}
.tab-item.active .tab-text {
  color: #409eff;
  font-weight: bold;
}

/* 表单内容 */
.form-content {
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.form-title {
  font-size: 36rpx;
  font-weight: bold;
  margin-bottom: 40rpx;
  color: #333;
}
.form-item {
  margin-bottom: 28rpx;
}
.label {
  font-size: 24rpx;
  color: #666;
  margin-bottom: 10rpx;
  display: block;
}
input {
  display: block;
  border: 2rpx solid #ddd;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 26rpx;
  width: 100%;
  height: 56px;
  line-height: 28px;
  box-sizing: border-box;
  background: #fff;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}
input:focus {
  border-color: #409eff;
}
.code-row {
  display: flex;
  gap: 12rpx;
}
.code-row input {
  flex: 1;
}
.code-btn {
  white-space: nowrap;
  padding: 0 20rpx;
  font-size: 22rpx;
  background: #409eff;
  color: #fff;
  border-radius: 8rpx;
}
.code-btn[disabled] {
  background: #ccc;
}

/* 保持登录复选框 */
.remember-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 16rpx;
}
.checkbox {
  width: 32rpx;
  height: 32rpx;
  border: 2rpx solid #ddd;
  border-radius: 6rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.checkbox.checked {
  background: #409eff;
  border-color: #409eff;
}
.checkmark {
  width: 10rpx;
  height: 16rpx;
  border-left: 3rpx solid #fff;
  border-bottom: 3rpx solid #fff;
  transform: rotate(-45deg);
  opacity: 0;
  transition: opacity 0.2s;
}
.checkbox.checked .checkmark {
  opacity: 1;
}
.remember-text {
  font-size: 22rpx;
  color: #666;
  cursor: pointer;
}

.login-btn {
  background: #409eff;
  color: #fff;
  font-size: 28rpx;
  padding: 22rpx 0;
  border-radius: 8rpx;
  margin-top: 36rpx;
}
.login-btn[disabled] {
  background: #ccc;
}

/* 横屏小屏适配 */
@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
    max-width: 520px;
    min-height: auto;
  }
  .brand-side {
    padding: 40rpx;
    min-height: 180px;
  }
  .logo {
    font-size: 48rpx;
    margin-bottom: 12rpx;
  }
  .brand-desc {
    margin-bottom: 30rpx;
  }
  .feature-list {
    flex-direction: row;
    gap: 30rpx;
  }
  .form-side {
    padding: 40rpx;
  }
  .form-title {
    font-size: 32rpx;
  }
}
</style>
