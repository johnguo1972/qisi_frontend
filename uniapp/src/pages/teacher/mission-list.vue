<template>
  <view class="container">
    <view class="page-header">
      <text class="page-title">任务列表</text>
      <button class="btn-create" @click="goCreateMission">+ 创建任务</button>
    </view>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="missions.length === 0" class="empty">
      <text>暂无任务，点击"创建任务"开始</text>
    </view>
    <view v-else class="mission-list">
      <view v-for="m in missions" :key="m.id" class="mission-card" @click="goMissionDetail(m.id)">
        <view class="card-header">
          <text class="mission-name">{{ m.mission_name }}</text>
          <text :class="['status-badge', m.status]">{{ statusText(m.status) }}</text>
        </view>
        <view class="card-body">
          <text class="mission-no">编号: {{ m.mission_no }}</text>
          <text v-if="m.goal_text" class="mission-goal">{{ m.goal_text }}</text>
          <text v-if="m.level_count" class="mission-levels">关卡数: {{ m.level_count }}</text>
        </view>
        <view v-if="m.end_at" class="card-footer">
          <text class="mission-end">截止: {{ m.end_at }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { missionApi, type Mission } from '@/api/missions'

const missions = ref<Mission[]>([])
const loading = ref(false)

onMounted(() => {
  loadMissions()
})

async function loadMissions() {
  loading.value = true
  try {
    const res: any = await missionApi.list()
    missions.value = (res.data || []) as Mission[]
  } catch (e) {
    console.error('加载任务列表失败:', e)
    uni.showToast({ title: '加载任务列表失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    published: '已发布',
    closed: '已结束',
  }
  return map[status] || status
}

function goCreateMission() {
  uni.navigateTo({ url: '/pages/teacher/mission-create' })
}

function goMissionDetail(id: number) {
  uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${id}` })
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #f5f7fa;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 500;
  color: #303133;
}
.btn-create {
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
}
.loading, .empty {
  text-align: center;
  color: #909399;
  padding: 60px 0;
  font-size: 14px;
}
.mission-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.mission-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.mission-card:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.mission-name {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}
.status-badge {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}
.status-badge.draft { background: #f0f0f0; color: #909399; }
.status-badge.published { background: #ecf5ff; color: #409eff; }
.status-badge.closed { background: #fff0f0; color: #f56c6c; }
.card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.mission-no {
  font-size: 13px;
  color: #909399;
}
.mission-goal {
  font-size: 13px;
  color: #606266;
}
.mission-levels {
  font-size: 13px;
  color: #409eff;
}
.card-footer {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}
.mission-end {
  font-size: 12px;
  color: #e6a23c;
}
</style>