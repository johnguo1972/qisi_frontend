<template>
  <view class="workbench">
    <TeacherSidebar activeItem="missions" />
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">任务列表</text>
        <button class="create-btn" @click="goCreate">+ 创建任务</button>
      </view>
      <view v-if="missions.length === 0" class="empty">
        <text>还没有任务，点击"创建任务"开始</text>
      </view>
      <view class="mission-grid">
        <view v-for="m in missions" :key="m.id" class="mission-card"
              @click="goMissionDetail(m.id)">
          <view class="card-header">
            <text class="mission-name">{{ m.mission_name }}</text>
            <text class="mission-status">{{ statusText(m.status) }}</text>
          </view>
          <text class="mission-levels">{{ m.level_count || 0 }} 个关卡</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { missionApi, type Mission } from '@/api/missions.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

const missions = ref<Mission[]>([])

onMounted(async () => {
  try {
    const res = await missionApi.list()
    missions.value = res.data || []
  } catch (e) {
    console.error('Failed to load missions:', e)
  }
})

function statusText(status: string): string {
  const map: Record<string, string> = { draft: '草稿', published: '已发布', running: '进行中', closed: '已关闭', archived: '已归档' }
  return map[status] || status
}

function goMissionDetail(id: number) { uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${id}` }) }
function goCreate() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }
</script>

<style scoped>
.workbench {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10rpx 0 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.create-btn {
  padding: 12rpx 32rpx;
  background: #4caf50;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}
.mission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20rpx;
}
.mission-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.mission-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.mission-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.mission-status {
  font-size: 22rpx;
  color: #409eff;
}
.mission-levels {
  font-size: 22rpx;
  color: #999;
}
.empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}
</style>
