<template>
  <view class="page">
    <view class="card">
      <text class="title">进入作业</text>
      <text class="hint">请扫描教师提供的作业二维码，或输入二维码中的6位作业码。</text>
      <input v-model="shortCode" maxlength="6" placeholder="请输入6位作业码" class="code-input" />
      <button type="primary" :loading="loading" @click="lookup">查询作业</button>
      <button class="scan-button" @click="scan">扫码进入</button>
      <button v-if="isWechat && mission" class="wechat-button" @click="openMiniProgram">打开微信小程序</button>
      <view v-if="mission" class="mission">
        <text class="name">{{ mission.mission_name }}</text>
        <text>截止：{{ mission.end_at || '未设置' }}</text>
        <button type="primary" @click="enter">进入作业</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { qrcodeApi } from '@/api/index'

const shortCode = ref('')
const mission = ref<any>(null)
const loading = ref(false)
const isWechat = /MicroMessenger/i.test((globalThis as any).navigator?.userAgent || '')

onLoad((options: any) => {
  if (options?.student_code && options?.code) {
    uni.navigateTo({ url: `/pages/student/paper-scan?studentCode=${options.student_code}&missionCode=${options.code}&pageNo=${options.page || 1}` })
    return
  }
  const scene = String(options?.scene || options?.code || '').trim()
  if (scene) handleScanValue(scene)
})

function handleScanValue(raw: string) {
  const value = decodeURIComponent(raw)
  const paper = value.match(/\/paper\/([^/]+)\/([^/]+)\/p(\d+)/i)
  if (paper) {
    uni.navigateTo({ url: `/pages/student/paper-scan?studentCode=${paper[1]}&missionCode=${paper[2]}&pageNo=${paper[3]}` })
    return
  }
  const match = value.match(/\/hw\/([A-Za-z0-9]{6})(?:\?|$)/i)
  shortCode.value = (match?.[1] || value.slice(-6)).toUpperCase()
  lookup()
}

async function lookup() {
  shortCode.value = shortCode.value.trim().toUpperCase()
  if (!/^[A-Z0-9]{6}$/.test(shortCode.value)) { uni.showToast({ title: '请输入6位作业码', icon: 'none' }); return }
  loading.value = true
  try { const res: any = await qrcodeApi.info(shortCode.value); mission.value = res.data }
  catch { uni.showToast({ title: '作业不存在或已过期', icon: 'none' }) }
  finally { loading.value = false }
}

function scan() {
  // #ifdef MP-WEIXIN
  uni.scanCode({ success: (result) => handleScanValue(String(result.result || '')) })
  // #endif
  // #ifndef MP-WEIXIN
  uni.showToast({ title: '当前环境请手动输入作业码', icon: 'none' })
  // #endif
}

async function openMiniProgram() {
  try {
    const res: any = await qrcodeApi.urlLink(shortCode.value)
    const url = res.data?.url_link
    if (url) (globalThis as any).location.href = url
  } catch { uni.showToast({ title: '微信小程序链接暂不可用', icon: 'none' }) }
}

async function enter() {
  try {
    const res: any = await qrcodeApi.enter(shortCode.value)
    uni.navigateTo({ url: res.data.redirect_url })
  } catch { uni.showToast({ title: '请先登录或无权进入该作业', icon: 'none' }) }
}
</script>

<style scoped>
.page { min-height: 100vh; background: #f0f2f5; padding: 48rpx 24rpx; box-sizing: border-box; }
.card { background: #fff; border-radius: 16rpx; padding: 40rpx 32rpx; }
.title { display: block; font-size: 36rpx; font-weight: bold; margin-bottom: 32rpx; }
.code-input { height: 88rpx; border: 1px solid #dcdfe6; border-radius: 8rpx; padding: 0 24rpx; margin-bottom: 24rpx; letter-spacing: 8rpx; text-transform: uppercase; }
.scan-button { margin-top: 20rpx; }
.wechat-button { margin-top: 20rpx; background: #07c160; color: #fff; }
.mission { margin-top: 36rpx; padding-top: 28rpx; border-top: 1px solid #eee; display: flex; flex-direction: column; gap: 20rpx; }
.name { font-size: 32rpx; font-weight: bold; }
</style>
