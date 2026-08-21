<template>
  <view class="login-page">
    <view class="login-container">
      <!-- 左侧品牌区 -->
      <view class="brand-side">
        <view class="logo">优途AI辅学系统</view>
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
                  @click.stop="switchRole(tab.role)">
              <text class="tab-icon">{{ tab.icon }}</text>
              <text class="tab-text">{{ tab.label }}</text>
            </view>
          </view>

          <!-- 登录表单 -->
          <view class="form-content">
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
            <!-- #ifdef H5 -->
            <button class="wechat-web-entry" :disabled="loading" @click="switchLoginMode('wechat')">
              微信扫码登录
            </button>
            <!-- #endif -->
            <!-- #ifdef MP-WEIXIN -->
            <button class="wechat-btn" :disabled="loading" @click="handleWechatLogin">微信一键登录</button>
            <!-- #endif -->
            </template>
            <!-- #ifdef H5 -->
            <view v-else class="wechat-web-login">
              <button
                class="wechat-web-start"
                :disabled="wechatWebLoading || !wechatWebPhoneAuthorizationConfirmed"
                @click="startWechatWebLogin"
              >
                {{ wechatWebLoading ? '正在创建扫码会话...' : '开始微信扫码' }}
              </button>
              <view v-if="false" class="wechat-web-qr">
                <view v-if="false"
                  class="wechat-web-qr-frame"
                  :src="wechatWebSession.authorization_url"
                  title="微信扫码登录二维码"
                  scrolling="no"
                ></view>
              </view>
              <view v-if="wechatWebSession" class="wechat-web-qr">
                <image class="wechat-web-binding-qr-image" :src="wechatWebBindingQrUrl" mode="aspectFit" />
              </view>
              <view class="wechat-web-consent" @click="wechatWebPhoneAuthorizationConfirmed = !wechatWebPhoneAuthorizationConfirmed">
                <view class="checkbox" :class="{ checked: wechatWebPhoneAuthorizationConfirmed }">
                  <view class="checkmark"></view>
                </view>
                <text class="remember-text">手机号绑定授权确认</text>
              </view>
              <text v-if="wechatWebSession" class="wechat-web-status">{{ wechatWebStatusText }}</text>
              <view v-if="wechatWebSession && !wechatWebBindingComplete" class="wechat-web-binding-guide">
                <text>请在微信小程序完成手机号授权</text>
                <text class="wechat-web-guide-desc">完成后此页面会自动继续登录，请勿关闭页面。</text>
              </view>
              <button class="wechat-web-back" @click="switchLoginMode('phone')">
                手机号验证码登录
              </button>
            </view>
            <!-- #endif -->
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { authApi } from '@/api/index.ts'
// 微信网页扫码登录只存在于 H5，不能让小程序主包依赖该模块。
// #ifdef H5
import { wechatWebApi, type WechatWebSession } from '@/api/wechat-web'
// #endif
import { useUserStore } from '@/store/index.ts'
import { wxLogin } from '@/utils/wechat-auth'
import { persistSession, routeForRole, type AppRole } from '@/utils/roles'

const tabs = [
  { role: 'student', label: '学生', icon: '🎓' },
  { role: 'teacher', label: '教师', icon: '👩‍🏫' },
  { role: 'parent', label: '家长', icon: '👨‍👩‍👧' },
  { role: 'admin', label: '管理员', icon: '⚙️' },
]

const activeTab = ref('student')
const loginMode = ref<'phone' | 'wechat'>('phone')
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
const wechatWebSession = ref<WechatWebSession | null>(null)
const wechatWebLoading = ref(false)
const wechatWebBindingComplete = ref(false)
const wechatWebCompleting = ref(false)
const wechatWebPhoneAuthorizationConfirmed = ref(false)
const wechatWebStatusText = ref('请使用微信扫描二维码')
let wechatWebPollTimer: ReturnType<typeof setInterval> | undefined
const wechatWebBindingQrUrl = computed(() => {
  const webSessionId = wechatWebSession.value?.web_session_id
  return webSessionId
    ? `/api/v1/auth/wechat-web/binding-qrcode?web_session_id=${encodeURIComponent(webSessionId)}`
    : ''
})

function stopWechatWebPolling() {
  if (wechatWebPollTimer) {
    clearInterval(wechatWebPollTimer)
    wechatWebPollTimer = undefined
  }
}

function resetWechatWebSession() {
  stopWechatWebPolling()
  wechatWebSession.value = null
  wechatWebBindingComplete.value = false
  wechatWebCompleting.value = false
  wechatWebStatusText.value = '请使用微信扫描二维码'
}

function restoreWechatWebSessionFromCallback() {
  // #ifdef H5
  const query = window.location.hash.split('?', 2)[1] || ''
  const webSessionId = new URLSearchParams(query).get('web_session_id')
  if (!webSessionId) return
  loginMode.value = 'wechat'
  wechatWebPhoneAuthorizationConfirmed.value = true
  wechatWebSession.value = { web_session_id: webSessionId, authorization_url: '', expires_in: 0 }
  wechatWebStatusText.value = '已完成扫码，等待小程序手机号授权'
  void pollWechatWebBindingStatus()
  wechatWebPollTimer = setInterval(() => { void pollWechatWebBindingStatus() }, 3000)
  // #endif
}

function switchLoginMode(mode: 'phone' | 'wechat') {
  if (loginMode.value === mode) return
  loginMode.value = mode
  resetWechatWebSession()
}

function switchRole(role: string) {
  if (activeTab.value === role) return
  activeTab.value = role
  if (loginMode.value === 'wechat') {
    resetWechatWebSession()
    if (wechatWebPhoneAuthorizationConfirmed.value) {
      void startWechatWebLogin()
    }
  }
}

async function completeWechatWebLogin(ticket: string) {
  stopWechatWebPolling()
  wechatWebCompleting.value = true
  wechatWebStatusText.value = '正在完成登录...'
  const res = await wechatWebApi.complete(ticket, activeTab.value)
  if (res.code !== 0 || !res.data) {
    throw new Error(res.message || '微信扫码登录失败')
  }
  wechatWebBindingComplete.value = true
  persistSession(res.data)
  userStore.setUserInfo(res.data.user)
  uni.reLaunch({ url: routeForRole(res.data.user.active_role as AppRole) })
}

async function pollWechatWebBindingStatus(): Promise<boolean> {
  if (!wechatWebSession.value || wechatWebCompleting.value) return false
  try {
    const res = await wechatWebApi.bindingStatus(wechatWebSession.value.web_session_id)
    if (res.code !== 0 || !res.data) return false
    if (res.data.bound && res.data.ticket) {
      await completeWechatWebLogin(res.data.ticket)
      return true
    }
    wechatWebStatusText.value = '扫码后，请在小程序完成授权'
  } catch (e) {
    console.error('查询微信绑定状态失败:', e)
  }
  return false
}

async function startWechatWebLogin() {
  if (wechatWebLoading.value) return
  if (!wechatWebPhoneAuthorizationConfirmed.value) {
    uni.showToast({ title: '请先确认手机号绑定授权', icon: 'none' })
    return
  }
  resetWechatWebSession()
  wechatWebLoading.value = true
  wechatWebStatusText.value = '正在创建扫码会话...'
  try {
    const res = await wechatWebApi.createSession(
      activeTab.value,
      wechatWebPhoneAuthorizationConfirmed.value,
    )
    if (res.code !== 0 || !res.data?.web_session_id || !res.data.authorization_url) {
      throw new Error(res.message || '无法创建微信扫码会话')
    }
    wechatWebSession.value = res.data
    // WeChat OAuth must navigate at the top level. A nested callback would
    // leave the browser on the QR frame instead of showing the MP bridge QR.
    if (window.location.href !== res.data.authorization_url) {
      window.location.assign(res.data.authorization_url)
      return
    }
    wechatWebStatusText.value = '请使用微信扫描二维码'
    const loginCompleted = await pollWechatWebBindingStatus()
    if (!loginCompleted) {
      wechatWebPollTimer = setInterval(() => { void pollWechatWebBindingStatus() }, 3000)
    }
  } catch (e: any) {
    console.error('创建微信扫码会话失败:', e)
    wechatWebStatusText.value = '二维码创建失败，请重试'
    uni.showToast({ title: e?.message || '创建微信扫码会话失败', icon: 'none' })
  } finally {
    wechatWebLoading.value = false
  }
}

onMounted(restoreWechatWebSessionFromCallback)
onUnmounted(stopWechatWebPolling)

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
      persistSession(res.data)
      userStore.setUserInfo(res.data.user)

      // 保持登录状态：写入7天后过期时间戳
      if (rememberMe.value) {
        const expiry = Date.now() + 7 * 24 * 60 * 60 * 1000
        uni.setStorageSync('tokenExpiry', expiry.toString())
      } else {
        uni.removeStorageSync('tokenExpiry')
      }

      uni.reLaunch({ url: routeForRole(res.data.user.active_role as AppRole) })
    } else {
      const message = (res as any).code === 'ROLE_NOT_GRANTED' ? '该账号未开通此角色' : (res.message || '登录失败')
      uni.showToast({ title: message, icon: 'none' })
    }
  } catch (e: any) {
    console.error('登录失败:', e)
    const msg = e?.data?.code === 'ROLE_NOT_GRANTED' ? '该账号未开通此角色' : (e?.errMsg || e?.message || '网络异常，请重试')
    uni.showToast({ title: msg, icon: 'none' })
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
  } catch (e: any) { uni.showToast({ title: e.message || '微信登录失败', icon: 'none' }) }
  finally { loading.value = false }
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
  align-items: center;
  gap: 12rpx;
}

.code-row input {
  flex: 1;
  min-width: 0;
  margin: 0;
}
.code-btn {
  flex: 0 0 112px;
  height: 56px;
  margin: 0;
  white-space: nowrap;
  padding: 0;
  font-size: 22rpx;
  line-height: 1;
  background: #409eff;
  color: #fff;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  box-sizing: border-box;
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
.wechat-web-entry {
  width: 100%;
  margin-top: 18rpx;
  color: #07c160;
  background: #fff;
  border: 2rpx solid #07c160;
  border-radius: 8rpx;
  font-size: 28rpx;
}
.wechat-btn { margin-top: 18rpx; background: #07c160; color: #fff; font-size: 28rpx; border-radius: 8rpx; }
.wechat-web-login {
  text-align: center;
}
.wechat-web-status, .wechat-web-guide-desc {
  display: block;
  margin-top: 10rpx;
  color: #888;
  font-size: 22rpx;
}
.wechat-web-start {
  width: 100%;
  margin-top: 18rpx;
  color: #fff;
  background: #07c160;
  border-radius: 8rpx;
  font-size: 26rpx;
}
.wechat-web-start[disabled] { background: #93d7ad; }
.wechat-web-consent { display: flex; align-items: center; gap: 10rpx; margin-top: 16rpx; }
.wechat-web-qr {
  width: 360px;
  height: 420px;
  max-width: 100%;
  margin: 20rpx auto 0;
  overflow: hidden;
  background: #fff;
}
.wechat-web-qr-frame {
  width: 360px;
  height: 420px;
  max-width: 100%;
  display: block;
  border: 0;
  overflow: hidden;
}
.wechat-web-binding-qr-image { width: 360px; height: 420px; display: block; }
.wechat-web-binding-guide {
  margin-top: 18rpx;
  padding: 18rpx;
  border-radius: 8rpx;
  color: #8a5a00;
  background: #fff7e6;
  font-size: 24rpx;
}
.wechat-web-back {
  width: 100%;
  margin-top: 20rpx;
  color: #409eff;
  background: #fff;
  border: 2rpx solid #409eff;
  border-radius: 8rpx;
  font-size: 26rpx;
}

@media (max-width: 480px) {
  .wechat-web-qr,
  .wechat-web-qr-frame {
    width: 320px;
    height: 390px;
  }
}

/* #ifdef MP-WEIXIN */
.login-page input {
  height: 88rpx;
  line-height: 1.4;
  padding: 0 24rpx;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  box-sizing: border-box;
}
.login-page input:focus {
  border: 1rpx solid #409eff;
}
.login-page .code-row input {
  height: 88rpx;
  min-height: 0;
}
.login-page .code-btn {
  height: 88rpx;
}
/* #endif */

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
