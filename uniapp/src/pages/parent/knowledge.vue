<template>
  <ParentShell active-item="knowledge">
  <view class="page">
    <view class="header"><text class="title">知识掌握</text></view>
    <MpChildSwitcher :visible="true" @changed="onChildChanged" />
    <view v-if="!selectedChild" class="state-card">请先绑定并选择孩子</view>
    <view v-else-if="loading" class="state-card">正在加载知识掌握情况...</view>
    <view v-else-if="errorMessage" class="state-card error">{{ errorMessage }}</view>
    <view v-else-if="!items.length" class="state-card">暂无知识点作答数据</view>
    <view v-else class="list">
      <view v-for="item in items" :key="item.knowledge" class="item">
        <view class="row"><text class="name">{{ item.knowledge }}</text><text :class="['tag', item.mastery]">{{ masteryLabel(item.mastery) }}</text></view>
        <view class="progress"><view class="bar" :style="{ width: `${Math.min(100, Number(item.accuracy || 0))}%` }"></view></view>
        <text class="meta">正确率 {{ item.accuracy }}% · 作答 {{ item.attempt }} 次</text>
      </view>
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
import { masteryLabel } from '@/utils/display-format'

const selectedChild = ref<any>(null)
const items = ref<any[]>([])
const loading = ref(false)
const errorMessage = ref('')

async function onChildChanged(child: any) {
  if (!ensurePageRole('parent')) return
  selectedChild.value = child
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await studentApi.knowledgeMastery()
    if (response?.code !== 0) throw new Error(response?.detail || response?.message || '知识掌握加载失败')
    items.value = Array.isArray(response.data?.items) ? response.data.items : []
  } catch (error: any) {
    items.value = []
    errorMessage.value = error?.message || '知识掌握加载失败，请稍后重试'
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
.list { margin-top: 24rpx; padding: 0 24rpx; border-radius: 18rpx; background: #fff; }
.item { padding: 24rpx 0; border-bottom: 1rpx solid #f0f0f0; }
.item:last-child { border-bottom: 0; }
.row { display: flex; align-items: center; justify-content: space-between; }
.name { color: #303133; font-size: 27rpx; }
.tag { padding: 4rpx 12rpx; border-radius: 20rpx; font-size: 21rpx; }
.mastered { color: #67c23a; background: #f0f9eb; }.reviewing { color: #e6a23c; background: #fdf6ec; }.weak { color: #f56c6c; background: #fef0f0; }
.progress { height: 12rpx; margin-top: 16rpx; overflow: hidden; border-radius: 8rpx; background: #f0f2f5; }
.bar { height: 100%; border-radius: 8rpx; background: #409eff; }
.meta { display: block; margin-top: 10rpx; color: #909399; font-size: 22rpx; }
</style>
