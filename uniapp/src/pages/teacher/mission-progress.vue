<template>
  <view class="progress-page">
    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="errorMessage" class="state error">{{ errorMessage }}</view>
    <template v-else>
      <view class="page-header">
        <!-- #ifndef MP-WEIXIN -->
        <button class="back-btn" @click="goBack">返回作业列表</button>
        <!-- #endif -->
        <text class="page-title">学生完成进度</text>
        <text class="mission-name">{{ missionName || '作业' }}</text>
      </view>

      <view class="summary-card">
        <view class="summary-item">
          <text class="summary-label">整体完成</text>
          <text class="summary-value">{{ summary.completed }}/{{ summary.total }}</text>
        </view>
        <view class="summary-item">
          <text class="summary-label">完成比例</text>
          <text class="summary-value">{{ summary.percent }}%</text>
        </view>
        <view class="summary-item">
          <text class="summary-label">未完成</text>
          <text class="summary-value unfinished">{{ summary.unfinished }}人</text>
        </view>
        <view class="summary-item">
          <text class="summary-label">待批阅</text>
          <text class="summary-value">{{ summary.submitted }}人</text>
        </view>
      </view>

      <view v-if="classOptions.length > 1" class="class-filter">
        <text class="filter-label">查看班级</text>
        <picker :range="classOptions" range-key="name" @change="onClassChange">
          <view class="class-picker">{{ selectedClassName }}</view>
        </picker>
      </view>

      <view class="student-card">
        <view class="section-title">
          <text>学生明细</text>
          <text class="student-count">共{{ displayStudents.length }}人</text>
        </view>
        <view class="filters">
          <input v-model="keyword" class="filter-input" placeholder="搜索学生姓名或手机号" />
          <picker :range="statusOptions" @change="onStatusChange"><view class="status-picker">{{ statusLabel }}</view></picker>
        </view>
        <scroll-view scroll-x class="table-scroll">
          <view class="student-table">
            <view class="table-row table-header">
              <text class="col student">学生</text>
              <text class="col status">状态</text>
              <text class="col percent">完成进度</text>
              <text class="col time">最后学习时间</text>
            </view>
            <view v-for="student in displayStudents" :key="student.student_id" class="table-row">
              <text class="col student">{{ student.student_name || student.mobile || '-' }}</text>
              <text class="col status" :class="statusClass(displayStatus(student))">
                {{ statusText(displayStatus(student)) }}
              </text>
              <text class="col percent">{{ progressText(student.progress_percent) }}</text>
              <text class="col time">{{ formatLastAction(student.last_action_at) }}</text>
            </view>
            <view v-if="students.length === 0" class="empty">暂无被布置学生</view>
          </view>
        </scroll-view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/missions'
import { formatDateOnly } from '@/utils/display-format'

interface StudentProgress {
  student_id: string
  student_name?: string
  mobile?: string
  progress_status: string
  status?: string
  progress_percent: number
  last_action_at?: string | null
  answered_count?: number
  correct_count?: number
  accuracy?: number
  overdue?: boolean
}

interface ProgressSummary {
  completed: number
  total: number
  unfinished: number
  percent: number
  submitted: number
}

const missionId = ref('')
const missionName = ref('')
const loading = ref(true)
const errorMessage = ref('')
const students = ref<StudentProgress[]>([])
const classOptions = ref<Array<{ id: string; name: string }>>([{ id: '', name: '全部班级' }])
const selectedClassId = ref('')
const summary = ref<ProgressSummary>({ completed: 0, total: 0, unfinished: 0, percent: 0, submitted: 0 })
const keyword = ref('')
const status = ref('')
const statusOptions = ['全部状态', '未开始', '进行中', '已提交', '已批改', '已逾期']
const statusValues = ['', 'not_started', 'in_progress', 'submitted', 'graded', 'overdue']
const statusLabel = computed(() => statusOptions[statusValues.indexOf(status.value)] || '全部状态')
const displayStudents = computed(() => students.value.filter(student => {
  const value = student.status || student.progress_status
  const text = `${student.student_name || ''}${student.mobile || ''}`.toLowerCase()
  const matchesKeyword = !keyword.value.trim() || text.includes(keyword.value.trim().toLowerCase())
  return matchesKeyword && (!status.value || value === status.value || (status.value === 'overdue' && (student as any).overdue))
}))
const selectedClassName = computed(() => classOptions.value.find(item => item.id === selectedClassId.value)?.name || '全部班级')

onLoad((options: any) => {
  missionId.value = String(options?.id || '')
})

onMounted(() => {
  if (!missionId.value) {
    errorMessage.value = '缺少作业ID'
    loading.value = false
    return
  }
  loadProgress()
})

async function loadProgress() {
  loading.value = true
  errorMessage.value = ''
  try {
    if (classOptions.value.length === 1) {
      const detail: any = await missionApi.detail(missionId.value)
      const data = detail?.data || {}
      const ids = (data.class_ids || (data.class_obj ? [data.class_obj] : [])).map((id: any) => String(id))
      const names = data.class_names || []
      classOptions.value = [{ id: '', name: '全部班级' }, ...ids.map((id: string, index: number) => ({ id, name: names[index] || id }))]
    }
    const response: any = await missionApi.progress(missionId.value, selectedClassId.value ? { class_id: selectedClassId.value } : undefined)
    const data = response?.data || {}
    missionName.value = data.mission_name || ''
    summary.value = {
      completed: Number(data.summary?.completed || data.summary?.graded || 0),
      total: Number(data.summary?.total || 0),
      unfinished: Number(data.summary?.unfinished || 0),
      percent: Number(data.summary?.percent || data.summary?.completion_rate || 0),
      submitted: Number(data.summary?.submitted || 0),
    }
    students.value = Array.isArray(data.students) ? data.students : []
  } catch (error) {
    console.error('加载学生完成进度失败:', error)
    errorMessage.value = '加载学生完成进度失败'
  } finally {
    loading.value = false
  }
}

function onClassChange(event: any) {
  const index = Number(event?.detail?.value || 0)
  selectedClassId.value = classOptions.value[index]?.id || ''
  loadProgress()
}

function onStatusChange(event: any) {
  status.value = statusValues[Number(event?.detail?.value || 0)] || ''
}

function progressText(value: number): string {
  return `${Number(value || 0)}%`
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    not_started: '未开始',
    in_progress: '进行中',
    submitted: '已提交',
    graded: '已批改',
    completed: '已批改',
    passed: '已批改',
  }
  if (status === 'overdue') return '已逾期'
  return map[status] || status || '未开始'
}

function displayStatus(student: StudentProgress): string {
  return student.overdue && !['submitted', 'graded', 'completed', 'passed'].includes(student.progress_status)
    ? 'overdue'
    : (student.progress_status || 'not_started')
}

function statusClass(status: string): string {
  return `status-${status || 'not_started'}`
}

function formatLastAction(value?: string | null): string {
  return value ? formatDateOnly(value, '-') : '未开始'
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.redirectTo({ url: '/pages/teacher/layout?section=assignment-list' })
}
</script>

<style scoped>
.progress-page {
  min-height: 100vh;
  padding: 30rpx 40rpx;
  background: #f0f2f5;
  box-sizing: border-box;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 24rpx;
}
.back-btn { margin: 0; padding: 8px 16px; color: #606266; background: #fff; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 13px; }
.back-btn::after { border: none; }
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.mission-name {
  color: #666;
  font-size: 28rpx;
}
.summary-card,
.student-card {
  background: #fff;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.summary-card {
  display: flex;
  margin-bottom: 20rpx;
  padding: 24rpx;
}
.summary-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  text-align: center;
  border-right: 1rpx solid #eee;
}
.summary-item:last-child { border-right: none; }
.summary-label { color: #909399; font-size: 24rpx; }
.summary-value { color: #303133; font-size: 34rpx; font-weight: bold; }
.summary-value.unfinished { color: #e6a23c; }
.class-filter { display: flex; align-items: center; gap: 16rpx; margin-bottom: 20rpx; padding: 18rpx 24rpx; background: #fff; border-radius: 12rpx; }
.filter-label { color: #606266; font-size: 26rpx; }
.class-picker { min-width: 260rpx; height: 58rpx; padding: 0 18rpx; border: 1rpx solid #dcdfe6; border-radius: 6rpx; color: #303133; font-size: 26rpx; line-height: 58rpx; }
.student-card { padding: 24rpx; }
.filters { display: flex; gap: 16rpx; margin-bottom: 18rpx; }
.filter-input, .status-picker { height: 58rpx; padding: 0 16rpx; box-sizing: border-box; border: 1rpx solid #dcdfe6; border-radius: 6rpx; background: #fff; color: #606266; font-size: 24rpx; line-height: 58rpx; }
.filter-input { flex: 1; }
.status-picker { width: 180rpx; text-align: center; }
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
  color: #303133;
  font-size: 30rpx;
  font-weight: bold;
}
.student-count { color: #909399; font-size: 24rpx; font-weight: normal; }
.table-scroll { width: 100%; }
.student-table { min-width: 900rpx; }
.table-row {
  display: flex;
  align-items: center;
  min-height: 76rpx;
  border-bottom: 1rpx solid #ebeef5;
  color: #606266;
  font-size: 26rpx;
}
.table-header { min-height: 64rpx; background: #f5f7fa; color: #909399; font-size: 24rpx; }
.col { padding: 0 16rpx; box-sizing: border-box; }
.col.student { width: 260rpx; }
.col.status { width: 180rpx; }
.col.percent { width: 180rpx; }
.col.time { width: 280rpx; }
.status-not_started { color: #909399; }
.status-in_progress { color: #409eff; }
.status-completed,
.status-passed { color: #67c23a; }
.state,
.empty { padding: 100rpx 30rpx; text-align: center; color: #909399; }
.error { color: #f56c6c; }
</style>
