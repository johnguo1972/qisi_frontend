<template>
  <view class="knowledge-graph">
    <StudentSidebar activeItem="knowledge" />
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">知识图谱</text>
      </view>
      <view class="placeholder-card">
        <text class="placeholder-icon">📊</text>
        <text class="placeholder-title">功能开发中</text>
        <text class="placeholder-sub">即将上线，敬请期待...</text>
      </view>
      <!-- 统计卡片 -->
      <view v-if="summary" class="stats-grid">
        <view class="panel-header">
          <text class="panel-title">我的知识概览</text>
        </view>
        <view class="stat-card">
          <text class="stat-value">{{ summary.accuracy }}%</text>
          <text class="stat-label">综合正确率</text>
        </view>
        <view class="stat-card">
          <text class="stat-value">{{ summary.total_correct }}</text>
          <text class="stat-label">做对题数</text>
        </view>
        <view class="stat-card">
          <text class="stat-value">{{ summary.mastered_count }}</text>
          <text class="stat-label">已掌握知识点</text>
        </view>
        <view class="stat-card">
          <text class="stat-value">{{ summary.total_attempts }}</text>
          <text class="stat-label">总作答次数</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'
import StudentSidebar from '@/components/StudentSidebar.vue'

const summary = ref<{
  accuracy: number
  total_correct: number
  mastered_count: number
  total_attempts: number
} | null>(null)

onMounted(async () => {
  try {
    const res = await studentApi.growth()
    if (res.data) {
      summary.value = res.data
    }
  } catch (e) {
    console.error('Failed to load growth data:', e)
  }
})
</script>

<style scoped>
.knowledge-graph {
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
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.placeholder-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 12rpx;
  padding: 80rpx 40rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 30rpx;
}
.placeholder-icon {
  font-size: 120rpx;
  margin-bottom: 40rpx;
}
.placeholder-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 16rpx;
}
.placeholder-sub {
  font-size: 26rpx;
  color: #999;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20rpx;
}
.panel-header {
  grid-column: 1 / -1;
  margin-bottom: 8rpx;
}
.panel-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.stat-card {
  background: #fff;
  padding: 30rpx;
  border-radius: 12rpx;
  text-align: center;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.stat-value {
  font-size: 48rpx;
  font-weight: bold;
  color: #409eff;
  display: block;
}
.stat-label {
  font-size: 24rpx;
  color: #999;
  display: block;
  margin-top: 8rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .knowledge-graph {
    flex-direction: column;
  }
  .main {
    margin-left: 0;
    width: 100%;
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
