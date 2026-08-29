<template>
  <view class="page">
    <view class="card">
      <text class="title">家长绑定</text>
      <text class="hint">生成申请码后，让家长使用手机号验证码登录并输入申请码。学生确认后，家长才能查看学习数据。</text>
      <button class="primary" :loading="loadingCode" @click="createCode">生成申请码</button>
      <view v-if="bindCode" class="code-box">
        <text class="code-label">申请码（1小时内有效）</text>
        <text class="code">{{ bindCode }}</text>
        <button class="copy-button" @click="copyCode">复制申请码</button>
        <text class="code-tip">请将申请码提供给家长，不要公开发布。</text>
      </view>
    </view>

    <view class="card">
      <view class="section-title">待确认申请</view>
      <view v-if="!requests.length" class="empty">暂无待确认的家长绑定申请</view>
      <view v-for="item in requests" :key="item.id" class="request-row">
        <view class="request-info">
          <text class="request-name">{{ item.parent_name || '家长' }}</text>
          <text class="request-detail">{{ item.parent_mobile || '' }} · {{ relationLabel(item.relation_type) }}</text>
        </view>
        <view class="actions">
          <button class="approve" :loading="processing === item.id" @click="decide(item.id, 'approve')">同意</button>
          <button class="reject" :disabled="processing === item.id" @click="decide(item.id, 'reject')">拒绝</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { studentParentApi } from '@/api/index'

const bindCode = ref('')
const requests = ref<any[]>([])
const loadingCode = ref(false)
const processing = ref('')

function messageOf(response: any, fallback: string) {
  return response?.detail || response?.message || fallback
}

async function createCode() {
  loadingCode.value = true
  try {
    const response: any = await studentParentApi.createBindCode()
    if (response?.code !== 0) throw new Error(messageOf(response, '申请码生成失败'))
    bindCode.value = response.data?.bind_code || ''
  } catch (error: any) {
    uni.showToast({ title: error?.message || '申请码生成失败', icon: 'none' })
  } finally {
    loadingCode.value = false
  }
}

function copyCode() {
  if (!bindCode.value) return
  uni.setClipboardData({
    data: bindCode.value,
    success: () => uni.showToast({ title: '申请码已复制', icon: 'success' }),
    fail: () => uni.showToast({ title: '复制失败，请手动输入', icon: 'none' }),
  })
}

async function loadRequests() {
  try {
    const response: any = await studentParentApi.pendingRequests()
    if (response?.code !== 0) throw new Error(messageOf(response, '绑定申请加载失败'))
    requests.value = Array.isArray(response.data) ? response.data : []
  } catch (error: any) {
    uni.showToast({ title: error?.message || '绑定申请加载失败', icon: 'none' })
  }
}

async function decide(bindId: string, decision: 'approve' | 'reject') {
  processing.value = bindId
  try {
    const response: any = await studentParentApi.decide(bindId, decision)
    if (response?.code !== 0) throw new Error(messageOf(response, '操作失败'))
    uni.showToast({ title: decision === 'approve' ? '已同意绑定' : '已拒绝绑定', icon: 'success' })
    await loadRequests()
  } catch (error: any) {
    uni.showToast({ title: error?.message || '操作失败', icon: 'none' })
  } finally {
    processing.value = ''
  }
}

function relationLabel(value: string) {
  return ({ father: '父亲', mother: '母亲', guardian: '监护人' } as Record<string, string>)[value] || '监护人'
}

onMounted(loadRequests)
onShow(loadRequests)
</script>

<style scoped>
.page { min-height: 100vh; padding: 30rpx 24rpx 60rpx; box-sizing: border-box; background: #f0f2f5; }
.card { margin-bottom: 24rpx; padding: 32rpx; border-radius: 18rpx; background: #fff; }
.title { display: block; color: #303133; font-size: 36rpx; font-weight: 700; }
.hint { display: block; margin-top: 18rpx; color: #909399; font-size: 24rpx; line-height: 1.6; }
.primary { margin: 28rpx 0 0; color: #fff; background: #409eff; font-size: 26rpx; }
.code-box { margin-top: 24rpx; padding: 24rpx; border-radius: 14rpx; background: #ecf5ff; text-align: center; }
.code-label, .code-tip { display: block; color: #606266; font-size: 23rpx; }
.code { display: block; margin: 14rpx 0; color: #1677ff; font-size: 48rpx; font-weight: 700; letter-spacing: 8rpx; }
.copy-button { width: 260rpx; margin: 0 auto 16rpx; color: #409eff; background: #fff; border: 1rpx solid #409eff; font-size: 24rpx; }
.code-tip { color: #909399; }
.section-title { display: block; margin-bottom: 18rpx; color: #303133; font-size: 29rpx; font-weight: 600; }
.empty { padding: 44rpx 0; color: #909399; text-align: center; font-size: 24rpx; }
.request-row { display: flex; align-items: center; justify-content: space-between; gap: 18rpx; padding: 20rpx 0; border-top: 1rpx solid #f0f0f0; }
.request-info { flex: 1; min-width: 0; }
.request-name, .request-detail { display: block; }
.request-name { color: #303133; font-size: 27rpx; }
.request-detail { margin-top: 8rpx; color: #909399; font-size: 22rpx; }
.actions { display: flex; gap: 12rpx; }
.actions button { min-width: 100rpx; margin: 0; padding: 0 12rpx; font-size: 22rpx; line-height: 2.2; }
.approve { color: #fff; background: #67c23a; }
.reject { color: #f56c6c; background: #fff; border: 1rpx solid #fbc4c4; }
</style>
