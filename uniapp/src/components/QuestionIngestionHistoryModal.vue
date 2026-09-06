<template>
  <view v-if="visible" class="history-overlay" @click.self="close">
    <view class="history-modal" @click.stop>
      <view class="history-header">
        <text class="history-title">{{ UI_TEXT.title }}</text>
        <button size="mini" class="history-close" data-test="ingestion-history-close" @click="close">
          {{ UI_TEXT.close }}
        </button>
      </view>

      <view v-if="loading" class="history-state">{{ UI_TEXT.loading }}</view>
      <view v-else-if="error" class="history-state history-error">{{ error }}</view>
      <view v-else-if="!items.length" class="history-state">{{ UI_TEXT.empty }}</view>
      <scroll-view v-else scroll-y class="history-list">
        <view v-for="item in items" :key="item.id" class="history-item">
          <view class="history-item-main">
            <text class="history-source">{{ sourceLabel(item.source_type) }}</text>
            <text class="history-name">{{ item.source_name || UI_TEXT.unnamedSource }}</text>
          </view>
          <text class="history-time">{{ formatTime(item.created_at) }}</text>
          <view class="history-counts">
            <text>{{ UI_TEXT.created }} {{ item.created_count || 0 }}</text>
            <text>{{ UI_TEXT.skipped }} {{ item.skipped_existing_count || 0 }}</text>
            <text>{{ UI_TEXT.failed }} {{ item.failed_count || 0 }}</text>
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

const UI_TEXT = {
  title: '\u65b0\u589e/\u5bfc\u5165\u4e60\u9898\u5386\u53f2',
  close: '\u5173\u95ed',
  loading: '\u52a0\u8f7d\u4e2d...',
  empty: '\u6700\u8fd1\u4e00\u4e2a\u6708\u6682\u65e0\u65b0\u589e\u6216\u5bfc\u5165\u4e60\u9898\u8bb0\u5f55',
  unnamedSource: '\u672a\u547d\u540d\u6765\u6e90',
  unknownTime: '\u65f6\u95f4\u672a\u77e5',
  created: '\u65b0\u589e',
  skipped: '\u5df2\u8df3\u8fc7',
  failed: '\u5931\u8d25',
  loadErrorShort: '\u52a0\u8f7d\u5386\u53f2\u8bb0\u5f55\u5931\u8d25',
  loadError: '\u52a0\u8f7d\u5386\u53f2\u8bb0\u5f55\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5',
  loadErrorLog: '\u52a0\u8f7d\u4e60\u9898\u5bfc\u5165\u5386\u53f2\u5931\u8d25:',
} as const

const SOURCE_LABELS: Record<string, string> = {
  json_import: 'JSON \u6570\u636e\u5305\u5bfc\u5165',
  manual_create: '\u624b\u52a8\u65b0\u589e',
  photo_create: '\u62cd\u7167\u5bfc\u5165',
  course_material_import: '\u8bfe\u4ef6\u5bfc\u5165',
  course_link_import: '\u8bfe\u7a0b\u5173\u8054\u5bfc\u5165',
}

function sourceLabel(sourceType?: string): string {
  return SOURCE_LABELS[String(sourceType || '').trim()] || '\u4e60\u9898\u5bfc\u5165'
}

function formatTime(value?: string): string {
  if (!value) return UI_TEXT.unknownTime
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
    if (response && Object.prototype.hasOwnProperty.call(response, 'code') && Number(response.code) !== 0) {
      throw new Error(response.message || UI_TEXT.loadErrorShort)
    }
    const data = response?.data?.data || response?.data || response || {}
    items.value = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : [])
  } catch (reason) {
    console.error(UI_TEXT.loadErrorLog, reason)
    items.value = []
    error.value = UI_TEXT.loadError
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
