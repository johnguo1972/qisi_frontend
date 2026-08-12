<template>
  <view class="container">
    <view class="page-header">
      <text class="page-title">作业列表</text>
      <button class="btn-create" @click="goCreateMission">+ 新增作业</button>
    </view>

    <view class="filter-bar">
      <text class="filter-label">科目</text>
      <picker
        class="subject-picker"
        mode="selector"
        :range="subjectRange"
        :value="subjectIndex"
        @change="onSubjectChange"
      >
        <view class="subject-select">{{ subjectLabel }}</view>
      </picker>
      <button v-if="selectedSubject" class="btn-reset" size="mini" @click="resetSubject">重置</button>
    </view>

    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="missions.length === 0" class="empty">
      <text>{{ selectedSubject ? '当前科目暂无作业' : '暂无任务，点击“创建任务”开始' }}</text>
    </view>
    <view v-else class="mission-list">
      <view v-for="m in missions" :key="m.id" class="mission-card" @click="goMissionDetail(m.id)">
        <view class="card-header">
          <text class="mission-name">{{ m.mission_name }}</text>
          <text :class="['status-badge', m.status]">{{ statusText(m.status) }}</text>
        </view>
        <view class="card-body">
          <text class="mission-no">编号: {{ m.mission_no }}</text>
          <text class="mission-subject">科目: {{ subjectText(m.subject) }}</text>
          <text v-if="m.goal_text" class="mission-goal">{{ m.goal_text }}</text>
          <text v-if="m.level_count" class="mission-levels">关卡数: {{ m.level_count }}</text>
        </view>
        <view v-if="m.end_at" class="card-footer">
          <text class="mission-start" v-if="m.start_at">开始: {{ formatMissionDate(m.start_at) }}</text>
          <text class="mission-end">截止: {{ formatMissionDate(m.end_at) }}</text>
        </view>
        <view class="card-actions">
          <button size="mini" @click.stop="goGradeMission(m.id)">批改作业</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi, type Mission } from '@/api/missions'

const missions = ref<Mission[]>([])
const loading = ref(false)
const classId = ref<string | undefined>()
const selectedSubject = ref('')
const subjectOptions = [
  { value: '', label: '全部科目' },
  { value: 'math', label: '数学' },
  { value: 'physics', label: '物理' },
]
const subjectRange = subjectOptions.map(item => item.label)
const subjectIndex = computed(() => Math.max(0, subjectOptions.findIndex(item => item.value === selectedSubject.value)))
const subjectLabel = computed(() => subjectOptions[subjectIndex.value]?.label || '全部科目')

onLoad((options: any) => {
  const queryClassId = String(options?.classId || '').trim()
  classId.value = queryClassId || undefined
})

onMounted(() => {
  loadMissions()
})

async function loadMissions() {
  loading.value = true
  try {
    const params: { class_id?: string; subject?: string } = {}
    if (classId.value) params.class_id = classId.value
    if (selectedSubject.value) params.subject = selectedSubject.value
    const res: any = await missionApi.list(Object.keys(params).length ? params : undefined)
    missions.value = (res.data || []) as Mission[]
  } catch (e) {
    console.error('加载任务列表失败:', e)
    uni.showToast({ title: '加载任务列表失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function onSubjectChange(e: any) {
  const index = Number(e?.detail?.value)
  selectedSubject.value = subjectOptions[index]?.value || ''
  loadMissions()
}

function resetSubject() {
  selectedSubject.value = ''
  loadMissions()
}

function subjectText(subject?: string): string {
  return subject || '未设置'
}

function formatMissionDate(value?: string): string {
  if (!value) return ''
  const text = String(value).trim()
  const iso = text.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/)
  if (iso) return `${iso[1]} ${iso[2]}`
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text.replace('T', ' ').replace(/([+-]\d{2}:\d{2}|Z)$/, '')
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
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

function goMissionDetail(id: string) {
  uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${id}` })
}

function goGradeMission(id: string) {
  uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${id}&mode=grading` })
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
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 12px;
  background: #fff;
  border-radius: 8px;
}
.filter-label {
  color: #606266;
  font-size: 14px;
}
.subject-picker {
  width: 132px;
  max-width: 100%;
  box-sizing: border-box;
}
.subject-select {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 100%;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.btn-reset {
  margin: 0;
  color: #606266;
  background: #f4f4f5;
  border: 1px solid #dcdfe6;
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
.mission-subject {
  font-size: 13px;
  color: #409eff;
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
.mission-start {
  margin-right: 18px;
  font-size: 12px;
  color: #909399;
}
.card-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
