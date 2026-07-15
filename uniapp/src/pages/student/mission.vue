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
        <!-- 班级和截止日期 -->
        <view class="mission-meta">
          <view class="meta-item" v-if="className">
            <text class="meta-icon">🏫</text>
            <text class="meta-text">{{ className }}</text>
          </view>
          <view class="meta-item" v-if="deadline">
            <text class="meta-icon">📅</text>
            <text class="meta-text">截止：{{ deadlineText }}</text>
          </view>
        </view>
        <!-- 整体进度 -->
        <view class="overall-progress" v-if="overallProgressPercent > 0">
          <view class="progress-label">
            <text>总体进度</text>
            <text>{{ overallProgressPercent }}%</text>
          </view>
          <view class="progress-bar">
            <view class="progress-fill" :style="{ width: overallProgressPercent + '%' }"></view>
          </view>
        </view>
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
            <view class="level-info">
              <text class="level-name">{{ lv.level_name }}</text>
              <text class="level-detail">{{ lv.question_count || 0 }} 题目</text>
            </view>
          </view>
          <view class="level-right">
            <!-- 关卡进度 -->
            <view class="level-progress">
              <view class="progress-bar-small">
                <view class="progress-fill-small" :style="{ width: lv.progress_percent + '%' }"></view>
              </view>
              <text class="progress-text">{{ lv.progress_percent }}%</text>
            </view>
            <text class="level-status" :class="'status-' + lv.status">{{ statusText(lv.status) }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { studentApi } from '@/api/student.ts'

const missionId = ref(0)
const missionName = ref('')
const goalText = ref('')
const className = ref('')
const deadline = ref('')
const levels = ref<any[]>([])

const deadlineText = computed(() => {
  if (!deadline.value) return ''
  try {
    const d = new Date(deadline.value)
    const month = d.getMonth() + 1
    const day = d.getDate()
    return `${month}月${day}日`
  } catch {
    return deadline.value
  }
})

// 计算总体进度（所有关卡进度的平均值）
const overallProgressPercent = computed(() => {
  if (levels.value.length === 0) return 0
  const total = levels.value.reduce((sum, lv) => sum + (lv.progress_percent || 0), 0)
  return Math.round(total / levels.value.length)
})

function statusText(status: string): string {
  const map: Record<string, string> = {
    locked: '未开始',
    running: '进行中',
    completed: '已完成',
    passed: '已通过',
  }
  return map[status] || status
}

onLoad((options: any) => {
  missionId.value = parseInt(options?.id)
})

onMounted(async () => {
  try {
    const res = await studentApi.missionDetail(missionId.value)
    missionName.value = res.data?.mission_name || ''
    goalText.value = res.data?.goal_text || ''
    className.value = res.data?.class_name || ''
    deadline.value = res.data?.deadline || ''
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
  margin-bottom: 16rpx;
}
/* 班级和截止日期 */
.mission-meta {
  display: flex;
  gap: 24rpx;
  flex-wrap: wrap;
  margin-bottom: 16rpx;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6rpx;
  font-size: 22rpx;
  color: #888;
}
.meta-icon {
  font-size: 24rpx;
}
.meta-text {
  color: #555;
}
/* 总体进度 */
.overall-progress {
  margin-top: 8rpx;
}
.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 22rpx;
  color: #666;
  margin-bottom: 6rpx;
}
.progress-bar {
  height: 10rpx;
  background: #eee;
  border-radius: 5rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 5rpx;
  transition: width 0.3s;
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
.level-info {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
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
.level-detail {
  font-size: 22rpx;
  color: #999;
}
.level-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8rpx;
}
/* 关卡进度 */
.level-progress {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.progress-bar-small {
  width: 100rpx;
  height: 8rpx;
  background: #eee;
  border-radius: 4rpx;
  overflow: hidden;
}
.progress-fill-small {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 4rpx;
  transition: width 0.3s;
}
.progress-text {
  font-size: 20rpx;
  color: #999;
  min-width: 40rpx;
  text-align: right;
}
.level-status {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 4rpx;
}
.status-locked {
  color: #999;
  background: #f0f0f0;
}
.status-running {
  color: #409eff;
  background: #ecf5ff;
}
.status-completed, .status-passed {
  color: #67c23a;
  background: #e8f5e9;
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
