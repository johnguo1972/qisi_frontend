<template>
  <ParentShell active-item="wrongbook">
  <view class="page">
    <view class="header"><text class="title">错题分析</text></view>
    <MpChildSwitcher :visible="true" @changed="onChildChanged" />
    <view v-if="!selectedChild" class="state-card">请先绑定并选择孩子</view>
    <view v-else-if="loading" class="state-card">正在加载错题...</view>
    <view v-else-if="errorMessage" class="state-card error">{{ errorMessage }}</view>
    <view v-else-if="!items.length" class="state-card">该孩子暂无错题记录</view>
    <view v-else class="list">
      <view v-for="item in items" :key="item.id" class="item">
        <text class="stem">{{ item.stem || '错题' }}</text>
        <view class="item-meta-tags">
          <text class="meta-chip">🔖 {{ item.difficulty_label || '难度未标注' }}</text>
          <text v-for="point in (item.knowledge_point_labels || [])" :key="`kp-${item.id}-${point}`" class="meta-chip">💡 {{ point }}</text>
          <text v-for="tag in (item.tags || [])" :key="`tag-${item.id}-${tag}`" class="meta-chip">🏷️ {{ tag }}</text>
        </view>
        <view class="meta"><text>{{ statusLabel(item.status, '待复习') }}</text><text>{{ formatDateTime(item.latest_wrong_at) }}</text></view>
        <view class="item-actions"><button size="mini" type="primary" @click.stop="goPractice(item.id)">加入精练</button></view>
      </view>
    </view>
  </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { wrongbookApi } from '@/api/student'
import ParentShell from '@/components/ParentShell.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import { ensurePageRole } from '@/utils/roles'
import { formatDateTime, statusLabel } from '@/utils/display-format'

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
    const response: any = await wrongbookApi.list()
    if (response?.code !== 0) throw new Error(response?.detail || response?.message || '错题加载失败')
    items.value = Array.isArray(response.data) ? response.data : []
  } catch (error: any) {
    items.value = []
    errorMessage.value = error?.message || '错题加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function goPractice(id: string) {
  uni.navigateTo({
    url: `/pages/student/wrongbook-practice-candidates?id=${id}`,
    fail: () => uni.showToast({ title: '打开关联题失败', icon: 'none' }),
  })
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
.stem { display: block; color: #303133; font-size: 27rpx; line-height: 1.5; }
.meta { display: flex; justify-content: space-between; margin-top: 10rpx; color: #909399; font-size: 22rpx; }
.item-meta-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 8rpx; margin-top: 12rpx; }
.meta-chip { padding: 4rpx 10rpx; border-radius: 999rpx; background: #f4f4f5; color: #606266; font-size: 21rpx; }
.item-actions { display: flex; justify-content: flex-end; margin-top: 12rpx; }
</style>
