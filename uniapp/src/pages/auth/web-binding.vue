<template>
  <view class="page">
    <view class="card">
      <text class="title">确认网页登录</text>
      <text class="hint">确认后，网页端将自动完成登录，不会发送短信验证码。</text>
      <button
        v-if="phoneBindingToken"
        type="primary"
        :loading="loading"
        open-type="getPhoneNumber"
        @getphonenumber="authorizePhone"
      >
        授权手机号并登录
      </button>
      <text v-else class="status">{{ statusText || '正在确认微信身份…' }}</text>
      <text v-if="statusText && phoneBindingToken" class="status">{{ statusText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { post } from '@/utils/request'

const bridgeCode = ref('')
const phoneBindingToken = ref('')
const loading = ref(false)
const statusText = ref('')

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
  if (!bridgeCode.value) return
  loading.value = true
  statusText.value = '正在确认微信身份…'
  try {
    const response: any = await post('/auth/wechat-device/scan', {
      bridge_code: bridgeCode.value,
      login_code: await loginCode(),
    })
    if (response?.code !== 0 || !response?.data?.status) {
      throw new Error(response?.message || '微信身份确认失败')
    }
    if (response.data.status === 'login_confirmed') {
      statusText.value = '确认成功，网页端正在自动登录。'
      return
    }
    if (response.data.status === 'phone_authorization_required' && response.data.phone_binding_token) {
      phoneBindingToken.value = response.data.phone_binding_token
      statusText.value = '请点击下方按钮授权微信手机号。'
      return
    }
    throw new Error('二维码状态无效，请返回网页重新扫码。')
  } catch (error: any) {
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
  statusText.value = '正在确认手机号授权…'
  try {
    const response: any = await post('/auth/wechat-device/phone', {
      phone_binding_token: phoneBindingToken.value,
      phone_code: phoneCode,
    })
    if (response?.code !== 0 || response?.data?.status !== 'login_confirmed') {
      throw new Error(response?.message || '手机号授权失败')
    }
    phoneBindingToken.value = ''
    statusText.value = '授权成功，网页端正在自动登录。'
    uni.showToast({ title: '授权成功', icon: 'success' })
  } catch (error: any) {
    statusText.value = error?.message || '授权失败，请返回网页重新扫码。'
    uni.showToast({ title: statusText.value, icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((options: Record<string, string | undefined>) => {
  bridgeCode.value = String(options?.scene || options?.bridge_code || '')
  if (!bridgeCode.value) {
    statusText.value = '二维码无效或已过期，请返回网页重新扫码。'
    return
  }
  void confirmWechatIdentity()
})
</script>

<style scoped>
.page { min-height: 100vh; padding: 48rpx 32rpx; background: #f5f7fa; }
.card { padding: 48rpx 36rpx; border-radius: 20rpx; background: #fff; }
.title, .hint, .status { display: block; }
.title { margin-bottom: 20rpx; font-size: 36rpx; font-weight: 600; }
.hint, .status { color: #6b7280; font-size: 28rpx; line-height: 1.6; }
.status { margin-top: 28rpx; color: #409eff; }
button { margin-top: 36rpx; }
</style>
