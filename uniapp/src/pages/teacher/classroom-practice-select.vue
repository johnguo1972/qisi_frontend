<template>
  <view class="page">
    <view class="header"><text class="title">选择课堂练习</text></view>
    <view v-if="loading" class="empty">正在加载...</view>
    <view v-else-if="!missions.length" class="empty">暂无已发布的课堂练习</view>
    <view v-else class="list">
      <view v-for="mission in missions" :key="mission.mission_id" class="card">
        <view class="name">{{ mission.mission_name }}</view>
        <view class="meta">{{ mission.node_count }} 个节点 · {{ mission.question_count }} 道题</view>
        <view class="classes">
          <button size="mini" @click="openMission(mission)">{{ feedbackMode ? '查看课堂反馈' : '查看错题统计' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { courseApi } from '@/api/courses'

const missions = ref<any[]>([])
const loading = ref(false)
const feedbackMode = ref(false)

onLoad(async (options: any) => {
  const courseId = String(options?.course_id || '')
  feedbackMode.value = options?.mode === 'feedback'
  if (!courseId) return
  loading.value = true
  try {
    const response: any = await courseApi.classroomPracticeMissions(courseId as any)
    missions.value = response?.data?.missions || response?.data?.data?.missions || []
  } catch (error) {
    console.error('加载课堂练习失败:', error)
    uni.showToast({ title: '加载课堂练习失败', icon: 'none' })
  } finally {
    loading.value = false
  }
})

function openMission(mission: any) {
  const ids = (mission.class_ids || []).map(String)
  const suffix = ids.length === 1 ? `&class_id=${ids[0]}` : ''
  const page = feedbackMode.value ? 'classroom-feedback' : 'classroom-wrongbook-statistics'
  uni.navigateTo({ url: `/pages/teacher/${page}?mission_id=${mission.mission_id}${suffix}` })
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f5f7fa; box-sizing: border-box; }
.header { margin-bottom: 24rpx; }
.title { font-size: 36rpx; font-weight: 600; color: #303133; }
.empty { padding: 120rpx 0; color: #909399; text-align: center; }
.list { display: flex; flex-direction: column; gap: 20rpx; }
.card { padding: 24rpx; background: #fff; border-radius: 12rpx; }
.name { font-size: 30rpx; color: #303133; font-weight: 600; }
.meta { margin: 12rpx 0 20rpx; color: #909399; font-size: 24rpx; }
.classes { display: flex; flex-wrap: wrap; gap: 16rpx; }
.classes button { margin: 0; color: #409eff; background: #ecf5ff; }
</style>
