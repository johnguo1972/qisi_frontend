<template>
  <view class="growth">
    <StudentSidebar activeItem="growth" />
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">我的成长</text>
      </view>
      <!-- 统计卡片 -->
      <view class="stats-grid">
        <view class="stat-card">
          <text class="stat-value">{{ summary.accuracy }}%</text>
          <text class="stat-label">正确率</text>
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
      <!-- 学习反馈 -->
      <view class="feedback-panel">
        <view class="panel-header">
          <text class="panel-title">学习反馈</text>
        </view>
        <view class="feedback-card">
          <text class="feedback-text">
            累计完成 {{ summary.total_attempts }} 次作答，正确率 {{ summary.accuracy }}%，
            已掌握 {{ summary.mastered_count }} 个知识点。
            错题本中有 {{ summary.wrong_book_count }} 道待攻克。
          </text>
          <view class="progress-visual">
            <view class="progress-ring">
              <view class="progress-fill" :style="{ '--percent': summary.accuracy + '%' }"></view>
              <text class="ring-text">{{ summary.accuracy }}%</text>
            </view>
            <text class="visual-label">综合正确率</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'
import StudentSidebar from '@/components/StudentSidebar.vue'

const summary = ref({
  total_attempts: 0,
  total_correct: 0,
  accuracy: 0,
  mastered_count: 0,
  wrong_book_count: 0,
})

onMounted(async () => {
  try {
    const res = await studentApi.growth()
    if (res.data) summary.value = res.data
  } catch (e) {
    console.error('Failed to load growth:', e)
  }
})
</script>

<style scoped>
.growth {
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
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20rpx;
  margin-bottom: 30rpx;
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
.feedback-panel {
  background: #fff;
  border-radius: 12rpx;
  padding: 30rpx;
}
.panel-header {
  margin-bottom: 24rpx;
}
.panel-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.feedback-card {
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 30rpx;
}
.feedback-text {
  font-size: 26rpx;
  color: #333;
  line-height: 1.8;
  display: block;
  margin-bottom: 30rpx;
}
.progress-visual {
  text-align: center;
}
.progress-ring {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: conic-gradient(#409eff var(--percent, 0%), #eee var(--percent, 0%));
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16rpx;
}
.progress-fill {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ring-text {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.visual-label {
  font-size: 22rpx;
  color: #999;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .growth {
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
