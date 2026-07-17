<template>
  <view class="student-home">
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="panel-header">
        <text class="panel-title">我的任务</text>
      </view>

      <!-- 班级选择器 -->
      <ClassSelector
        :selected-class-id="selectedClassId"
        @select="onClassSelect"
      />

      <!-- 时间筛选栏 -->
      <TimeFilterBar
        :selected-scope="selectedScope"
        @change="onScopeChange"
      />

      <view v-if="sortedMissions.length === 0" class="empty">
        <text>暂无任务，等待老师发布吧</text>
      </view>
      <view class="mission-grid">
        <view v-for="m in sortedMissions" :key="m.mission.id" class="mission-card"
              @click="goMission(m.mission.id)">
          <!-- 班级标签角标 -->
          <view v-if="m.class_label" class="class-badge" :style="{ background: getClassBadgeColor(m.class_label) }">
            <text class="badge-text">{{ m.class_label }}</text>
          </view>
          <view class="card-top">
            <text class="mission-name">{{ m.mission.mission_name }}</text>
            <text class="mission-status" :class="'status-' + m.progress_status">{{ statusText(m.progress_status) }}</text>
          </view>
          <!-- 关卡数和题目数 -->
          <view class="mission-meta">
            <text class="meta-item">
              <text class="meta-icon">📋</text>
              <text>{{ m.level_count || 0 }} 关卡</text>
            </text>
            <text class="meta-item">
              <text class="meta-icon"></text>
              <text>{{ m.question_count || 0 }} 题目</text>
            </text>
          </view>
          <view v-if="m.mission.deadline" class="deadline-row">
            <text class="deadline-text">截止：{{ formatDeadline(m.mission.deadline) }}</text>
          </view>
          <view class="progress-section">
            <view class="progress-bar">
              <view class="progress-fill" :style="{ width: m.progress_percent + '%' }"></view>
            </view>
            <text class="progress-text">{{ m.progress_percent }}%</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'
import ClassSelector from '@/components/ClassSelector.vue'
import TimeFilterBar from '@/components/TimeFilterBar.vue'

const missions = ref<any[]>([])

// 班级选择器状态
const selectedClassId = ref(0)

// 时间筛选状态
const selectedScope = ref('all')

// 按 deadline 升序排序后的任务
const sortedMissions = computed(() => {
  return [...missions.value].sort((a, b) => {
    const aDeadline = a.mission?.deadline || '9999-12-31'
    const bDeadline = b.mission?.deadline || '9999-12-31'
    return aDeadline.localeCompare(bDeadline)
  })
})

// 加载任务数据
async function loadMissions() {
  try {
    const res = await studentApi.home({
      class_id: selectedClassId.value,
      scope: selectedScope.value
    })
    missions.value = res.data?.missions || []
  } catch (e) {
    console.error('Failed to load missions:', e)
  }
}

// 班级选择事件
function onClassSelect(classId: number) {
  selectedClassId.value = classId
  loadMissions()
}

// 时间范围切换事件
function onScopeChange(scope: string) {
  selectedScope.value = scope
  loadMissions()
}

onMounted(async () => {
  await loadMissions()
})

function goMission(id: number) {
  uni.navigateTo({ url: `/pages/student/mission?id=${id}` })
}

// 班级角标颜色
function getClassBadgeColor(classLabel: string): string {
  const colors: Record<string, string> = {
    '一班': '#409eff',
    '二班': '#67c23a',
    '三班': '#e6a23c',
    '四班': '#f56c6c',
    '五班': '#909399',
  }
  return colors[classLabel] || '#6366f1'
}

// 格式化截止日期
function formatDeadline(deadline: string): string {
  if (!deadline) return ''
  try {
    const d = new Date(deadline)
    const month = d.getMonth() + 1
    const day = d.getDate()
    return `${month}月${day}日`
  } catch {
    return deadline
  }
}

// 任务状态中文映射
function statusText(status: string): string {
  const map: Record<string, string> = {
    'not_started': '未开始',
    'in_progress': '进行中',
    'completed': '已完成',
  }
  return map[status] || status
}
</script>

<style scoped>
.student-home {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 30rpx 40rpx;
}
.panel-header {
  margin-bottom: 24rpx;
}
.panel-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.mission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20rpx;
}
.mission-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: box-shadow 0.2s;
  position: relative;
  overflow: visible;
}
.mission-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.class-badge {
  position: absolute;
  top: -6rpx;
  left: -6rpx;
  padding: 4rpx 12rpx;
  border-radius: 8rpx 0 8rpx 0;
  z-index: 1;
}
.badge-text {
  font-size: 20rpx;
  color: #fff;
  font-weight: 500;
}
.card-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16rpx;
}
.mission-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.mission-status {
  font-size: 22rpx;
  color: #ff9800;
}
.status-not_started {
  color: #999;
}
.status-in_progress {
  color: #409eff;
}
.status-completed {
  color: #67c23a;
}
/* 关卡数和题目数 */
.mission-meta {
  display: flex;
  gap: 24rpx;
  margin-bottom: 12rpx;
}
.meta-item {
  font-size: 22rpx;
  color: #888;
  display: flex;
  align-items: center;
  gap: 4rpx;
}
.meta-icon {
  font-size: 24rpx;
}
.deadline-row {
  margin-bottom: 12rpx;
}
.deadline-text {
  font-size: 22rpx;
  color: #999;
}
.progress-section {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.progress-bar {
  flex: 1;
  height: 12rpx;
  background: #eee;
  border-radius: 6rpx;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #6366f1);
  border-radius: 6rpx;
}
.progress-text {
  font-size: 22rpx;
  color: #666;
  min-width: 50rpx;
  text-align: right;
}
.empty {
  text-align: center;
  padding: 100rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .student-home {
    flex-direction: column;
  }
  .main {
    margin-left: 0;
    width: 100%;
  }
  .mission-grid {
    grid-template-columns: 1fr;
  }
}
</style>
