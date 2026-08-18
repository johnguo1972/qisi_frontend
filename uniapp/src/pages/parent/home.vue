<template>
  <ParentShell active-item="home">
  <view class="page">
    <view class="header">
      <view>
        <text class="title">家长端</text>
        <text class="subtitle">查看孩子的学习任务和完成进度</text>
      </view>
    </view>

    <MpChildSwitcher ref="childSwitcher" :visible="true" @changed="onChildChanged" />

    <view v-if="!selectedChild" class="state-card">
      <text class="state-title">暂无已绑定孩子</text>
      <text class="state-text">请先完成家长与学生的绑定，绑定后即可查看学习情况。</text>
      <button class="bind-button" @click="goBind">添加孩子</button>
    </view>
    <view v-else-if="loading" class="state-card">
      <text class="state-text">正在加载孩子的学习任务...</text>
    </view>
    <view v-else-if="errorMessage" class="state-card">
      <text class="state-title">暂时无法加载</text>
      <text class="state-text">{{ errorMessage }}</text>
    </view>
    <view v-else class="content">
      <text class="section-title">学习任务</text>
      <view v-if="!missions.length" class="state-card">
        <text class="state-text">暂无任务，等待老师发布吧</text>
      </view>
      <MpMissionCard
        v-for="mission in missions"
        :key="mission.mission?.id"
        :mission-id="String(mission.mission?.id)"
        :mission-name="mission.mission?.mission_name || mission.mission_name"
        :class-label="mission.class_label"
        :status="mission.progress_status || 'not_started'"
        :level-count="mission.level_count || 0"
        :question-count="mission.question_count || 0"
        :end-at="mission.mission?.deadline || mission.end_at"
        :progress-percent="mission.progress_percent || 0"
        @click="goMission"
      />
    </view>
  </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import ParentShell from '@/components/ParentShell.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import MpMissionCard from '@/components/MpMissionCard.vue'
import { parentApi } from '@/api/index'
import { ensurePageRole } from '@/utils/roles'

const selectedChild = ref<any>(null)
const missions = ref<any[]>([])
const loading = ref(false)
const errorMessage = ref('')
const childSwitcher = ref<any>(null)
const navigateParentSection = inject<(key: string) => void>('parentLayoutNavigate', undefined)

async function onChildChanged(child: any) {
  selectedChild.value = child
  await load()
}

async function load() {
  if (!selectedChild.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await parentApi.missions({ scope: 'all' })
    if (response?.detail) {
      missions.value = []
      errorMessage.value = response.detail
      return
    }
    if (response?.code !== undefined && response.code !== 0) {
      missions.value = []
      errorMessage.value = response.message || '学习任务加载失败'
      return
    }
    missions.value = (response?.data?.missions || []).map((item: any) => ({
      ...item,
      mission: {
        id: item.id,
        mission_name: item.mission_name,
        deadline: item.deadline,
      },
      class_label: item.class_name,
    }))
  } catch (error: any) {
    missions.value = []
    errorMessage.value = error?.message || '学习任务加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function goMission(id: string) {
  if (id && id !== 'undefined') uni.navigateTo({ url: `/pages/parent/mission?id=${id}` })
}

function goBind() {
  if (navigateParentSection) {
    navigateParentSection('children')
    return
  }
  uni.navigateTo({ url: '/pages/parent/bind' })
}

onShow(() => {
  if (!ensurePageRole('parent')) return
  childSwitcher.value?.load?.()
})
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 22rpx 60rpx; box-sizing: border-box; background: #f0f2f5; }
.header { display: flex; align-items: center; justify-content: space-between; padding: 18rpx 4rpx 8rpx; }
.title { display: block; color: #303133; font-size: 38rpx; font-weight: 700; }
.subtitle { display: block; margin-top: 8rpx; color: #909399; font-size: 23rpx; }
.content { margin-top: 24rpx; }
.section-title { display: block; margin: 0 4rpx 18rpx; color: #303133; font-size: 30rpx; font-weight: 600; }
.state-card { margin-top: 24rpx; padding: 70rpx 30rpx; border-radius: 18rpx; background: #fff; text-align: center; }
.state-title { display: block; color: #606266; font-size: 29rpx; font-weight: 600; }
.state-text { display: block; margin-top: 14rpx; color: #909399; font-size: 25rpx; line-height: 1.6; }
.bind-button { margin-top: 28rpx; width: 260rpx; color: #fff; background: #409eff; font-size: 25rpx; }
</style>
