<template>
  <view class="card" @click="$emit('click', missionId)">
    <text v-if="classLabel" class="badge">{{ classLabel }}</text>
    <view class="head">
      <text class="name">{{ missionName }}</text>
      <text :class="`status-${status}`">{{ statusLabel(status, '未开始') }}</text>
    </view>
    <view class="meta">📋 {{ levelCount }} 关卡　{{ questionCount }} 题目</view>
    <text v-if="endAt" class="deadline">截止：{{ formatDateTime(endAt) }}</text>
    <view class="progress">
      <view class="fill" :style="{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }" />
      <text>{{ progressPercent }}%</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { formatDateTime, statusLabel } from '@/utils/display-format'

defineProps<{
  missionId: string
  missionName: string
  classLabel?: string
  status: string
  levelCount: number
  questionCount: number
  endAt?: string
  progressPercent: number
}>()

defineEmits<{ click: [id: string] }>()
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
</style>
