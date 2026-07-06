<template>
  <view class="mission-page">
    <!-- 左侧任务信息 -->
    <view class="info-panel">
      <view class="page-header">
        <text class="page-title">关卡</text>
        <button class="export-btn" @click="goExport">导出习题</button>
      </view>
      <view class="mission-card">
        <text class="title">{{ missionName }}</text>
        <text class="goal">{{ goalText || '暂无描述' }}</text>
      </view>
    </view>
    <!-- 右侧关卡列表 -->
    <view class="levels-panel">
      <view class="panel-header">
        <text class="panel-title">关卡列表</text>
      </view>
      <view class="levels">
        <view v-for="lv in levels" :key="lv.id" class="level-card"
              @click="goLevel(lv.id)">
          <view class="level-left">
            <view class="level-badge">{{ lv.level_no }}</view>
            <text class="level-name">{{ lv.level_name }}</text>
          </view>
          <text class="level-status">{{ lv.status }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'

const missionId = ref(0)
const missionName = ref('')
const goalText = ref('')
const levels = ref<any[]>([])

onMounted(async () => {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  missionId.value = parseInt(page.options.id)

  try {
    const res = await studentApi.missionDetail(missionId.value)
    missionName.value = res.data?.mission_name || ''
    goalText.value = res.data?.goal_text || ''
    levels.value = res.data?.levels || []
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
})

function goLevel(id: number) {
  uni.navigateTo({ url: `/pages/student/answer?levelId=${id}` })
}

function goExport() {
  uni.navigateTo({ url: `/pages/student/export?type=mission&ids=${missionId.value}` })
}
</script>

<style scoped>
.mission-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.info-panel {
  width: 280px;
  padding: 30rpx 24rpx;
  background: #fff;
  border-right: 1rpx solid #e8e8e8;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.page-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.export-btn {
  padding: 0;
  margin: 0;
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
  border: none;
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
  line-height: 1.4;
}
.export-btn::after {
  border: none;
}
.mission-card {
  background: #f8f8f8;
  border-radius: 8rpx;
  padding: 20rpx;
}
.title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 12rpx;
}
.goal {
  color: #666;
  font-size: 24rpx;
  display: block;
  line-height: 1.6;
}
.levels-panel {
  flex: 1;
  padding: 30rpx 40rpx;
}
.panel-header {
  margin-bottom: 24rpx;
}
.panel-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.levels {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.level-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.2s;
}
.level-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.level-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.level-badge {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: bold;
}
.level-name {
  font-size: 28rpx;
  color: #333;
}
.level-status {
  color: #ff9800;
  font-size: 24rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .mission-page {
    flex-direction: column;
  }
  .info-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1rpx solid #e8e8e8;
  }
}
</style>
