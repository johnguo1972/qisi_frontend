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
      <text>处理 {{ batch.requested_count }} 条，成功 {{ batch.generated_count }} 条，失败 {{ batch.failed_count }} 条</text>
      <button v-if="batch.status === 'published' || batch.status === 'partially_failed'" size="mini" @click="loadRecommendations">查看 AI 推荐</button>
      <view v-for="rec in recommendations" :key="rec.id" class="recommendation">
        <checkbox :value="rec.id" :checked="selectedRecommendations.includes(rec.id)" @click="selectRecommendation(rec.id)" />
        <text>{{ rec.candidate?.question_no || rec.candidate_question_id }}（{{ statusLabel(rec.status) }}）</text>
      </view>
      <button v-if="selectedRecommendations.length" size="mini" type="primary" @click="confirmRecommendations">确认 AI 补充</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/missions'

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
const recommendations = ref<any[]>([])
const selectedRecommendations = ref<string[]>([])
const questionPanelVisible = ref(true)
const selectedQuestionId = ref('')
const selectedQuestion = computed(() => (
  matrix.value?.questions?.find((question: any) => question.id === selectedQuestionId.value) || null
))
const canGenerate = computed(() => (!!matrix.value?.marked_count || pending.value.some(item => item.wrong)) && matrix.value?.status !== 'scope_changed' && matrix.value?.status !== 'closed')
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
}
let pollTimer: ReturnType<typeof setInterval> | undefined

onLoad((options: any) => {
  missionId.value = String(options?.missionId || options?.id || '')
  loadMissionName()
  loadMatrix()
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

function changeClass(event: any) {
  classId.value = classIds.value[Number(event.detail.value)] || ''
  loadMatrix()
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
    const res: any = await missionApi.generateWrongbook(missionId.value, {
      version: matrix.value.version,
      idempotency_key: `${missionId.value}-${matrix.value.version}`,
      related_limit: 3,
    })
    batch.value = res.data
    if (batch.value?.status === 'queued' || batch.value?.status === 'generating' || batch.value?.status === 'snapshotting' || batch.value?.status === 'publishing') {
      if (pollTimer) clearInterval(pollTimer)
      pollTimer = setInterval(async () => {
        const status: any = await missionApi.wrongbookGeneration(missionId.value, batch.value.id)
        batch.value = status.data
        if (!['queued', 'generating', 'snapshotting', 'publishing'].includes(batch.value.status) && pollTimer) {
          clearInterval(pollTimer)
          pollTimer = undefined
          await loadMatrix()
        }
      }, 1500)
    }
    uni.showToast({ title: '已提交生成任务', icon: 'success' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '生成失败', icon: 'none' })
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
.recommendation { display: flex; align-items: center; gap: 8px; padding-top: 8px; font-size: 13px; }
</style>
