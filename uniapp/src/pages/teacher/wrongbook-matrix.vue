<template>
  <view class="page">
    <view class="toolbar">
      <view>
        <text class="title">{{ missionName || '作业' }} · 学生错题统计</text>
        <text class="sub">已标记 {{ matrix?.marked_count || 0 }} 题</text>
      </view>
      <view class="actions">
        <picker :range="classLabels" :value="classIndex" @change="changeClass">
          <button size="mini">{{ classLabels[classIndex] || '全部班级' }}</button>
        </picker>
        <button size="mini" @click="loadMatrix">刷新</button>
        <button size="mini" :disabled="!pending.length" @click="save">保存标记</button>
        <button size="mini" type="primary" :disabled="!canGenerate" @click="generate">生成错题练习</button>
      </view>
    </view>

    <view v-if="matrixNotice" class="status-banner" :class="`status-${matrixNotice.type}`">
      <view class="status-copy">
        <text class="status-title">{{ matrixNotice.title }}</text>
        <text class="status-message">{{ matrixNotice.message }}</text>
      </view>
      <view class="status-actions">
        <button v-if="matrixNotice.action === 'refresh'" size="mini" type="primary" @click="refreshScope">刷新范围</button>
        <button v-if="matrixNotice.action === 'candidate'" size="mini" type="primary" @click="openCandidateSelector">继续选择同类题</button>
        <button v-if="latestGeneration?.final_mission_id" size="mini" @click="viewGeneratedMission">查看已生成作业</button>
      </view>
    </view>

    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="!matrix || !matrix.questions?.length || !matrix.students?.length" class="state">
      当前作业暂无可展示的学生或题目；仍可进入页面，但没有错题标记时不能生成。
    </view>
    <scroll-view v-else scroll-x class="matrix-scroll">
      <view class="matrix" :style="{ minWidth: `${Math.max(620, 220 + matrix.questions.length * 92)}px` }">
        <view class="matrix-row header">
          <view class="student-col">学生 / 学号</view>
          <view v-for="question in matrix.questions" :key="question.id" class="question-col question-header" @click="openQuestion(question)">
            <text class="question-no">{{ question.question_no || question.sort_no }}</text>
            <text class="question-id">{{ question.id }}</text>
          </view>
        </view>
        <view v-for="student in matrix.students" :key="student.student_id" class="matrix-row">
          <view class="student-col student-name">{{ student.student_name }}<text>{{ student.student_no }}</text></view>
          <button
            v-for="cell in student.cells"
            :key="`${cell.student_id}-${cell.source_question_id}`"
            class="question-col cell"
            :class="{ marked: cell.wrong }"
            :disabled="!canEdit"
            @click="toggle(cell)"
          >{{ cell.wrong ? '×' : '' }}</button>
        </view>
      </view>
    </scroll-view>

    <view v-if="questionPanelVisible && matrix?.questions?.length" class="question-panel">
      <view class="question-panel-head">
        <text class="question-panel-title">{{ selectedQuestion ? `第 ${selectedQuestion.question_no} 题` : '全部题目' }}</text>
        <view class="question-panel-actions">
          <button v-if="selectedQuestion" size="mini" @click="showAllQuestions">全部题目</button>
          <button size="mini" @click="closeQuestionPanel">关闭</button>
        </view>
      </view>
      <view v-if="selectedQuestion" class="question-detail">
        <text class="detail-label">题目编号</text>
        <text class="detail-id">{{ selectedQuestion.id }}</text>
        <text class="detail-label">题号</text>
        <text class="detail-value">{{ selectedQuestion.question_no }}</text>
        <text class="detail-label">题目内容</text>
        <text class="detail-stem">{{ selectedQuestion.snapshot?.stem || selectedQuestion.snapshot?.stem_html || '暂无题干内容' }}</text>
        <view v-for="option in (selectedQuestion.snapshot?.options_html || [])" :key="option.label" class="detail-option">
          <text>{{ option.label }}. {{ option.content }}</text>
        </view>
      </view>
      <view v-else class="question-list">
        <view v-for="question in matrix.questions" :key="question.id" class="question-list-item" @click="openQuestion(question)">
          <text class="question-list-no">{{ question.question_no || question.sort_no }}</text>
          <text class="question-list-id">{{ question.id }}</text>
          <rich-text
            class="question-list-stem"
            :nodes="question.snapshot?.stem_html || question.snapshot?.stem || '暂无题干内容'"
          />
          <view v-for="option in (question.snapshot?.options_html || [])" :key="option.label" class="question-list-option">
            <text>{{ option.label }}. {{ option.content }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="batch" class="result-card">
      <view class="result-title">生成批次：{{ batchStatusLabel(batch.status) }}</view>
      <text v-if="batch.created_at" class="result-time">提交时间：{{ formatDate(batch.created_at) }}</text>
      <text>处理 {{ batch.requested_count }} 条，成功 {{ batch.generated_count }} 条，失败 {{ batch.failed_count }} 条</text>
      <button v-if="batch.status === 'awaiting_selection'" size="mini" type="primary" @click="openCandidateSelector">手动选择同类题</button>
      <button v-if="batch.final_mission_id" size="mini" @click="viewGeneratedMission">查看已生成作业</button>
      <button v-if="batch.status === 'published' || batch.status === 'partially_failed'" size="mini" @click="loadRecommendations">查看 AI 推荐</button>
      <view v-for="rec in recommendations" :key="rec.id" class="recommendation">
        <checkbox :value="rec.id" :checked="selectedRecommendations.includes(rec.id)" @click="selectRecommendation(rec.id)" />
        <text>{{ rec.candidate?.question_no || rec.candidate_question_id }}（{{ statusLabel(rec.status) }}）</text>
      </view>
      <button v-if="selectedRecommendations.length" size="mini" type="primary" @click="confirmRecommendations">确认 AI 补充</button>
    </view>

    <view v-if="generationHistory.length > 1" class="history-card">
      <text class="history-title">历史生成批次（{{ generationHistory.length }}）</text>
      <view v-for="historyItem in generationHistory" :key="historyItem.id" class="history-item">
        <view>
          <text class="history-status">{{ batchStatusLabel(historyItem.status) }}</text>
          <text class="history-meta">处理 {{ historyItem.requested_count }} 条 · 成功 {{ historyItem.generated_count }} 条 · {{ formatDate(historyItem.created_at) }}</text>
        </view>
        <button v-if="historyItem.final_mission_id" size="mini" @click="viewGeneratedMission(historyItem)">查看作业</button>
      </view>
    </view>

    <TeacherWrongbookCandidateSelector
      v-if="candidateSelectorVisible"
      :groups="candidateGroups"
      :submitting="candidateSubmitting"
      @close="candidateSelectorVisible = false"
      @confirm="confirmTeacherCandidates"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/missions'
import TeacherWrongbookCandidateSelector from '@/components/TeacherWrongbookCandidateSelector.vue'

const missionId = ref('')
const missionName = ref('')
const matrix = ref<any>(null)
const loading = ref(false)
const classId = ref('')
const classLabels = ref(['全部班级'])
const classIds = ref<string[]>([''])
const classIndex = computed(() => Math.max(0, classIds.value.indexOf(classId.value)))
const pending = ref<Array<{ student_id: string; source_question_id: string; wrong: boolean }>>([])
const batch = ref<any>(null)
const generationHistory = ref<any[]>([])
const recommendations = ref<any[]>([])
const selectedRecommendations = ref<string[]>([])
const candidateGroups = ref<any[]>([])
const candidateSelectorVisible = ref(false)
const candidateSubmitting = ref(false)
const questionPanelVisible = ref(true)
const selectedQuestionId = ref('')
const selectedQuestion = computed(() => (
  matrix.value?.questions?.find((question: any) => question.id === selectedQuestionId.value) || null
))
const pendingMarkedCount = computed(() => pending.value.filter(item => item.wrong).length)
const markedCount = computed(() => Number(matrix.value?.marked_count || 0))
const generatedCount = computed(() => Number(matrix.value?.generated_count || 0))
const hasGenerationHistory = computed(() => Boolean(matrix.value?.has_generation_history || generationHistory.value.length))
const latestGeneration = computed(() => batch.value || matrix.value?.latest_batch || generationHistory.value[0] || null)
const canEdit = computed(() => Boolean(matrix.value) && matrix.value.status !== 'scope_changed' && matrix.value.status !== 'closed')
const canGenerate = computed(() => (markedCount.value > 0 || pendingMarkedCount.value > 0) && canEdit.value)
const matrixNotice = computed(() => {
  const status = matrix.value?.status
  const latestStatus = latestGeneration.value?.status
  if (!matrix.value) return null
  if (status === 'closed') {
    return { type: 'info', title: '错题练习已关闭', message: '当前作业不再接受新的错题标记或生成请求。' }
  }
  if (status === 'scope_changed') {
    if (hasGenerationHistory.value) {
      return {
        type: 'warning',
        title: '该作业已经生成过错题练习',
        message: `当前矩阵范围已发生变化，历史练习不会重复生成；已生成 ${generatedCount.value} 题，请到历史批次或已生成作业查看。`,
      }
    }
    return {
      type: 'warning',
      title: '错题范围已变化',
      message: '作业的学生或题目范围发生了变化，请先刷新范围后再保存和生成。',
      action: 'refresh',
    }
  }
  if (latestStatus === 'awaiting_selection') {
    return {
      type: 'warning',
      title: '生成任务等待教师选择',
      message: '部分错题缺少足够的 AI 推荐，请为每个错题选择同类题后继续生成。',
      action: 'candidate',
    }
  }
  if (['queued', 'generating', 'snapshotting', 'publishing', 'retrying'].includes(latestStatus)) {
    return { type: 'info', title: '错题练习正在生成', message: '系统正在处理最新生成批次，请稍候或点击刷新查看结果。' }
  }
  if (hasGenerationHistory.value && generatedCount.value > 0 && markedCount.value === 0) {
    return {
      type: 'success',
      title: '错题练习已生成',
      message: `当前没有待生成的错题，最近批次已生成 ${generatedCount.value} 题。可查看历史批次或已生成作业。`,
    }
  }
  return null
})
const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  generating: '生成中',
  snapshotting: '题目处理中',
  publishing: '发布中',
  published: '已发布',
  partially_failed: '部分失败',
  failed: '生成失败',
  retrying: '重试中',
  generated: '已生成',
  snapshot_failed: '题目处理失败',
  publish_failed: '发布失败',
  suggested: '待确认',
  teacher_selected: '已选择',
  awaiting_selection: '等待教师选择',
}
let pollTimer: ReturnType<typeof setInterval> | undefined

onLoad((options: any) => {
  missionId.value = String(options?.missionId || options?.id || '')
  loadMissionName()
  loadPageData()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

async function loadMatrix() {
  if (!missionId.value) return
  loading.value = true
  try {
    const res: any = await missionApi.wrongbookMatrix(missionId.value, classId.value ? { class_id: classId.value } : undefined)
    matrix.value = res.data
    questionPanelVisible.value = true
    if (!matrix.value?.questions?.some((question: any) => question.id === selectedQuestionId.value)) selectedQuestionId.value = ''
    const classes = new Map<string, string>(classIds.value.slice(1).map((id, index) => [id, classLabels.value[index + 1] || id]))
    for (const student of matrix.value?.students || []) classes.set(student.class_id, student.class_name || student.class_id)
    classIds.value = ['', ...classes.keys()]
    classLabels.value = ['全部班级', ...classes.values()]
    pending.value = []
  } catch (error: any) {
    uni.showToast({ title: error?.message || '作业数据加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function loadMissionName() {
  if (!missionId.value) return
  try {
    const res: any = await missionApi.detail(missionId.value)
    missionName.value = String(res?.data?.mission_name || '').trim()
  } catch {
    // 获取作业名称失败不阻断错题统计页面，保留通用标题。
  }
}

async function loadGenerationHistory() {
  if (!missionId.value) return
  try {
    const res: any = await missionApi.wrongbookHistory(missionId.value)
    generationHistory.value = Array.isArray(res?.data) ? res.data : []
    if (!batch.value && generationHistory.value.length) batch.value = generationHistory.value[0]
  } catch (error: any) {
    // 历史加载失败不阻断矩阵编辑；刷新矩阵时仍可重新加载。
    generationHistory.value = []
  }
}

async function loadPageData() {
  await loadMatrix()
  await loadGenerationHistory()
}

function openQuestion(question: any) {
  selectedQuestionId.value = question.id
  questionPanelVisible.value = true
}

function showAllQuestions() {
  selectedQuestionId.value = ''
  questionPanelVisible.value = true
}

function closeQuestionPanel() {
  questionPanelVisible.value = false
}

function statusLabel(status: string) {
  return STATUS_LABELS[status] || '处理中'
}

function batchStatusLabel(status: string) {
  return statusLabel(status)
}

function formatDate(value: string | Date) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function changeClass(event: any) {
  classId.value = classIds.value[Number(event.detail.value)] || ''
  loadPageData()
}

async function refreshScope() {
  try {
    const res: any = await missionApi.refreshWrongbookScope(missionId.value, classId.value ? { class_id: classId.value } : {})
    matrix.value = res.data
    batch.value = null
    await loadGenerationHistory()
    uni.showToast({ title: '错题范围已刷新', icon: 'success' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '刷新范围失败，请先确认作业范围', icon: 'none' })
  }
}

function viewGeneratedMission(generation: any = latestGeneration.value) {
  const generatedMissionId = generation?.final_mission_id
  if (!generatedMissionId) return
  uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${generatedMissionId}` })
}

function toggle(cell: any) {
  cell.wrong = !cell.wrong
  cell.status = cell.wrong ? 'marked' : 'cancelled'
  const index = pending.value.findIndex(item => item.student_id === cell.student_id && item.source_question_id === cell.source_question_id)
  const change = { student_id: cell.student_id, source_question_id: cell.source_question_id, wrong: cell.wrong }
  if (index >= 0) pending.value[index] = change
  else pending.value.push(change)
}

async function save() {
  if (!pending.value.length) return true
  try {
    const res: any = await missionApi.saveWrongbookMatrix(missionId.value, { version: matrix.value.version, cells: pending.value })
    matrix.value = res.data.matrix
    pending.value = []
    return true
  } catch (error: any) {
    uni.showToast({ title: error?.message || '保存失败，请刷新', icon: 'none' })
    return false
  }
}

async function generate() {
  if (!(await save())) return
  try {
    const res: any = await missionApi.generateTeacherWrongbook(missionId.value, {
      version: matrix.value.version,
      idempotency_key: `${missionId.value}-${matrix.value.version}-teacher-select`,
    })
    batch.value = res.data
    if (batch.value?.status === 'queued' || batch.value?.status === 'generating' || batch.value?.status === 'snapshotting' || batch.value?.status === 'publishing') {
      if (pollTimer) clearInterval(pollTimer)
      pollTimer = setInterval(async () => {
        try {
          const status: any = await missionApi.wrongbookGeneration(missionId.value, batch.value.id)
          batch.value = status.data
          if (!['queued', 'generating', 'snapshotting', 'publishing'].includes(batch.value.status) && pollTimer) {
            clearInterval(pollTimer)
            pollTimer = undefined
            await loadPageData()
            if (batch.value.status === 'awaiting_selection') await openCandidateSelector()
          }
        } catch (error: any) {
          if (pollTimer) {
            clearInterval(pollTimer)
            pollTimer = undefined
          }
          uni.showToast({ title: error?.message || '生成状态获取失败', icon: 'none' })
        }
      }, 1500)
    }
    if (batch.value?.status === 'awaiting_selection') await openCandidateSelector()
    uni.showToast({
      title: batch.value?.status === 'awaiting_selection' ? '部分错题需要手动选择同类题' : '已提交生成任务',
      icon: batch.value?.status === 'awaiting_selection' ? 'none' : 'success',
    })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '生成失败', icon: 'none' })
  }
}

async function openCandidateSelector() {
  if (!batch.value?.id) return
  try {
    const res: any = await missionApi.teacherWrongbookCandidateGroups(missionId.value, batch.value.id)
    candidateGroups.value = res.data || []
    if (candidateGroups.value.length) candidateSelectorVisible.value = true
    else uni.showToast({ title: '暂无需要手动选择的错题', icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '同类题加载失败', icon: 'none' })
  }
}

async function confirmTeacherCandidates(groups: Array<{ student_id: string; source_wrong_book_item_id: string; candidate_question_ids: string[] }>) {
  if (!batch.value?.id) return
  candidateSubmitting.value = true
  try {
    const res: any = await missionApi.confirmTeacherWrongbookCandidateGroups(missionId.value, batch.value.id, {
      groups,
      idempotency_key: `${batch.value.id}-teacher-select`,
    })
    candidateSelectorVisible.value = false
    candidateGroups.value = []
    batch.value = {
      ...batch.value,
      status: 'published',
      final_mission_id: res.data?.mission_id || batch.value.final_mission_id,
    }
    await loadPageData()
    uni.showToast({ title: '错题练习已生成', icon: 'success' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '确认生成失败', icon: 'none' })
  } finally {
    candidateSubmitting.value = false
  }
}

async function loadRecommendations() {
  if (!batch.value?.id) return
  try {
    const res: any = await missionApi.wrongbookRecommendations(missionId.value, batch.value.id, { limit: 10 })
    recommendations.value = res.data || []
  } catch (error: any) {
    uni.showToast({ title: error?.message || '推荐加载失败', icon: 'none' })
  }
}

function selectRecommendation(id: string) {
  selectedRecommendations.value = selectedRecommendations.value.includes(id)
    ? selectedRecommendations.value.filter(item => item !== id)
    : [...selectedRecommendations.value, id]
}

async function confirmRecommendations() {
  try {
    await missionApi.confirmWrongbookRecommendations(missionId.value, batch.value.id, {
      recommendation_ids: selectedRecommendations.value,
      idempotency_key: `${batch.value.id}-ai-confirm`,
    })
    selectedRecommendations.value = []
    await loadRecommendations()
    uni.showToast({ title: 'AI 补充任务已发布', icon: 'success' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '确认失败', icon: 'none' })
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 16px; background: #f5f7fa; box-sizing: border-box; }
.toolbar, .result-card { background: #fff; border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.title { display: block; font-size: 18px; font-weight: 600; color: #303133; }
.sub { display: block; margin-top: 6px; color: #909399; font-size: 12px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.actions button, .result-card button { margin: 0; }
.status-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; margin-bottom: 12px; border: 1px solid; border-radius: 8px; }
.status-copy { min-width: 0; }
.status-title, .status-message { display: block; }
.status-title { font-weight: 600; }
.status-message { margin-top: 4px; font-size: 12px; line-height: 1.5; }
.status-actions { display: flex; flex: 0 0 auto; gap: 8px; flex-wrap: wrap; }
.status-info { color: #2f6fad; background: #f0f7ff; border-color: #b3d8ff; }
.status-warning { color: #9a6700; background: #fff8e6; border-color: #f5d48a; }
.status-success { color: #287d3c; background: #f0fff4; border-color: #b7e1c0; }
.state { padding: 60px 20px; text-align: center; color: #909399; background: #fff; border-radius: 8px; }
.matrix-scroll { background: #fff; border-radius: 8px; }
.matrix-row { display: flex; min-height: 48px; border-bottom: 1px solid #ebeef5; }
.header { background: #f8fafc; font-weight: 600; }
.student-col { width: 180px; flex: 0 0 180px; padding: 12px 10px; box-sizing: border-box; border-right: 1px solid #ebeef5; position: sticky; left: 0; z-index: 1; background: inherit; }
.student-name { color: #303133; }
.student-name text { display: block; color: #909399; font-size: 11px; margin-top: 3px; }
.question-col { width: 92px; flex: 0 0 92px; text-align: center; padding: 12px 4px; box-sizing: border-box; }
.question-header { cursor: pointer; padding: 7px 3px; display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 62px; background: #f8fafc; }
.question-header:active { background: #e6f1ff; }
.question-no { display: block; color: #303133; font-size: 16px; line-height: 22px; }
.question-id { display: block; max-width: 86px; color: #909399; font-size: 9px; font-weight: 400; line-height: 11px; word-break: break-all; }
button.question-col { margin: 0; border-radius: 0; border: 0; border-right: 1px solid #ebeef5; background: #fff; color: #303133; font-size: 20px; }
button.question-col.marked { background: #fff1f0; color: #f56c6c; font-weight: 700; }
button.question-col[disabled] { opacity: .75; cursor: not-allowed; }
.question-panel { position: fixed; top: 48px; right: 0; bottom: 0; z-index: 20; width: 420px; max-width: 86vw; padding: 0 16px 16px; box-sizing: border-box; overflow-y: auto; background: #fff; box-shadow: -4px 0 16px rgba(0, 0, 0, .12); }
.question-panel-head { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 14px 0 12px; background: #fff; border-bottom: 1px solid #ebeef5; }
.question-panel-title { font-size: 16px; font-weight: 600; color: #303133; }
.question-panel-actions { display: flex; gap: 6px; }
.question-list-item { padding: 12px 4px; border-bottom: 1px solid #f0f2f5; cursor: pointer; }
.question-list-no { display: block; font-weight: 600; color: #303133; }
.question-list-id, .detail-id { display: block; margin-top: 4px; color: #909399; font-size: 11px; word-break: break-all; }
.question-list-stem { display: block; margin-top: 9px; color: #303133; font-size: 13px; line-height: 1.6; word-break: break-word; }
.question-list-option { padding-top: 5px; color: #606266; font-size: 12px; line-height: 1.5; word-break: break-word; }
.question-detail { padding-top: 14px; }
.detail-label { display: block; margin-top: 12px; color: #909399; font-size: 12px; }
.detail-value, .detail-stem { display: block; margin-top: 5px; color: #303133; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.detail-option { padding-top: 6px; color: #606266; line-height: 1.5; word-break: break-word; }
.result-title { font-weight: 600; margin-bottom: 6px; }
.result-time { display: block; margin-bottom: 5px; color: #909399; font-size: 12px; }
.recommendation { display: flex; align-items: center; gap: 8px; padding-top: 8px; font-size: 13px; }
.history-card { background: #fff; border-radius: 8px; padding: 14px; margin-bottom: 12px; }
.history-title { display: block; margin-bottom: 8px; font-weight: 600; color: #303133; }
.history-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0; border-top: 1px solid #f0f2f5; }
.history-status, .history-meta { display: block; }
.history-status { color: #409eff; }
.history-meta { margin-top: 3px; color: #909399; font-size: 12px; }
@media (max-width: 640px) {
  .toolbar, .status-banner { align-items: stretch; flex-direction: column; }
  .actions, .status-actions { justify-content: flex-start; }
}
</style>
