<template>
  <view class="page">
    <view class="header">
      <view>
        <text class="title">课堂反馈</text>
        <text class="subtitle">{{ report?.mission_name || '课堂错题反馈话术表' }}</text>
      </view>
      <view class="header-actions">
        <button class="plain-button" :disabled="loading" @click="load">刷新</button>
        <button class="export-button top-export" :disabled="exporting || !report || !['ready', 'partial'].includes(report.status)" @click="exportPdf">{{ exporting ? '生成PDF中...' : '导出课堂反馈PDF' }}</button>
      </view>
    </view>

    <view v-if="classOptions.length > 1" class="toolbar card">
      <text class="label">班级</text>
      <picker :range="classOptions" range-key="class_name" :value="classIndex" @change="changeClass">
        <view class="picker-value">{{ classOptions[classIndex]?.class_name || '请选择班级' }} ▼</view>
      </picker>
    </view>

    <view v-if="errorMessage" class="state card"><text>{{ errorMessage }}</text></view>
    <view v-else-if="loading && !report" class="state card"><text>正在加载课堂反馈...</text></view>
    <template v-else>
      <view class="summary card">
        <view v-for="item in summaryItems" :key="item.label" class="summary-item">
          <text class="summary-label">{{ item.label }}</text>
          <text class="summary-value">{{ item.value }}</text>
        </view>
      </view>
      <view v-if="!report" class="state card">
        <text>当前班级尚未生成课堂反馈</text>
        <button class="primary-button" :disabled="generating" @click="generate">{{ generating ? '生成中...' : '生成课堂反馈' }}</button>
      </view>
      <template v-else>
        <view class="status-line card"><text>报告状态：{{ statusText(report.status) }}</text><text v-if="report.source_matrix_version">数据版本：{{ report.source_matrix_version }}</text></view>
        <view v-if="report.status === 'stale'" class="notice-box">统计数据已更新，请重新生成最新课堂反馈。</view>
        <view v-if="report.error_message" class="error-box">{{ report.error_message }}</view>
        <view class="card">
          <text class="section-title">班级整体反馈话术</text>
          <view class="script-box"><text>{{ report.class_feedback_text || '话术生成中...' }}</text></view>
          <button v-if="report.class_feedback_text" class="plain-button" @click="copy(report.class_feedback_text)">复制话术</button>
        </view>
        <view class="card">
          <text class="section-title">知识点掌握情况</text>
          <view class="table header-row"><text>知识点</text><text>错误次数</text><text>错误率</text><text>掌握情况</text></view>
          <view v-for="item in report.knowledge_stats" :key="item.knowledge_key" class="table"><text>{{ item.knowledge_name }}</text><text>{{ item.wrong_count }}</text><text :class="{ danger: item.error_rate >= 50 }">{{ item.error_rate }}%</text><text>{{ masteryText(item.mastery_level) }}</text></view>
        </view>
        <view class="card">
          <view class="section-line"><text class="section-title">{{ showAllQuestions ? '全部题目统计' : '高错误率题目' }}</text><button class="plain-button small-button" @click="showAllQuestions = !showAllQuestions">{{ showAllQuestions ? '仅看高错误率' : '查看全部题目' }}</button></view>
          <view class="table header-row"><text>讲义/节点·题号</text><text>知识点</text><text>错误人数</text><text>错误率</text></view>
          <view v-for="item in visibleQuestions" :key="item.source_question_id" class="table"><text>{{ questionLabel(item) }}</text><text>{{ item.knowledge_points.join('、') }}</text><text>{{ item.wrong_count }}人</text><text :class="{ danger: item.wrong_rate >= 50 }">{{ item.wrong_rate }}%</text></view>
        </view>
        <view class="card">
          <view class="section-line"><text class="section-title">学生个人反馈（{{ report.students.length }}人）</text><button class="primary-button small-button" :disabled="generating" @click="generate">{{ generating ? '生成中' : '重新生成' }}</button></view>
          <view v-for="student in report.students" :key="student.student_id" class="student-card">
            <text class="student-name">{{ student.student_name }}</text>
            <view class="student-feedback-table">
              <view class="student-table-row student-table-header"><text>项目</text><text>内容</text></view>
              <view class="student-table-row"><text>错题（{{ student.wrong_count }}道）</text><text>{{ studentWrongQuestionText(student) }}</text></view>
              <view class="student-table-row"><text>涉及板块</text><text>{{ knowledgeText(student) }}</text></view>
              <view class="student-table-row"><text>核心错误知识点</text><text>{{ coreKnowledgeText(student) }}</text></view>
              <view class="student-table-row"><text>重练安排</text><text>{{ student.review_arrangement.join('；') || '请结合错题完成订正和重练。' }}</text></view>
            </view>
            <text class="student-meta">反馈话术</text>
            <view class="script-box"><text>{{ student.feedback_text || '话术生成中...' }}</text></view>
            <button v-if="student.feedback_text" class="plain-button" @click="copy(student.feedback_text)">复制该生话术</button>
          </view>
        </view>
      </template>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classroomFeedbackApi } from '@/api/classroom-feedback'
import { getPublicMediaUrl } from '@/utils/media-url'

const missionId = ref('')
const classId = ref('')
const classOptions = ref<any[]>([])
const classIndex = ref(0)
const report = ref<any>(null)
const currentSummary = ref<any>({})
const loading = ref(false)
const generating = ref(false)
const exporting = ref(false)
const errorMessage = ref('')
const showAllQuestions = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const summaryItems = computed(() => [
  { label: '参考人数', value: `${report.value?.participant_count ?? currentSummary.value.participant_count ?? 0}人` },
  { label: '统计题量', value: `${report.value?.question_count ?? currentSummary.value.question_count ?? 0}题` },
  { label: '累计错题', value: `${report.value?.total_wrong_count ?? currentSummary.value.total_wrong_count ?? 0}次` },
  { label: '人均错题', value: `${report.value?.average_wrong_count ?? currentSummary.value.average_wrong_count ?? 0}道` },
])
const visibleQuestions = computed(() => showAllQuestions.value
  ? (report.value?.question_stats || [])
  : (report.value?.high_error_questions || []))

function unwrap(response: any) {
  if (response?.code !== undefined && response.code !== 0) throw new Error(response.message || '请求失败')
  return response?.data || {}
}

async function load() {
  if (!missionId.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const data = unwrap(await classroomFeedbackApi.detail(missionId.value, classId.value ? { class_id: classId.value } : undefined))
    classOptions.value = data.class_options || []
    const selected = classOptions.value.findIndex((item: any) => String(item.class_id) === String(data.class_id))
    if (selected >= 0) classIndex.value = selected
    classId.value = data.class_id || classId.value
    currentSummary.value = data.overview || data.current_summary || {}
    report.value = data.report || null
    if (report.value && ['queued', 'running'].includes(report.value.status)) schedulePoll()
  } catch (error: any) {
    errorMessage.value = error?.message || '课堂反馈加载失败'
  } finally {
    loading.value = false
  }
}

function schedulePoll() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(load, 2000)
}

function changeClass(event: any) {
  classIndex.value = Number(event.detail.value)
  classId.value = classOptions.value[classIndex.value]?.class_id || ''
  report.value = null
  load()
}

async function generate() {
  if (generating.value || !classId.value) return
  generating.value = true
  try {
    const detail = unwrap(await classroomFeedbackApi.detail(missionId.value, { class_id: classId.value }))
    await classroomFeedbackApi.generate(missionId.value, {
      class_id: classId.value,
      matrix_version: detail.current_matrix_version,
      idempotency_key: `${missionId.value}-${classId.value}-${Date.now()}`,
      force: true,
    })
    await load()
  } catch (error: any) {
    errorMessage.value = error?.message || '反馈生成失败'
  } finally {
    generating.value = false
  }
}

async function exportPdf() {
  if (!report.value || exporting.value) return
  exporting.value = true
  try {
    const response: any = await classroomFeedbackApi.exportPdf(missionId.value, { class_id: classId.value, report_id: report.value.id })
    const data = unwrap(response)
    const url = getPublicMediaUrl(data.download_url)
    if (url && typeof window !== 'undefined' && window.open) window.open(url, '_blank')
    else if (url) uni.showToast({ title: 'PDF已生成，请在浏览器打开', icon: 'none' })
  } catch (error: any) {
    errorMessage.value = error?.message || 'PDF导出失败'
  } finally {
    exporting.value = false
  }
}

function copy(text: string) {
  uni.setClipboardData({ data: text, success: () => uni.showToast({ title: '已复制', icon: 'success' }) })
}
function statusText(value: string) { return ({ queued: '排队中', running: '生成中', ready: '已完成', partial: '部分完成', stale: '数据已更新', failed: '失败' } as any)[value] || value }
function masteryText(value: string) { return ({ good: '掌握较好', attention: '基本掌握，需巩固', weak: '薄弱，需重点训练' } as any)[value] || '待关注' }
function knowledgeText(student: any) { return student.knowledge_summary?.join('、') || '待归类题目' }
function questionLabel(item: any) { return `${item.node_name || '未分节点'}·第${item.question_no}题` }
function studentWrongQuestionText(student: any) {
  if (student.wrong_questions?.length) return student.wrong_questions.map((item: any) => `${item.node_name || '未分节点'}·第${item.question_no}题`).join('、')
  return student.wrong_question_nos?.length ? student.wrong_question_nos.join('、') : '无'
}
function coreKnowledgeText(student: any) {
  const points = (student.knowledge_summary || []).filter((item: string) => item !== '待归类题目')
  return points.join('、') || '待归类题目（请结合题干、解析和答案归纳）'
}

onLoad((options: any) => {
  missionId.value = String(options?.mission_id || '')
  classId.value = String(options?.class_id || '')
  load()
})
onUnmounted(() => { if (timer) clearTimeout(timer) })
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 22rpx 60rpx; box-sizing: border-box; background: #f0f2f5; }
.header, .section-line, .status-line { display: flex; align-items: center; justify-content: space-between; gap: 18rpx; }
.header { margin-bottom: 22rpx; }.header-actions { display: flex; align-items: center; gap: 12rpx; flex-shrink: 0; }.top-export { width: 260rpx; margin: 0; }
.title { display: block; color: #303133; font-size: 38rpx; font-weight: 700; }
.subtitle, .student-meta { display: block; margin-top: 8rpx; color: #909399; font-size: 23rpx; line-height: 1.6; }
.card { margin-bottom: 20rpx; padding: 26rpx; border-radius: 16rpx; background: #fff; box-shadow: 0 2rpx 12rpx #0000000d; }
.toolbar { display: flex; align-items: center; justify-content: space-between; }.label { color: #606266; }.picker-value { color: #409eff; }
.summary { display: flex; justify-content: space-between; }.summary-item { flex: 1; text-align: center; }.summary-label { display: block; color: #909399; font-size: 22rpx; }.summary-value { display: block; margin-top: 10rpx; color: #1265bd; font-size: 31rpx; font-weight: 700; }
.state { color: #606266; text-align: center; }.primary-button, .export-button, .plain-button { margin: 16rpx 0 0; padding: 0 20rpx; height: 58rpx; line-height: 58rpx; border-radius: 10rpx; font-size: 23rpx; }.primary-button, .export-button { color: #fff; background: #409eff; }.plain-button { color: #409eff; background: #ecf5ff; border: 1rpx solid #b3d8ff; }.small-button { margin: 0; height: 48rpx; line-height: 48rpx; }.section-title { display: block; margin-bottom: 16rpx; color: #1265bd; font-size: 29rpx; font-weight: 700; }.script-box { padding: 20rpx; color: #303133; background: #f4f8fc; border-left: 8rpx solid #1265bd; font-size: 25rpx; line-height: 1.8; }.table { display: grid; grid-template-columns: 1.35fr .8fr .8fr 1.1fr; gap: 10rpx; padding: 16rpx 0; color: #606266; font-size: 23rpx; border-bottom: 1rpx solid #ebeef5; }.header-row { color: #303133; font-weight: 600; background: #f7f9fb; }.danger { color: #f56c6c; font-weight: 700; }.student-card { margin-top: 20rpx; padding-top: 20rpx; border-top: 1rpx solid #ebeef5; }.student-name { display: block; color: #1265bd; font-size: 28rpx; font-weight: 700; }.export-button { width: 100%; margin-top: 10rpx; }.export-button[disabled], .primary-button[disabled] { opacity: .55; }
.student-feedback-table { margin-top: 18rpx; border: 1rpx solid #d9dfe7; }.student-table-row { display: grid; grid-template-columns: 1.1fr 3fr; gap: 0; color: #606266; font-size: 23rpx; line-height: 1.7; border-top: 1rpx solid #d9dfe7; }.student-table-row:first-child { border-top: none; }.student-table-row > text { padding: 16rpx; }.student-table-row > text:first-child { display: flex; align-items: center; background: #f7f9fb; border-right: 1rpx solid #d9dfe7; }.student-table-header { color: #303133; font-weight: 600; background: #f3f6fa; }.student-table-header > text { padding-top: 12rpx; padding-bottom: 12rpx; }
.header-actions .top-export { width: 260rpx; margin: 0; }
.plain-button::after, .primary-button::after, .export-button::after { border: none; }
.notice-box, .error-box { margin-bottom: 20rpx; padding: 18rpx 22rpx; color: #8a6d3b; background: #fcf8e3; border-left: 8rpx solid #f0ad4e; font-size: 23rpx; line-height: 1.6; }
.error-box { color: #a94442; background: #fdf0f0; border-left-color: #f56c6c; }
</style>
