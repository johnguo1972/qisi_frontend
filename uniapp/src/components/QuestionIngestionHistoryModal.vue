<template>
  <view v-if="visible" class="history-overlay" @click.self="close">
    <view class="history-modal" @click.stop>
      <view class="history-header">
        <text class="history-title">新增/导入习题历史</text>
        <button size="mini" class="history-close" data-test="ingestion-history-close" @click="close">关闭</button>
      </view>

      <view v-if="loading" class="history-state">加载中...</view>
      <view v-else-if="error" class="history-state history-error">{{ error }}</view>
      <view v-else-if="!items.length" class="history-state">最近一个月暂无新增或导入习题记录</view>
      <scroll-view v-else scroll-y class="history-list">
        <view v-for="item in items" :key="item.id" class="history-item">
          <view class="history-item-main">
            <text class="history-source">{{ sourceLabel(item.source_type) }}</text>
            <text class="history-name">{{ item.source_name || '未命名来源' }}</text>
          </view>
          <text class="history-time">{{ formatTime(item.created_at) }}</text>
          <view class="history-counts">
            <text>新增 {{ item.created_count || 0 }}</text>
            <text>已跳过 {{ item.skipped_existing_count || 0 }}</text>
            <text>失败 {{ item.failed_count || 0 }}</text>
          </view>
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { getQuestionIngestionHistory, type QuestionIngestionHistoryScope } from '@/api/questions'

type IngestionHistoryItem = {
  id: string
  created_at?: string
  source_type?: string
  source_name?: string
  created_count?: number
  skipped_existing_count?: number
  failed_count?: number
}

const props = defineProps<{
  visible: boolean
  scope: QuestionIngestionHistoryScope
  courseId?: string
}>()

const emit = defineEmits<{ close: [] }>()
const items = ref<IngestionHistoryItem[]>([])
const loading = ref(false)
const error = ref('')

const SOURCE_LABELS: Record<string, string> = {
  json_package: 'JSON 数据包',
  manual_create: '手动新增',
  photo_import: '拍照导入',
  course_material_import: '课件导入',
  course_link_import: '课程关联导入',
}

function sourceLabel(sourceType?: string): string {
  return SOURCE_LABELS[String(sourceType || '').trim()] || '习题导入'
}

function formatTime(value?: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function close() {
  emit('close')
}

async function loadHistory() {
  if (!props.visible) return
  loading.value = true
  error.value = ''
  try {
    const response: any = await getQuestionIngestionHistory({
      scope: props.scope,
      ...(props.scope === 'course' && props.courseId ? { courseId: props.courseId } : {}),
    })
    const data = response?.data?.data || response?.data || response || {}
    items.value = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : [])
  } catch (reason) {
    console.error('加载习题导入历史失败:', reason)
    items.value = []
    error.value = '加载历史记录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.visible, props.scope, props.courseId] as const,
  () => { void loadHistory() },
  { immediate: true },
)
</script>

<style scoped>
.history-overlay { position: fixed; inset: 0; z-index: 220; display: flex; align-items: center; justify-content: center; padding: 32rpx; box-sizing: border-box; background: rgba(0, 0, 0, .45); }
.history-modal { width: min(760rpx, 92vw); max-height: 72vh; overflow: hidden; border-radius: 14rpx; background: #fff; box-shadow: 0 12rpx 38rpx rgba(0, 0, 0, .2); }
.history-header { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 28rpx 32rpx 20rpx; border-bottom: 1rpx solid #ebeef5; }
.history-title { color: #303133; font-size: 30rpx; font-weight: 700; }
.history-close { margin: 0; color: #606266; background: #fff; border: 1rpx solid #dcdfe6; font-size: 24rpx; }
.history-list { max-height: calc(72vh - 100rpx); }
.history-item { padding: 24rpx 32rpx; border-bottom: 1rpx solid #f0f2f5; }
.history-item-main { display: flex; align-items: center; gap: 12rpx; }
.history-source { padding: 3rpx 10rpx; color: #409eff; background: #ecf5ff; border-radius: 6rpx; font-size: 22rpx; }
.history-name { color: #303133; font-size: 26rpx; font-weight: 500; word-break: break-all; }
.history-time { display: block; margin-top: 10rpx; color: #909399; font-size: 22rpx; }
.history-counts { display: flex; gap: 22rpx; margin-top: 12rpx; color: #606266; font-size: 23rpx; }
.history-state { padding: 64rpx 32rpx; color: #909399; text-align: center; font-size: 26rpx; }
.history-error { color: #f56c6c; }
</style>
