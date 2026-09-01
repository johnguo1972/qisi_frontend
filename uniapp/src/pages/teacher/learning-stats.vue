<template>
  <view class="stats-page">
    <view class="page-header">
      <text class="page-title">学情统计</text>
      <view v-if="classes.length" class="class-filter">
        <text class="filter-label">班级</text>
        <picker :range="classes" range-key="class_name" :value="selectedClassIndex" @change="handleClassChange">
          <view class="picker-control">
            <text>{{ selectedClassName || '请选择班级' }}</text>
            <text class="picker-arrow">⌄</text>
          </view>
        </picker>
      </view>
    </view>

    <view v-if="loadingClasses" class="empty-card">加载班级中...</view>
    <view v-else-if="!classes.length" class="empty-card">暂无可查看的班级</view>
    <view v-else-if="loading" class="empty-card">加载中...</view>
    <template v-else>
      <view class="overview-card">
        <view class="overview-title">
          <text>{{ stats.class_name || selectedClassName || '班级' }}</text>
          <text class="overview-subtitle">作业按创建时间倒序排列</text>
        </view>
        <view class="summary-grid">
          <view class="summary-item"><text class="summary-label">学生人数</text><text class="summary-value">{{ summary.student_count }}</text></view>
          <view class="summary-item"><text class="summary-label">作业数量</text><text class="summary-value">{{ summary.mission_count }}</text></view>
          <view class="summary-item"><text class="summary-label">作业完成率</text><text class="summary-value primary">{{ summary.completion_rate }}%</text></view>
          <view class="summary-item"><text class="summary-label">总答题数</text><text class="summary-value">{{ summary.answer_count }}</text></view>
          <view class="summary-item"><text class="summary-label">总体正确率</text><text class="summary-value success">{{ summary.accuracy }}%</text></view>
          <view class="summary-item"><text class="summary-label">待批改</text><text class="summary-value warning">{{ summary.pending_count }}</text></view>
        </view>
      </view>

      <view v-if="missions.length === 0" class="empty-card">该班级暂无作业数据</view>
      <view v-for="mission in missions" :key="mission.mission_id" class="mission-card">
        <view class="mission-header">
          <view class="mission-title-area">
            <text class="mission-title">{{ mission.mission_name || '未命名作业' }}</text>
            <text class="mission-no">{{ mission.mission_no || mission.mission_id }}</text>
          </view>
          <view class="mission-header-right">
            <text class="mission-status" :class="missionStatusClass(mission.status)">{{ missionStatusText(mission.status) }}</text>
            <button class="detail-button" size="mini" @click="goMission(mission.mission_id)">查看作业详情</button>
          </view>
        </view>

        <view class="mission-meta">
          <text>创建时间：{{ formatMissionDate(mission.created_at) }}</text>
          <text>截止时间：{{ formatMissionDate(mission.end_at) }}</text>
          <text>题目：{{ mission.question_count || 0 }}题</text>
          <text>学生：{{ mission.student_count || 0 }}人</text>
        </view>

        <view class="mission-metrics">
          <view class="mission-metric">
            <text class="metric-label">作业完成</text>
            <text class="metric-value">{{ mission.completed_count || 0 }}/{{ mission.student_count || 0 }}</text>
            <text class="metric-rate primary">{{ numberValue(mission.completion_rate) }}%</text>
          </view>
          <view class="mission-metric">
            <text class="metric-label">答题数</text>
            <text class="metric-value">{{ mission.answer_count || 0 }}</text>
            <text class="metric-extra">应答 {{ expectedAnswers(mission) }}</text>
          </view>
          <view class="mission-metric">
            <text class="metric-label">正确</text>
            <text class="metric-value success">{{ mission.correct_count || 0 }}</text>
            <text class="metric-extra">错误 {{ mission.wrong_count || 0 }}</text>
          </view>
          <view class="mission-metric">
            <text class="metric-label">正确率</text>
            <text class="metric-value success">{{ numberValue(mission.accuracy) }}%</text>
            <text class="metric-extra">待批改 {{ mission.pending_count || 0 }}</text>
          </view>
        </view>

        <view class="student-section-header">
          <text>学生完成情况</text>
          <view class="student-section-actions">
            <text class="student-count">共{{ (mission.students || []).length }}人</text>
            <button class="expand-button" size="mini" @click="toggleMission(mission.mission_id)">{{ isExpanded(mission.mission_id) ? '收起' : '展开' }}</button>
          </view>
        </view>
        <scroll-view v-if="isExpanded(mission.mission_id)" scroll-x class="student-table-scroll">
          <view class="student-table">
            <view class="student-table-row student-table-header">
              <text class="student-col name">学生</text><text class="student-col">完成情况</text><text class="student-col">答题数</text><text class="student-col">正确/错误</text><text class="student-col">正确率</text><text class="student-col">状态</text>
            </view>
            <view v-for="student in mission.students || []" :key="student.student_id" class="student-table-row">
              <text class="student-col name">{{ student.student_name || student.mobile || '-' }}</text>
              <text class="student-col">{{ student.answered_count || 0 }}/{{ student.question_count || 0 }}（{{ numberValue(student.completion_rate) }}%）</text>
              <text class="student-col">{{ student.answered_count || 0 }}</text>
              <text class="student-col">{{ student.correct_count || 0 }}/{{ student.wrong_count || 0 }}</text>
              <text class="student-col success">{{ numberValue(student.accuracy) }}%</text>
              <text class="student-col" :class="studentStatusClass(student.status)">{{ student.status || '未开始' }}</text>
            </view>
            <view v-if="!(mission.students || []).length" class="empty-hint">该作业暂无学生数据</view>
          </view>
        </scroll-view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'
import { formatDateOnly } from '@/utils/display-format'
import type { UUID } from '@/types/uuid'

interface ClassOption {
  id: UUID
  class_name: string
  class_no?: string
}

const classes = ref<ClassOption[]>([])
const routeClassId = ref('')
const classId = ref<UUID | ''>('')
const loadingClasses = ref(false)
const loading = ref(false)
const stats = ref<any>({ missions: [], students: [], summary: {} })
const expandedMissions = ref<Record<string, boolean>>({})

const selectedClassIndex = computed(() => {
  const index = classes.value.findIndex(item => String(item.id) === String(classId.value))
  return index >= 0 ? index : 0
})
const selectedClassName = computed(() => classes.value.find(item => String(item.id) === String(classId.value))?.class_name || '')
const summary = computed(() => {
  const value = stats.value.summary || {}
  return {
    student_count: Number(value.student_count ?? stats.value.student_count ?? 0),
    mission_count: Number(value.mission_count ?? stats.value.mission_count ?? 0),
    completion_rate: numberValue(value.completion_rate),
    answer_count: Number(value.answer_count || 0),
    accuracy: numberValue(value.accuracy),
    pending_count: Number(value.pending_count || 0),
  }
})
const missions = computed(() => Array.isArray(stats.value.missions) ? stats.value.missions : [])

onLoad((options: any) => {
  routeClassId.value = String(options?.classId || '').trim()
})

onMounted(() => {
  initialize()
})

async function initialize() {
  loadingClasses.value = true
  try {
    const response: any = await classApi.list()
    const items = response.data?.items || response.data || []
    classes.value = Array.isArray(items) ? items : []
    classId.value = routeClassId.value || classes.value[0]?.id || ''
    if (classId.value) await loadStats()
  } catch (error) {
    console.error('加载班级失败:', error)
    classes.value = []
    uni.showToast({ title: '加载班级失败', icon: 'none' })
  } finally {
    loadingClasses.value = false
  }
}

async function handleClassChange(event: any) {
  const index = Number(event?.detail?.value || 0)
  const selected = classes.value[index]
  if (!selected || String(selected.id) === String(classId.value)) return
  classId.value = selected.id
  await loadStats()
}

async function loadStats() {
  if (!classId.value) return
  loading.value = true
  stats.value = { missions: [], students: [], summary: {} }
  try {
    const response: any = await classApi.learningStats(classId.value)
    if (response?.code !== undefined && response.code !== 0) throw new Error(response.message || '加载学情失败')
    stats.value = response?.data || { missions: [], students: [], summary: {} }
    const expanded: Record<string, boolean> = {}
    for (const mission of missions.value) expanded[String(mission.mission_id)] = true
    expandedMissions.value = expanded
  } catch (error) {
    console.error('加载学情失败:', error)
    uni.showToast({ title: '加载学情失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function toggleMission(missionId: string) {
  const key = String(missionId)
  expandedMissions.value[key] = !isExpanded(key)
}
function isExpanded(missionId: string) {
  return expandedMissions.value[String(missionId)] === true
}
function goMission(missionId: string) {
  const query = classId.value ? '&classId=' + encodeURIComponent(String(classId.value)) : ''
  uni.navigateTo({
    url: '/pages/teacher/mission-learning-stats?missionId=' + encodeURIComponent(String(missionId)) + query,
  })
}
function numberValue(value: any) {
  const number = Number(value || 0)
  return Number.isInteger(number) ? String(number) : number.toFixed(2)
}
function expectedAnswers(mission: any) {
  return Number(mission.expected_answer_count ?? (
    Number(mission.question_count || 0) * Number(mission.student_count || 0)
  ))
}
function formatMissionDate(value?: string | null) {
  return value ? formatDateOnly(value, '未设置') : '未设置'
}
function missionStatusText(status?: string) {
  return ({ draft: '未发布', published: '已发布', running: '进行中', closed: '已结束' } as Record<string, string>)[status || ''] || '未知状态'
}
function missionStatusClass(status?: string) {
  return 'mission-status-' + (status || 'unknown')
}
function studentStatusClass(status?: string) {
  return 'student-status-' + (status || '未开始')
}
</script>

<style scoped>
.stats-page { min-height: 100%; padding: 24px 24px 30px; background: #f5f7fa; box-sizing: border-box; overflow-y: auto; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }.page-title { font-size: 20px; font-weight: 600; color: #303133; }
.class-filter { display: flex; align-items: center; gap: 10px; }.filter-label { color: #606266; font-size: 14px; }.picker-control { min-width: 180px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 4px; background: #fff; color: #303133; font-size: 14px; cursor: pointer; }.picker-arrow { color: #909399; font-size: 16px; }
.overview-card, .mission-card, .empty-card { background: #fff; border-radius: 8px; }.overview-card, .mission-card { padding: 20px; }.empty-card { padding: 50px 20px; text-align: center; color: #909399; }.overview-card { margin-bottom: 20px; }
.overview-title { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 18px; color: #303133; font-size: 17px; font-weight: 600; }.overview-subtitle { color: #909399; font-size: 13px; font-weight: 400; }.summary-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }.summary-item { padding: 14px 10px; text-align: center; background: #f8fafc; border-radius: 6px; }.summary-label { display: block; color: #909399; font-size: 13px; }.summary-value { display: block; margin-top: 8px; color: #303133; font-size: 22px; font-weight: 600; }.primary { color: #409eff; }.success { color: #67c23a; }.warning { color: #e6a23c; }
.mission-card { margin-bottom: 20px; }.mission-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }.mission-title-area { min-width: 0; }.mission-title { display: block; overflow: hidden; color: #303133; font-size: 17px; font-weight: 600; white-space: nowrap; text-overflow: ellipsis; }.mission-no { display: block; margin-top: 6px; color: #909399; font-size: 12px; }.mission-header-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }.mission-status { padding: 4px 8px; border-radius: 4px; font-size: 12px; }.mission-status-published { color: #409eff; background: #ecf5ff; }.mission-status-running { color: #67c23a; background: #f0f9eb; }.mission-status-closed { color: #909399; background: #f4f4f5; }.mission-status-draft,.mission-status-unknown { color: #e6a23c; background: #fdf6ec; }
.detail-button, .expand-button { margin: 0; color: #409eff; background: #ecf5ff; border: 1px solid #b3d8ff; }.detail-button { min-width: 110px; }.expand-button { min-width: 56px; }.mission-meta { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 14px; color: #909399; font-size: 13px; }
.mission-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; padding: 16px 0; border-top: 1px solid #ebeef5; border-bottom: 1px solid #ebeef5; }.mission-metric { padding: 0 14px; border-right: 1px solid #ebeef5; }.mission-metric:last-child { border-right: 0; }.metric-label,.metric-extra { display: block; color: #909399; font-size: 13px; }.metric-value { display: inline-block; margin-top: 7px; margin-right: 8px; color: #303133; font-size: 20px; font-weight: 600; }.metric-rate { font-size: 14px; }.metric-extra { margin-top: 5px; font-size: 12px; }
.student-section-header { display: flex; align-items: center; justify-content: space-between; margin-top: 18px; color: #303133; font-size: 15px; font-weight: 600; }.student-section-actions { display: flex; align-items: center; gap: 10px; }.student-count { color: #909399; font-size: 12px; font-weight: 400; }.student-table-scroll { width: 100%; margin-top: 10px; }.student-table { min-width: 760px; }.student-table-row { display: grid; grid-template-columns: 1.5fr 1.5fr 1fr 1fr 1fr 1fr; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid #f2f6fc; color: #606266; font-size: 13px; }.student-table-header { color: #909399; border-bottom-color: #ebeef5; }.student-col { min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.student-col.name { color: #303133; }.student-status-已批改 { color: #67c23a; }.student-status-已提交 { color: #e6a23c; }.student-status-进行中 { color: #409eff; }.student-status-未开始 { color: #909399; }.empty-hint { padding: 24px 0; text-align: center; color: #909399; }
@media (max-width: 900px) { .summary-grid { grid-template-columns: repeat(3, 1fr); }.mission-header { align-items: flex-start; flex-direction: column; }.mission-header-right { width: 100%; justify-content: space-between; } }
@media (max-width: 600px) { .stats-page { padding: 16px 16px 30px; }.page-header { align-items: flex-start; flex-direction: column; gap: 12px; }.class-filter { width: 100%; }.class-filter picker { flex: 1; }.picker-control { min-width: 0; }.summary-grid { grid-template-columns: repeat(2, 1fr); }.overview-title { align-items: flex-start; flex-direction: column; gap: 8px; }.mission-metrics { grid-template-columns: repeat(2, 1fr); }.mission-metric:nth-child(2) { border-right: 0; }.mission-metric:nth-child(-n+2) { padding-bottom: 14px; border-bottom: 1px solid #ebeef5; } }
</style>
