<template>
  <ParentShell active-item="home">
  <view class="page">
    <view class="header">
      <text class="title">作业详情</text>
    </view>
    <MpChildSwitcher :visible="true" @changed="onChildChanged" />

    <view v-if="!selectedChild" class="state-card">请先绑定并选择孩子</view>
    <view v-else-if="loading" class="state-card">正在加载作业详情...</view>
    <view v-else-if="errorMessage" class="state-card error">{{ errorMessage }}</view>
    <view v-else-if="!mission" class="state-card">暂无作业详情</view>
    <template v-else>
      <view class="mission-card">
        <text class="mission-name">{{ mission.mission_name }}</text>
        <text class="mission-meta">{{ mission.class_name || '未设置班级' }}</text>
        <text class="mission-meta">截止：{{ formatDateOnly(mission.deadline) }}</text>
        <view class="overall">
          <text>整体进度 {{ mission.progress_percent || 0 }}%</text>
          <view class="progress"><view class="bar" :style="{ width: `${mission.progress_percent || 0}%` }"></view></view>
        </view>
      </view>

      <view class="levels">
        <view class="section-title">{{ mission.assignment_mode === 'flat' ? '作业进度' : '关卡进度' }}</view>
        <view v-if="!mission.levels?.length" class="empty">暂无关卡数据</view>
        <view v-for="level in mission.levels" :key="level.id" class="level">
          <view class="level-head"><text class="level-name">{{ mission.assignment_mode === 'flat' ? '作业题目' : `第${level.level_no}关 · ${level.level_name}` }}</text><text class="level-status">{{ statusLabel(level.status) }}</text></view>
          <text class="level-meta">{{ level.completed_count || 0 }}/{{ level.question_count || 0 }} 题 · 正确率 {{ level.accuracy || 0 }}%</text>
          <view class="progress"><view class="bar" :style="{ width: `${level.progress_percent || 0}%` }"></view></view>
        </view>
      </view>
    </template>
  </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { parentApi } from '@/api/index'
import ParentShell from '@/components/ParentShell.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import { ensurePageRole } from '@/utils/roles'
import { formatDateOnly, statusLabel } from '@/utils/display-format'

const missionId = ref('')
const selectedChild = ref<any>(null)
const mission = ref<any>(null)
const loading = ref(false)
const errorMessage = ref('')

onLoad((options: any) => {
  if (!ensurePageRole('parent')) return
  missionId.value = String(options?.id || '')
})

async function onChildChanged(child: any) {
  selectedChild.value = child
  await loadMission()
}

async function loadMission() {
  if (!selectedChild.value || !missionId.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await parentApi.missionDetail(missionId.value)
    if (response?.code !== 0) throw new Error(response?.detail || response?.message || '作业详情加载失败')
    mission.value = response.data?.mission || null
  } catch (error: any) {
    mission.value = null
    errorMessage.value = error?.message || '作业详情加载失败，请稍后重试'
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
.mission-card, .levels { margin-top: 24rpx; padding: 28rpx; border-radius: 18rpx; background: #fff; }
.mission-name { display: block; color: #303133; font-size: 32rpx; font-weight: 700; }
.mission-meta, .level-meta { display: block; margin-top: 10rpx; color: #909399; font-size: 23rpx; }
.overall { margin-top: 24rpx; color: #606266; font-size: 24rpx; }
.progress { height: 12rpx; margin-top: 12rpx; overflow: hidden; border-radius: 8rpx; background: #f0f2f5; }
.bar { height: 100%; border-radius: 8rpx; background: linear-gradient(90deg, #409eff, #67c23a); }
.section-title { color: #303133; font-size: 29rpx; font-weight: 600; }
.level { padding: 22rpx 0; border-top: 1rpx solid #f0f0f0; }
.level-head { display: flex; justify-content: space-between; gap: 12rpx; }
.level-name { color: #303133; font-size: 26rpx; }
.level-status { color: #409eff; font-size: 22rpx; }
.empty { padding: 44rpx 0; color: #909399; text-align: center; font-size: 24rpx; }
</style>
