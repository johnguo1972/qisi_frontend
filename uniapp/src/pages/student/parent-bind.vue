<template>
  <view class="page">
    <view class="card">
      <text class="title">绑定手机号</text>
      <text class="hint">首次使用微信登录，请绑定已有账号的手机号。</text>
      <input v-model="mobile" type="number" maxlength="11" placeholder="手机号" />
      <view class="code">
        <input v-model="code" type="number" maxlength="6" placeholder="验证码" />
        <button size="mini" @click="send">{{ countdown ? `${countdown}s` : '获取验证码' }}</button>
      </view>
      <picker :range="['学生', '家长']" @change="role = ['student', 'parent'][$event.detail.value]">
        <view class="picker">身份：{{ role === 'student' ? '学生' : '家长' }} ▼</view>
      </picker>
      <button type="primary" :loading="loading" @click="bind">完成绑定</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { authApi, wechatApi } from '@/api/index'
import { routeForRole, type AppRole } from '@/utils/roles'

const mobile = ref('')
const code = ref('')
const role = ref('student')
const bindToken = ref('')
const countdown = ref(0)
const loading = ref(false)

onLoad((options: any) => {
  bindToken.value = options?.bindToken || ''
})

async function send() {
  if (!/^1\d{10}$/.test(mobile.value)) {
    uni.showToast({ title: '请输入正确手机号', icon: 'none' })
    return
  }
  await authApi.sendCode(mobile.value, 'login')
  countdown.value = 60
  const timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
}

async function bind() {
  if (!mobile.value || !code.value || !bindToken.value) {
    uni.showToast({ title: '请填写完整信息', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const response: any = await wechatApi.bind({
      bind_token: bindToken.value,
      mobile: mobile.value,
      verify_code: code.value,
      role_type: role.value,
    })
    if (response.code !== 0) throw new Error(response.message || '绑定失败')
    uni.setStorageSync('accessToken', response.data.access_token)
    uni.setStorageSync('refreshToken', response.data.refresh_token)
    uni.setStorageSync('userInfo', response.data.user)
    uni.reLaunch({ url: routeForRole(response.data.user.active_role as AppRole) })
  } catch (error: any) {
    uni.showToast({ title: error.message || '绑定失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f0f2f5; padding: 40rpx; }
.card { background: #fff; border-radius: 18rpx; padding: 36rpx; }
.title { display: block; font-size: 36rpx; font-weight: 600; margin-bottom: 18rpx; }
.hint { display: block; color: #888; font-size: 24rpx; margin-bottom: 32rpx; }
input, .picker { height: 82rpx; border-bottom: 1rpx solid #eee; margin-bottom: 20rpx; line-height: 82rpx; }
.code { display: flex; gap: 16rpx; }
.code input { flex: 1; }
.code button { margin-top: 22rpx; height: 58rpx; }
.picker { color: #555; }
</style>
