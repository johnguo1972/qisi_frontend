<template><view class="page"><view class="card"><text class="title">确认手机号授权</text><text class="hint">授权后将自动完成网页端登录，不会发送短信验证码。</text><button type="primary" open-type="getPhoneNumber" :loading="loading" @getphonenumber="authorizePhone">授权手机号并登录</button><text v-if="statusText" class="status">{{ statusText }}</text></view></view></template>
<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { post } from '@/utils/request'
const bridgeCode = ref(''), loading = ref(false), statusText = ref('')
onLoad((options: Record<string, string | undefined>) => { bridgeCode.value = String(options?.scene || options?.bridge_code || ''); if (!bridgeCode.value) statusText.value = '二维码无效或已过期，请返回网页重新扫码。' })
async function authorizePhone(event: any) { const phoneCode = event?.detail?.code; if (!bridgeCode.value || typeof phoneCode !== 'string' || !phoneCode) { uni.showToast({ title: '未获得手机号授权，请重新扫码。', icon: 'none' }); return }; loading.value = true; statusText.value = '正在确认授权…'; try { const response: any = await post('/auth/wechat-web/binding-phone', { bridge_code: bridgeCode.value, phone_code: phoneCode }); if (response?.code !== 0 || response?.data?.bound !== true) throw new Error(response?.message || '手机号授权失败'); statusText.value = '授权成功，请返回网页端完成登录。'; uni.showToast({ title: '授权成功', icon: 'success' }) } catch (error: any) { statusText.value = '授权失败，请返回网页重新扫码后再试。'; uni.showToast({ title: error?.message || '授权失败', icon: 'none' }) } finally { loading.value = false } }
</script>
<style scoped>.page{min-height:100vh;background:#f5f7fa;padding:48rpx 32rpx}.card{background:#fff;border-radius:20rpx;padding:48rpx 36rpx}.title,.hint,.status{display:block}.title{font-size:36rpx;font-weight:600;margin-bottom:20rpx}.hint,.status{font-size:28rpx;line-height:1.6;color:#6b7280}.status{margin-top:28rpx;color:#409eff}</style>
