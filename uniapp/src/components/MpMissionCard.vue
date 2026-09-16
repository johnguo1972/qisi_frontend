<template>
  <view class="card" @click="$emit('click', missionId)">
    <text v-if="classLabel" class="badge">{{ classLabel }}</text>
    <view class="head">
      <text class="name">{{ missionName }}</text>
      <text :class="`status-${status}`">{{ statusLabel(status, '未开始') }}</text>
    </view>
    <view class="meta">
      <text v-if="assignmentMode === 'flat'">📋 作业题目　{{ questionCount }} 题目</text>
      <text v-else>📋 {{ levelCount }} 关卡　{{ questionCount }} 题目</text>
    </view>
    <text v-if="endAt" class="deadline">截止：{{ formatDateOnly(endAt) }}</text>
    <view class="progress">
      <view class="fill" :style="{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }" />
      <text>{{ progressPercent }}%</text>
    </view>
    <view v-if="pdfDownloadUrl || (isClassroomPractice && feedbackAvailable)" class="card-actions">
      <button v-if="pdfDownloadUrl" :class="['action-button', 'pdf-button', { 'single-action': !(isClassroomPractice && feedbackAvailable) }]" @click.stop="downloadPdf">下载PDF作业</button>
      <button v-if="isClassroomPractice && feedbackAvailable" class="action-button feedback-button" @click.stop="$emit('feedback', missionId)">查看错题反馈</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { formatDateOnly, statusLabel } from '@/utils/display-format'
import { getPublicMediaUrl } from '@/utils/media-url'

const props = defineProps<{
  missionId: string
  missionName: string
  classLabel?: string
  status: string
  levelCount: number
  questionCount: number
  assignmentMode?: 'flat' | 'levels'
  endAt?: string
  progressPercent: number
  pdfDownloadUrl?: string
  isClassroomPractice?: boolean
  feedbackAvailable?: boolean
  feedbackStatus?: string | null
}>()

defineEmits<{ click: [id: string]; feedback: [id: string] }>()

function downloadPdf() {
  const url = getPublicMediaUrl(props.pdfDownloadUrl)
  if (!url) {
    uni.showToast({ title: 'PDF尚未生成', icon: 'none' })
    return
  }
  if (typeof window !== 'undefined' && window.open) {
    window.open(url, '_blank')
    return
  }
  uni.downloadFile({
    url,
    success: (result) => {
      if (result.statusCode !== 200) {
        uni.showToast({ title: 'PDF下载失败', icon: 'none' })
        return
      }
      uni.openDocument({ filePath: result.tempFilePath, fileType: 'pdf', showMenu: true })
    },
    fail: () => uni.showToast({ title: 'PDF下载失败', icon: 'none' }),
  })
}
</script>

<style scoped>
.card { position: relative; margin-bottom: 22rpx; padding: 28rpx; border-radius: 18rpx; background: #fff; box-shadow: 0 2rpx 12rpx #0000000d; }
.badge { position: absolute; top: 0; left: 0; padding: 6rpx 18rpx; border-radius: 18rpx 0 18rpx 0; color: #fff; background: #409eff; font-size: 20rpx; }
.head { display: flex; justify-content: space-between; gap: 20rpx; margin-bottom: 18rpx; }
.name { font-size: 30rpx; font-weight: 600; }
.status-not_started, .status-locked { color: #999; }
.status-in_progress, .status-running { color: #409eff; }
.status-completed, .status-passed { color: #67c23a; }
.meta, .deadline { display: block; margin-bottom: 14rpx; color: #888; font-size: 24rpx; }
.progress { display: flex; align-items: center; gap: 14rpx; color: #666; font-size: 22rpx; }
.progress > view { height: 12rpx; flex: 1; border-radius: 8rpx; background: #eee; }
.fill { height: 100%; border-radius: 8rpx; background: linear-gradient(90deg, #409eff, #6366f1); }
.card-actions { display: flex; gap: 12rpx; margin-top: 18rpx; width: 100%; box-sizing: border-box; }
.action-button { flex: 0 0 calc(50% - 6rpx); width: calc(50% - 6rpx); margin: 0; padding: 0 10rpx; height: 58rpx; line-height: 58rpx; box-sizing: border-box; border-radius: 10rpx; font-size: 23rpx; }
.pdf-button { color: #409eff; background: #ecf5ff; border: 1rpx solid #b3d8ff; }
.single-action { flex-basis: 100%; width: 100%; }
.feedback-button { color: #fff; background: #409eff; border: 1rpx solid #409eff; }
.pdf-button::after { border: none; }
.feedback-button::after { border: none; }
</style>
