<template>
  <ParentShell active-item="growth">
  <view class="page">
    <view class="header"><text class="title">成长分析</text></view>
    <MpChildSwitcher :visible="true" @changed="onChildChanged" />
    <view v-if="!selectedChild" class="state-card">请先绑定并选择孩子</view>
    <view v-else-if="loading" class="state-card">正在加载成长数据...</view>
    <view v-else-if="errorMessage" class="state-card error">{{ errorMessage }}</view>
    <view v-else class="stats">
      <view class="stat"><text class="value">{{ summary.total_attempts }}</text><text class="label">作答次数</text></view>
      <view class="stat"><text class="value">{{ summary.accuracy }}%</text><text class="label">正确率</text></view>
      <view class="stat"><text class="value">{{ summary.mastered_count }}</text><text class="label">已掌握知识点</text></view>
      <view class="stat"><text class="value">{{ summary.wrong_book_count }}</text><text class="label">错题数量</text></view>
    </view>
  </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { studentApi } from '@/api/student'
import ParentShell from '@/components/ParentShell.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import { ensurePageRole } from '@/utils/roles'

const selectedChild = ref<any>(null)
const summary = ref({ total_attempts: 0, accuracy: 0, mastered_count: 0, wrong_book_count: 0 })
const loading = ref(false)
const errorMessage = ref('')

async function onChildChanged(child: any) {
  if (!ensurePageRole('parent')) return
  selectedChild.value = child
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await studentApi.growth()
    if (response?.code !== 0) throw new Error(response?.detail || response?.message || '成长数据加载失败')
    summary.value = { ...summary.value, ...(response.data || {}) }
  } catch (error: any) {
    errorMessage.value = error?.message || '成长数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 22rpx 60rpx; box-sizing: border-box; background: #f0f2f5; }
.header { display: flex; align-items: center; justify-content: space-between; padding: 18rpx 4rpx 8rpx; }
.title { color: #303133; font-size: 38rpx; font-weight: 700; }
.state-card { margin-top: 24rpx; padding: 70rpx 30rpx; border-radius: 18rpx; background: #fff; color: #909399; text-align: center; font-size: 25rpx; }
.error { color: #f56c6c; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 20rpx; margin-top: 24rpx; }
.stat { padding: 34rpx 20rpx; border-radius: 18rpx; background: #fff; text-align: center; }
.value { display: block; color: #409eff; font-size: 42rpx; font-weight: 700; }
.label { display: block; margin-top: 12rpx; color: #909399; font-size: 23rpx; }
</style>
