<template>
  <view class="stats-page">
    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="errorMessage" class="state error">{{ errorMessage }}</view>
    <template v-else>
      <view class="page-header">
        <button class="back-btn" @click="goBack">返回作业列表</button>
        <text class="page-title">学情统计</text>
        <text class="mission-name">{{ data.mission_name || '作业' }}</text>
      </view>

      <view class="summary-card">
        <view class="summary-item"><text class="summary-label">学生</text><text class="summary-value">{{ summary.students }}</text></view>
        <view class="summary-item"><text class="summary-label">题目</text><text class="summary-value">{{ summary.questions }}</text></view>
        <view class="summary-item"><text class="summary-label">答对</text><text class="summary-value correct">{{ summary.correct }}</text></view>
        <view class="summary-item"><text class="summary-label">答错</text><text class="summary-value wrong">{{ summary.wrong }}</text></view>
        <view class="summary-item"><text class="summary-label">待批改</text><text class="summary-value pending">{{ summary.pending }}</text></view>
        <view class="summary-item"><text class="summary-label">未作答</text><text class="summary-value">{{ summary.unanswered }}</text></view>
      </view>

      <view class="stats-layout">
        <view class="content-card matrix-card">
        <view class="section-title">
          <text>学生答题矩阵</text>
          <text class="hint">点击单元格查看该学生答案和判定结果</text>
        </view>
        <scroll-view scroll-x class="matrix-scroll">
          <view class="matrix" :style="{ minWidth: matrixWidth }">
            <view class="matrix-row matrix-header">
              <view class="student-column">学生</view>
              <view v-for="question in questions" :key="question.id" class="question-column">
                <text class="question-number">第{{ question.display_no }}题</text>
                <text v-if="question.question_no && question.question_no !== String(question.display_no)" class="source-number">原题{{ question.question_no }}</text>
              </view>
            </view>
            <view v-for="student in students" :key="student.student_id" class="matrix-row">
              <view class="student-column student-name">{{ student.student_name || student.mobile || '-' }}</view>
              <view
                v-for="cell in student.cells"
                :key="cell.question_id"
                class="question-column answer-cell"
                :class="[statusClass(cell.status), isSelected(student.student_id, cell.question_id) ? 'selected' : '']"
                @click="selectCell(student, cell)"
              >
                <text class="status-icon">{{ statusIcon(cell.status) }}</text>
                <text class="cell-answer">{{ cell.answer_text || statusLabel(cell.status) }}</text>
              </view>
            </view>
            <view v-if="students.length === 0" class="empty">暂无学生数据</view>
          </view>
        </scroll-view>
      </view>

        <view class="side-panel">
        <view class="content-card question-list-card">
          <view class="section-title"><text>作业题目</text><text class="hint">共{{ questions.length }}题</text></view>
          <scroll-view scroll-y class="question-list">
            <view
              v-for="question in questions"
              :key="question.id"
              class="question-item"
              :class="{ selected: selectedQuestionId === question.id }"
              @click="selectQuestion(question)"
            >
              <text class="question-item-number">第{{ question.display_no }}题</text>
              <text v-if="question.question_no && question.question_no !== String(question.display_no)" class="question-item-source">原题{{ question.question_no }}</text>
              <text class="question-item-type">{{ questionTypeText(question.question_type) }}</text>
              <rich-text class="question-stem" :nodes="question.stem_html || question.stem || '暂无题干'" />
              <view v-if="question.options?.length" class="question-options">
                <text v-for="option in question.options" :key="option.label" class="question-option">
                  {{ option.label }}. {{ option.content || option.text || '' }}
                </text>
              </view>
            </view>
            <view v-if="questions.length === 0" class="empty">暂无题目</view>
          </scroll-view>
        </view>

        <view class="content-card answer-detail-card">
          <view class="section-title"><text>答题详情</text></view>
          <view v-if="selectedCell" class="answer-detail">
            <view class="detail-meta">
              <text>{{ selectedStudentName }}</text>
              <text>第{{ selectedCell.display_no }}题</text>
              <text :class="statusClass(selectedCell.status)">{{ statusLabel(selectedCell.status) }}</text>
            </view>
            <view class="detail-row">
              <text class="detail-label">学生答案</text>
              <text class="detail-value">{{ selectedCell.answer_text || statusLabel(selectedCell.status) }}</text>
            </view>
            <view v-if="selectedQuestion" class="detail-row">
              <text class="detail-label">正确答案</text>
              <text class="detail-value">{{ correctAnswerText(selectedQuestion.answer) }}</text>
            </view>
            <view v-if="selectedCell.score !== null && selectedCell.score !== undefined" class="detail-row">
              <text class="detail-label">得分</text><text class="detail-value">{{ selectedCell.score }}</text>
            </view>
          </view>
          <view v-else class="empty">请选择学生和题目查看答题详情</view>
        </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/missions'

interface Cell {
  question_id: string
  display_no: number
  status: string
  answer_text?: string
  score?: number | null
}

interface Student {
  student_id: string
  student_name?: string
  mobile?: string
  cells: Cell[]
}

interface Question {
  id: string
  display_no: number
  question_no?: string
  question_type?: string
  stem?: string
  stem_html?: string
  options?: Array<{ label?: string; content?: string; text?: string }>
  answer?: any
}

const missionId = ref('')
const classId = ref('')
const loading = ref(true)
const errorMessage = ref('')
const data = ref<any>({ mission_name: '', summary: {} })
const questions = ref<Question[]>([])
const students = ref<Student[]>([])
const selectedStudentId = ref('')
const selectedQuestionId = ref('')

const summary = computed(() => ({
  students: Number(data.value.summary?.students || 0),
  questions: Number(data.value.summary?.questions || 0),
  correct: Number(data.value.summary?.correct || 0),
  wrong: Number(data.value.summary?.wrong || 0),
  pending: Number(data.value.summary?.pending || 0),
  unanswered: Number(data.value.summary?.unanswered || 0),
}))
const matrixWidth = computed(() => String(Math.max(680, 180 + questions.value.length * 116)) + 'px')
const selectedQuestion = computed(() => questions.value.find(item => item.id === selectedQuestionId.value) || null)
const selectedStudent = computed(() => students.value.find(item => item.student_id === selectedStudentId.value) || null)
const selectedCell = computed(() => selectedStudent.value?.cells.find(item => item.question_id === selectedQuestionId.value) || null)
const selectedStudentName = computed(() => selectedStudent.value?.student_name || selectedStudent.value?.mobile || '-')

onLoad((options: any) => {
  missionId.value = String(options?.missionId || options?.id || '')
  classId.value = String(options?.classId || '').trim()
})

onMounted(() => {
  if (!missionId.value) {
    errorMessage.value = '缺少作业ID'
    loading.value = false
    return
  }
  loadStats()
})

async function loadStats() {
  try {
    const response: any = await missionApi.learningStats(
      missionId.value,
      classId.value ? { class_id: classId.value } : undefined,
    )
    data.value = response?.data || {}
    questions.value = Array.isArray(data.value.questions) ? data.value.questions : []
    students.value = Array.isArray(data.value.students) ? data.value.students : []
    if (students.value.length && questions.value.length) {
      selectedStudentId.value = students.value[0].student_id
      selectedQuestionId.value = questions.value[0].id
    }
  } catch (error) {
    console.error('加载学情统计失败:', error)
    errorMessage.value = '加载学情统计失败'
  } finally {
    loading.value = false
  }
}

function selectCell(student: Student, cell: Cell) {
  selectedStudentId.value = student.student_id
  selectedQuestionId.value = cell.question_id
}

function selectQuestion(question: Question) {
  selectedQuestionId.value = question.id
  if (!selectedStudentId.value && students.value.length) selectedStudentId.value = students.value[0].student_id
}

function isSelected(studentId: string, questionId: string) {
  return selectedStudentId.value === studentId && selectedQuestionId.value === questionId
}

function statusIcon(status: string) {
  return ({ correct: '✅', wrong: '❌', pending: '⏳', unanswered: '—', not_assigned: '·' } as Record<string, string>)[status] || '—'
}

function statusLabel(status: string) {
  return ({ correct: '正确', wrong: '错误', pending: '待批改', unanswered: '未作答', not_assigned: '未布置' } as Record<string, string>)[status] || '未知'
}

function statusClass(status: string) {
  return 'status-' + (status || 'unanswered')
}

function questionTypeText(type?: string) {
  return ({
    single: '单选题', single_choice: '单选题',
    multiple: '多选题', multiple_choice: '多选题',
    judge: '判断题', true_false: '判断题',
    fill: '填空题', fill_blank: '填空题',
    subjective: '主观题', short_answer: '主观题', essay: '主观题',
  } as Record<string, string>)[type || ''] || '题目'
}

function correctAnswerText(answer: any) {
  if (answer === null || answer === undefined || answer === '') return '暂无标准答案'
  if (Array.isArray(answer)) return answer.join('、')
  if (typeof answer === 'object') return answer.answer || answer.text || JSON.stringify(answer)
  return String(answer)
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.redirectTo({ url: '/pages/teacher/layout?section=assignment-list' })
}
</script>

<style scoped>
.stats-page { min-height: 100vh; padding: 30rpx 40rpx; background: #f0f2f5; box-sizing: border-box; }
.state { padding: 100rpx; text-align: center; color: #606266; }.error { color: #f56c6c; }
.page-header { display: flex; align-items: center; gap: 24rpx; margin-bottom: 24rpx; }
.back-btn { margin: 0; font-size: 26rpx; color: #409eff; background: #fff; border: 1px solid #dcdfe6; }
.page-title { font-size: 38rpx; font-weight: 700; color: #303133; }.mission-name { margin-left: auto; color: #606266; font-size: 28rpx; }
.summary-card { display: flex; flex-wrap: wrap; background: #fff; border-radius: 12rpx; padding: 26rpx 12rpx; margin-bottom: 24rpx; }
.summary-item { flex: 1; min-width: 150rpx; text-align: center; border-right: 1px solid #ebeef5; }.summary-item:last-child { border-right: 0; }
.summary-label { display: block; color: #909399; font-size: 24rpx; }.summary-value { display: block; margin-top: 8rpx; color: #303133; font-size: 34rpx; font-weight: 700; }
.summary-value.correct { color: #67c23a; }.summary-value.wrong { color: #f56c6c; }.summary-value.pending { color: #e6a23c; }
.content-card { background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 24rpx; box-sizing: border-box; }
.section-title { display: flex; align-items: center; justify-content: space-between; color: #303133; font-size: 30rpx; font-weight: 700; margin-bottom: 20rpx; }.hint { color: #909399; font-size: 23rpx; font-weight: 400; }
.matrix-scroll { width: 100%; }.matrix { border: 1px solid #ebeef5; }.matrix-row { display: flex; min-height: 84rpx; border-bottom: 1px solid #ebeef5; }.matrix-row:last-child { border-bottom: 0; }
.student-column { flex: 0 0 180rpx; display: flex; align-items: center; padding: 12rpx 16rpx; box-sizing: border-box; border-right: 1px solid #ebeef5; font-size: 26rpx; }
.matrix-header { background: #f5f7fa; }.question-column { flex: 0 0 116rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 8rpx; box-sizing: border-box; border-right: 1px solid #ebeef5; }.question-column:last-child { border-right: 0; }
.question-number { color: #303133; font-size: 24rpx; }.source-number { color: #909399; font-size: 20rpx; margin-top: 4rpx; }.student-name { color: #303133; font-weight: 600; }
.answer-cell { cursor: pointer; }.answer-cell.selected { background: #ecf5ff; outline: 2px solid #409eff; outline-offset: -2px; }.status-icon { font-size: 27rpx; line-height: 1.2; }
.cell-answer { max-width: 105rpx; overflow: hidden; color: #606266; font-size: 20rpx; white-space: nowrap; text-overflow: ellipsis; }.status-correct .cell-answer { color: #67c23a; }.status-wrong .cell-answer { color: #f56c6c; }.status-pending .cell-answer { color: #e6a23c; }.status-not_assigned { color: #c0c4cc; background: #fafafa; }
.empty { padding: 50rpx; text-align: center; color: #909399; }.stats-layout { display: flex; gap: 24rpx; align-items: flex-start; }.matrix-card { flex: 1.8; min-width: 0; }.side-panel { flex: 1; min-width: 360rpx; }.question-list-card,.answer-detail-card { width: 100%; box-sizing: border-box; }
.question-list { max-height: 600rpx; }.question-item { padding: 18rpx; margin-bottom: 12rpx; border: 1px solid #ebeef5; border-radius: 8rpx; }.question-item.selected { border-color: #409eff; background: #ecf5ff; }
.question-item-number { color: #409eff; font-size: 26rpx; font-weight: 700; }.question-item-source,.question-item-type { margin-left: 12rpx; color: #909399; font-size: 22rpx; }.question-stem { display: block; margin-top: 12rpx; color: #303133; font-size: 25rpx; line-height: 1.6; }
.question-options { display: flex; flex-direction: column; margin-top: 12rpx; }.question-option { padding: 4rpx 0; color: #606266; font-size: 23rpx; line-height: 1.5; }
.detail-meta { display: flex; gap: 24rpx; padding-bottom: 20rpx; border-bottom: 1px solid #ebeef5; color: #303133; font-size: 27rpx; font-weight: 600; }.detail-row { display: flex; padding: 22rpx 0; border-bottom: 1px solid #f2f6fc; }.detail-label { flex: 0 0 150rpx; color: #909399; }.detail-value { flex: 1; color: #303133; word-break: break-all; }.status-correct { color: #67c23a; }.status-wrong { color: #f56c6c; }.status-pending { color: #e6a23c; }
@media screen and (max-width: 700px) { .stats-page { padding: 20rpx; }.page-header { flex-wrap: wrap; }.mission-name { width: 100%; margin-left: 0; }.stats-layout { display: block; }.side-panel { min-width: 0; } }
</style>
