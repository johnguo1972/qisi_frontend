<template>
  <view class="login-page">
    <view class="login-container">
      <view class="brand-side">
        <view class="logo">优途AI辅学系统</view>
        <text class="brand-desc">AI 智能学习辅导系统</text>
        <view class="feature-list">
          <view class="feature-item"><text class="feature-icon">📚</text><text>苏格拉底式引导教学</text></view>
          <view class="feature-item"><text class="feature-icon">📊</text><text>智能错题追踪分析</text></view>
          <view class="feature-item"><text class="feature-icon">👨‍👩‍👧</text><text>家长实时进度同步</text></view>
        </view>
      </view>

      <view class="form-side">
        <view class="form">
          <view class="tab-bar">
            <view v-for="tab in tabs" :key="tab.role" class="tab-item" :class="{ active: activeTab === tab.role }" @click="switchRole(tab.role)">
              <text class="tab-icon">{{ tab.icon }}</text>
              <text class="tab-text">{{ tab.label }}</text>
            </view>
          </view>

          <template v-if="loginMode === 'phone'">
            <view class="form-title">{{ currentTabLabel }}登录</view>
            <view class="form-item">
              <text class="label">手机号</text>
              <input v-model="mobile" type="tel" placeholder="请输入手机号" maxlength="11" />
            </view>
            <view class="form-item">
              <text class="label">验证码</text>
              <view class="code-row">
                <input v-model="code" type="text" placeholder="请输入验证码" maxlength="6" />
                <button :disabled="countdown > 0" class="code-btn" @click="sendCode">{{ countdown > 0 ? `${countdown}s` : '获取验证码' }}</button>
              </view>
            </view>
            <view class="remember-row" @click="rememberMe = !rememberMe">
              <view class="checkbox" :class="{ checked: rememberMe }"><view class="checkmark" /></view>
              <text class="remember-text">保持7天登录状态</text>
            </view>
            <button class="login-btn" :disabled="loading" @click="handleLogin">{{ loading ? '登录中...' : '登录' }}</button>

            <!-- #ifdef H5 -->
            <view class="wechat-login-row"><text class="wechat-login-link" @click="switchLoginMode('wechat')">微信扫码登录</text></view>
            <!-- #endif -->
            <!-- #ifdef MP-WEIXIN -->
            <button class="wechat-mini-login" :disabled="loading" @click="handleWechatLogin">微信一键登录</button>
            <!-- #endif -->
          </template>

          <!-- #ifdef H5 -->
          <template v-else>
            <view class="form-title">{{ currentTabLabel }}微信扫码登录</view>
            <view class="device-qr-panel">
              <view v-if="wechatDeviceSession" class="device-qr-image-wrap">
                <image class="device-qr-image" :src="wechatDeviceSession.qrcode_url" mode="aspectFit" show-menu-by-longpress />
              </view>
              <view v-else class="device-qr-placeholder">请确认授权后开始微信扫码</view>
            </view>
            <view class="wechat-consent" @click="phoneAuthorizationConfirmed = !phoneAuthorizationConfirmed">
              <view class="checkbox" :class="{ checked: phoneAuthorizationConfirmed }"><view class="checkmark" /></view>
              <text class="remember-text">手机号绑定授权确认</text>
            </view>
            <button class="wechat-start-btn" :disabled="wechatDeviceLoading" @click="startWechatDeviceLogin">{{ wechatDeviceLoading ? '正在生成二维码...' : '开始微信扫码' }}</button>
            <text class="wechat-status">{{ wechatDeviceStatusText }}</text>
            <button class="phone-login-back" @click="switchLoginMode('phone')">手机号验证码登录</button>
          </template>
          <!-- #endif -->
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'
import { wxLogin } from '@/utils/wechat-auth'
import { persistSession, routeForRole, type AppRole } from '@/utils/roles'
// #ifdef H5
import { wechatDeviceApi, type WechatDeviceSession } from '@/api/wechat-device'
// #endif

const tabs = [
  { role: 'student', label: '学生', icon: '🎓' },
  { role: 'teacher', label: '教师', icon: '👩‍🏫' },
  { role: 'parent', label: '家长', icon: '👨‍👩‍👧' },
  { role: 'admin', label: '管理员', icon: '⚙️' },
]
const activeTab = ref('student')
const loginMode = ref<'phone' | 'wechat'>('phone')
const mobile = ref('')
const code = ref('')
const countdown = ref(0)
const loading = ref(false)
const rememberMe = ref(false)
const userStore = useUserStore()
const currentTabLabel = computed(() => tabs.find((tab) => tab.role === activeTab.value)?.label || '')

// #ifdef H5
const wechatDeviceSession = ref<WechatDeviceSession | null>(null)
const wechatDeviceLoading = ref(false)
const wechatDeviceCompleting = ref(false)
const phoneAuthorizationConfirmed = ref(false)
const wechatDeviceStatusText = ref('请确认授权后，生成二维码并使用微信扫码。')
let wechatDevicePollTimer: ReturnType<typeof setInterval> | undefined

function stopWechatDevicePolling() {
  if (wechatDevicePollTimer) {
    clearInterval(wechatDevicePollTimer)
    wechatDevicePollTimer = undefined
  }
}

function resetWechatDeviceSession() {
  stopWechatDevicePolling()
  wechatDeviceSession.value = null
  wechatDeviceCompleting.value = false
  wechatDeviceStatusText.value = '请确认授权后，生成二维码并使用微信扫码。'
}

async function completeWechatDeviceLogin(ticket: string) {
  if (wechatDeviceCompleting.value) return
  wechatDeviceCompleting.value = true
  stopWechatDevicePolling()
  wechatDeviceStatusText.value = '正在完成登录...'
  try {
    const response = await wechatDeviceApi.complete(ticket, activeTab.value)
    if (response.code !== 0 || !response.data) throw new Error(response.message || '微信扫码登录失败')
    persistSession(response.data)
    userStore.setUserInfo(response.data.user)
    uni.reLaunch({ url: routeForRole(response.data.user.active_role as AppRole) })
  } catch (error: any) {
    wechatDeviceCompleting.value = false
    wechatDeviceStatusText.value = error?.message || '登录未完成，请重新生成二维码后再试。'
  }
}

async function pollWechatDeviceStatus(): Promise<boolean> {
  const session = wechatDeviceSession.value
  if (!session || wechatDeviceCompleting.value) return false
  try {
    const response = await wechatDeviceApi.status(session.web_session_id)
    if (response.code !== 0 || !response.data) return false
    if (response.data.ticket) {
      await completeWechatDeviceLogin(response.data.ticket)
      return true
    }
    if (response.data.status === 'pending') {
      wechatDeviceStatusText.value = '请使用微信扫描二维码并在小程序中确认。'
    } else if (response.data.status === 'phone_authorization_required') {
      wechatDeviceStatusText.value = '请在小程序中点击授权手机号，网页会自动完成登录。'
    } else {
      wechatDeviceStatusText.value = '正在等待小程序确认。'
    }
  } catch (error) {
    console.warn('查询微信扫码状态失败', error)
  }
  return false
}

async function createWechatDeviceSession() {
  if (wechatDeviceLoading.value) return
  resetWechatDeviceSession()
  wechatDeviceLoading.value = true
  wechatDeviceStatusText.value = '正在生成微信二维码...'
  try {
    const response = await wechatDeviceApi.createSession(activeTab.value)
    if (response.code !== 0 || !response.data?.web_session_id || !response.data.qrcode_url) {
      throw new Error(response.message || '二维码创建失败')
    }
    wechatDeviceSession.value = response.data
    wechatDeviceStatusText.value = '请使用微信扫描上方二维码。'
    const completed = await pollWechatDeviceStatus()
    if (!completed) wechatDevicePollTimer = setInterval(() => { void pollWechatDeviceStatus() }, 3000)
  } catch (error: any) {
    wechatDeviceStatusText.value = error?.message || '二维码创建失败，请重试。'
    uni.showToast({ title: wechatDeviceStatusText.value, icon: 'none' })
  } finally {
    wechatDeviceLoading.value = false
  }
}

async function startWechatDeviceLogin() {
  if (!phoneAuthorizationConfirmed.value) {
    uni.showToast({ title: '请先确认手机号绑定授权', icon: 'none' })
    return
  }
  await createWechatDeviceSession()
}
// #endif

function switchLoginMode(mode: 'phone' | 'wechat') {
  if (loginMode.value === mode) return
  loginMode.value = mode
  // #ifdef H5
  resetWechatDeviceSession()
  phoneAuthorizationConfirmed.value = false
  if (mode === 'wechat') void createWechatDeviceSession()
  // #endif
}

function switchRole(role: string) {
  if (activeTab.value === role) return
  activeTab.value = role
  // #ifdef H5
  if (loginMode.value === 'wechat') resetWechatDeviceSession()
  // #endif
}

async function sendCode() {
  if (!/^1\d{10}$/.test(mobile.value)) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  try {
    await authApi.sendCode(mobile.value)
    countdown.value = 60
    const timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
    uni.showToast({ title: '验证码已发送', icon: 'success' })
  } catch (error) {
    console.error('发送验证码失败', error)
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
    const response = await authApi.login(mobile.value, code.value, activeTab.value)
    if (response.code !== 0 || !response.data) throw new Error((response as any).message || '登录失败')
    persistSession(response.data)
    userStore.setUserInfo(response.data.user)
    if (rememberMe.value) {
      uni.setStorageSync('tokenExpiry', String(Date.now() + 7 * 24 * 60 * 60 * 1000))
    } else {
      uni.removeStorageSync('tokenExpiry')
    }
    uni.reLaunch({ url: routeForRole(response.data.user.active_role as AppRole) })
  } catch (error: any) {
    const message = error?.data?.code === 'ROLE_NOT_GRANTED' ? '该帐号未开通此角色' : (error?.message || '网络异常，请重试')
    uni.showToast({ title: message, icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function handleWechatLogin() {
  if (loading.value) return
  loading.value = true
  try {
    const result = await wxLogin(activeTab.value)
    if (result.needBindPhone) {
      uni.navigateTo({ url: `/pages/student/parent-bind?bindToken=${encodeURIComponent(result.bindToken || '')}` })
      return
    }
    userStore.setUserInfo(result.userInfo)
    uni.reLaunch({ url: routeForRole(result.userInfo.active_role as AppRole) })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '微信登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  // #ifdef H5
  stopWechatDevicePolling()
  // #endif
})
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 40rpx; background: linear-gradient(135deg, #667eea, #764ba2); }
.login-container { width: 960px; max-width: 100%; min-height: 540px; display: flex; overflow: hidden; background: #fff; border-radius: 16px; box-shadow: 0 20px 60px rgba(0, 0, 0, .3); }
.brand-side { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60rpx; color: #fff; background: linear-gradient(135deg, #409eff, #6366f1); }
.logo { margin-bottom: 20rpx; font-size: 64rpx; font-weight: 700; }
.brand-desc { margin-bottom: 60rpx; font-size: 28rpx; opacity: .88; }
.feature-list { display: flex; flex-direction: column; gap: 24rpx; }
.feature-item { display: flex; align-items: center; gap: 16rpx; font-size: 26rpx; }
.feature-icon { font-size: 36rpx; }
.form-side { flex: 1.2; display: flex; align-items: center; justify-content: center; padding: 40rpx; }
.form { width: 100%; max-width: 420px; }
.tab-bar { display: flex; gap: 4rpx; margin-bottom: 40rpx; padding: 4rpx; border-radius: 12rpx; background: #f5f5f5; }
.tab-item { flex: 1; display: flex; flex-direction: column; align-items: center; padding: 16rpx 8rpx; border-radius: 8rpx; cursor: pointer; }
.tab-item.active { background: #fff; box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, .08); }
.tab-icon { margin-bottom: 6rpx; font-size: 32rpx; }
.tab-text { font-size: 22rpx; color: #999; }
.tab-item.active .tab-text { color: #409eff; font-weight: 700; }
.form-title { margin-bottom: 40rpx; color: #333; font-size: 36rpx; font-weight: 700; }
.form-item { margin-bottom: 28rpx; }
.label { display: block; margin-bottom: 10rpx; color: #666; font-size: 24rpx; }
input { width: 100%; height: 56px; box-sizing: border-box; padding: 14px 16px; border: 2rpx solid #ddd; border-radius: 8px; background: #fff; font-size: 26rpx; }
.code-row { display: flex; gap: 12rpx; }
.code-row input { flex: 1; min-width: 0; }
.code-btn { flex: 0 0 112px; height: 56px; display: flex; align-items: center; justify-content: center; box-sizing: border-box; margin: 0; padding: 0; border-radius: 8rpx; background: #409eff; color: #fff; font-size: 22rpx; line-height: 1.2; text-align: center; }
.remember-row, .wechat-consent { display: flex; align-items: center; gap: 10rpx; cursor: pointer; }
.checkbox { display: flex; width: 32rpx; height: 32rpx; align-items: center; justify-content: center; border: 2rpx solid #ddd; border-radius: 6rpx; }
.checkbox.checked { border-color: #409eff; background: #409eff; }
.checkmark { width: 10rpx; height: 16rpx; border-bottom: 3rpx solid #fff; border-left: 3rpx solid #fff; opacity: 0; transform: rotate(-45deg); }
.checkbox.checked .checkmark { opacity: 1; }
.remember-text { color: #666; font-size: 22rpx; }
.login-btn, .wechat-mini-login, .wechat-start-btn, .phone-login-back { width: 100%; margin-top: 28rpx; border-radius: 8rpx; font-size: 28rpx; }
.login-btn { padding: 22rpx 0; background: #409eff; color: #fff; }
.wechat-mini-login, .wechat-start-btn { background: #07c160; color: #fff; }
.wechat-login-row { display: flex; justify-content: flex-end; margin-top: 16rpx; }
.wechat-login-link { color: #07c160; font-size: 24rpx; text-decoration: underline; cursor: pointer; }
.device-qr-panel { display: flex; min-height: 320px; align-items: center; justify-content: center; border: 1rpx solid #e5e7eb; border-radius: 12rpx; background: #fff; }
.device-qr-image-wrap { width: 320px; height: 320px; max-width: 100%; }
.device-qr-image { width: 100%; height: 100%; }
.device-qr-placeholder, .wechat-status { color: #7a7a7a; font-size: 24rpx; text-align: center; }
.wechat-consent { margin-top: 18rpx; }
.wechat-status { display: block; min-height: 42rpx; margin-top: 18rpx; line-height: 1.5; }
.phone-login-back { border: 2rpx solid #409eff; background: #fff; color: #409eff; }
@media (max-width: 900px) { .login-container { flex-direction: column; max-width: 520px; } .brand-side { min-height: 180px; padding: 40rpx; } .feature-list { flex-direction: row; gap: 24rpx; } .feature-item { font-size: 22rpx; } }
</style>
