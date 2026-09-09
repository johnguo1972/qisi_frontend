<template>
  <view class="page">
    <view class="card">
      <text class="state-icon" :class="`state-${bindingState}`">{{ bindingState === 'confirmed' ? '✓' : bindingState === 'error' ? '!' : '…' }}</text>
      <text class="title">{{ pageTitle }}</text>
      <text class="hint">{{ pageHint }}</text>
      <button
        v-if="bindingState === 'phone_required' && phoneBindingToken"
        type="primary"
        :loading="loading"
        open-type="getPhoneNumber"
        @getphonenumber="authorizePhone"
      >
        授权手机号并登录网页
      </button>
      <text v-if="statusText" class="status">{{ statusText }}</text>
      <text v-if="bindingState === 'confirmed'" class="return-hint">请返回电脑网页继续使用。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { post } from '@/utils/request'

const bridgeCode = ref('')
const phoneBindingToken = ref('')
const loading = ref(false)
const statusText = ref('')
const bindingState = ref<'checking' | 'phone_required' | 'confirmed' | 'error'>('checking')

const pageTitle = computed(() => {
  if (bindingState.value === 'confirmed') return '微信授权成功'
  if (bindingState.value === 'phone_required') return '需要授权手机号'
  if (bindingState.value === 'error') return '网页授权未完成'
  return '正在确认网页登录'
})

const pageHint = computed(() => {
  if (bindingState.value === 'confirmed') return '网页端正在自动完成登录，不需要再次扫码或输入短信验证码。'
  if (bindingState.value === 'phone_required') return '当前微信身份尚未绑定平台账号，请授权微信手机号完成网页登录。'
  if (bindingState.value === 'error') return '请根据下方提示处理，或返回网页重新生成二维码。'
  return '正在确认当前微信身份，请稍候。'
})

function deviceErrorMessage(code: unknown, fallback: string) {
  switch (code) {
    case 'DEVICE_BRIDGE_INVALID':
      return '二维码已被使用，请返回网页等待登录，不要重复扫码。'
    case 'DEVICE_SESSION_EXPIRED':
      return '二维码已过期，请返回网页重新生成二维码。'
    case 'DEVICE_BROWSER_MISMATCH':
      return '网页登录会话已失效，请返回网页重新生成二维码。'
    case 'DEVICE_ROLE_CONFLICT':
      return '当前微信账号没有开通所选角色，请返回网页切换角色。'
    case 'DEVICE_PHONE_TOKEN_INVALID':
      return '手机号授权已失效，请返回网页重新扫码。'
    default:
      return fallback
  }
}

function loginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: 'weixin',
      success: (result) => result.code ? resolve(result.code) : reject(new Error('未获得微信登录凭证')),
      fail: (error) => reject(error),
    })
  })
}

async function confirmWechatIdentity() {
  if (!bridgeCode.value || loading.value || bindingState.value === 'confirmed') return
  loading.value = true
  bindingState.value = 'checking'
  statusText.value = '正在确认微信身份…'
  try {
    const response: any = await post('/auth/wechat-device/scan', {
      bridge_code: bridgeCode.value,
      login_code: await loginCode(),
    })
    if (response?.code !== 0 || !response?.data?.status) {
      throw new Error(deviceErrorMessage(response?.code, response?.message || '微信身份确认失败'))
    }
    if (response.data.status === 'login_confirmed') {
      bindingState.value = 'confirmed'
      statusText.value = '确认成功，网页端正在自动登录。'
      return
    }
    if (response.data.status === 'phone_authorization_required' && response.data.phone_binding_token) {
      bindingState.value = 'phone_required'
      phoneBindingToken.value = response.data.phone_binding_token
      statusText.value = '请点击下方按钮授权微信手机号。'
      return
    }
    throw new Error('二维码状态无效，请返回网页重新扫码。')
  } catch (error: any) {
    bindingState.value = 'error'
    statusText.value = error?.message || '确认失败，请返回网页重新扫码。'
  } finally {
    loading.value = false
  }
}

async function authorizePhone(event: any) {
  const phoneCode = event?.detail?.code
  if (!phoneBindingToken.value || typeof phoneCode !== 'string' || !phoneCode) {
    uni.showToast({ title: '未获得手机号授权，请重新扫码。', icon: 'none' })
    return
  }
  loading.value = true
  bindingState.value = 'phone_required'
  statusText.value = '正在确认手机号授权…'
  try {
    const response: any = await post('/auth/wechat-device/phone', {
      phone_binding_token: phoneBindingToken.value,
      phone_code: phoneCode,
    })
    if (response?.code !== 0 || response?.data?.status !== 'login_confirmed') {
      throw new Error(deviceErrorMessage(response?.code, response?.message || '手机号授权失败'))
    }
    phoneBindingToken.value = ''
    bindingState.value = 'confirmed'
    statusText.value = '授权成功，网页端正在自动登录。'
    uni.showToast({ title: '授权成功', icon: 'success' })
  } catch (error: any) {
    bindingState.value = 'error'
    statusText.value = error?.message || '授权失败，请返回网页重新扫码。'
    uni.showToast({ title: statusText.value, icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((options: Record<string, string | undefined>) => {
  bridgeCode.value = String(options?.scene || options?.bridge_code || '')
  if (!bridgeCode.value) {
    bindingState.value = 'error'
    statusText.value = '二维码无效或已过期，请返回网页重新扫码。'
    return
  }
  void confirmWechatIdentity()
})
</script>

<style scoped>
.page { min-height: 100vh; padding: 48rpx 32rpx; background: #f5f7fa; }
.card { padding: 48rpx 36rpx; border-radius: 20rpx; background: #fff; text-align: center; }
.state-icon { display: block; width: 84rpx; height: 84rpx; margin: 0 auto 24rpx; border-radius: 50%; background: #409eff; color: #fff; font-size: 58rpx; line-height: 84rpx; }
.state-confirmed { background: #07c160; }
.state-error { background: #f56c6c; }
.title, .hint, .status, .return-hint { display: block; }
.title { margin-bottom: 20rpx; font-size: 36rpx; font-weight: 600; }
.hint, .status, .return-hint { color: #6b7280; font-size: 28rpx; line-height: 1.6; }
.status { margin-top: 28rpx; color: #409eff; }
.return-hint { margin-top: 20rpx; color: #07c160; }
button { margin-top: 36rpx; }
</style>
