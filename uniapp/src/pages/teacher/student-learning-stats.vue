<template>
  <view class="stats-page">
    <view v-if="loading" class="state">加载中...</view>
    <view v-else-if="errorMessage" class="state error">{{ errorMessage }}</view>
    <template v-else>
      <view class="page-header">
        <button class="back-btn" @click="goBack">返回学情统计</button>
        <view class="student-title">
          <text class="page-title">{{ student.name || '学生学情详情' }}</text>
          <text class="class-name">{{ classInfo.name || '班级' }}</text>
        </view>
      </view>

      <view class="summary-card">
        <view class="summary-item"><text class="summary-label">历史作业</text><text class="summary-value">{{ summary.mission_count }}</text></view>
        <view class="summary-item"><text class="summary-label">已作答题</text><text class="summary-value">{{ summary.answered_question_count }}</text></view>
        <view class="summary-item"><text class="summary-label">作答次数</text><text class="summary-value">{{ summary.attempt_count }}</text></view>
        <view class="summary-item"><text class="summary-label">当前正确率</text><text class="summary-value correct">{{ numberValue(summary.accuracy) }}%</text></view>
        <view class="summary-item"><text class="summary-label">待批改</text><text class="summary-value pending">{{ summary.pending_count }}</text></view>
        <view class="summary-item"><text class="summary-label">最近学习</text><text class="summary-time">{{ formatDateTime(summary.last_submitted_at) }}</text></view>
      </view>

      <view class="tabs">
        <text :class="['tab', { active: activeTab === 'history' }]" @click="activeTab = 'history'">历史记录</text>
        <text :class="['tab', { active: activeTab === 'knowledge' }]" @click="activeTab = 'knowledge'">知识图谱</text>
      </view>

      <view v-if="activeTab === 'history'" class="content-card">
        <view class="section-title">
          <text>作业历史</text>
          <text class="hint">共{{ total }}份</text>
        </view>
        <view v-if="!missions.length" class="empty">暂无历史作业记录</view>
        <view v-for="mission in missions" :key="mission.mission_id" class="mission-card">
          <view class="mission-header" @click="toggleMission(mission.mission_id)">
            <view class="mission-main">
              <text class="mission-name">{{ mission.mission_name || '未命名作业' }}</text>
              <text class="mission-meta">{{ mission.mission_no || mission.mission_id }} · {{ formatDateOnly(mission.created_at) }}</text>
            </view>
            <view class="mission-result">
              <text class="mission-status" :class="statusClass(mission.completion_status)">{{ statusLabel(mission.completion_status) }}</text>
              <text class="mission-rate">{{ numberValue(mission.accuracy) }}%</text>
              <text class="expand-icon">{{ isMissionExpanded(mission.mission_id) ? '收起' : '展开' }}</text>
            </view>
          </view>
          <view class="mission-summary">
            <text>题目 {{ mission.question_count || 0 }}</text>
            <text>已作答 {{ mission.answered_count || 0 }}</text>
            <text class="correct">答对 {{ mission.correct_count || 0 }}</text>
            <text class="wrong">答错 {{ mission.wrong_count || 0 }}</text>
            <text class="pending">待批改 {{ mission.pending_count || 0 }}</text>
            <text>最近 {{ formatDateTime(mission.last_submitted_at) }}</text>
          </view>

          <view v-if="isMissionExpanded(mission.mission_id)" class="question-list">
            <view v-for="question in mission.questions || []" :key="question.question_id" class="question-card">
              <view class="question-header" @click="toggleQuestion(mission.mission_id, question.question_id)">
                <text class="question-no">第{{ question.display_no }}题</text>
                <text v-if="question.question_no && question.question_no !== String(question.display_no)" class="source-no">原题{{ question.question_no }}</text>
                <text class="question-status" :class="statusClass(question.status)">{{ statusLabel(question.status) }}</text>
              </view>
              <text v-if="question.question_missing" class="question-missing">题目已删除</text>
              <text v-else class="question-stem">{{ question.stem || '暂无题干' }}</text>
              <view class="answer-row">
                <text>答案：{{ question.answer_text || '未作答' }}</text>
                <text>得分：{{ question.score === null || question.score === undefined ? '-' : question.score }}</text>
                <text>{{ formatDateTime(question.last_submitted_at) }}</text>
              </view>
              <view v-if="question.attempt_history?.length > 1" class="history-toggle" @click.stop="toggleQuestion(mission.mission_id, question.question_id)">
                {{ isQuestionExpanded(mission.mission_id, question.question_id) ? '收起历次作答' : `查看历次作答（${question.attempt_history.length}次）` }}
              </view>
              <view v-if="isQuestionExpanded(mission.mission_id, question.question_id)" class="attempt-list">
                <view v-for="attempt in question.attempt_history || []" :key="attempt.attempt_id" class="attempt-row">
                  <text>第{{ attempt.attempt_no }}次</text>
                  <text>{{ attempt.answer_text || '未作答' }}</text>
                  <text :class="statusClass(attempt.is_subjective_pending ? 'pending' : (attempt.is_correct ? 'correct' : 'wrong'))">
                    {{ attempt.is_subjective_pending ? '待批改' : (attempt.is_correct ? '正确' : '错误') }}
                  </text>
                  <text>{{ attempt.score ?? '-' }}分</text>
                  <text>{{ formatDateTime(attempt.submitted_at) }}</text>
                </view>
              </view>
            </view>
            <view v-if="!(mission.questions || []).length" class="empty">暂无题目记录</view>
          </view>
        </view>
        <view v-if="total > pageSize" class="pagination">
          <button size="mini" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <text>第{{ page }}页</text>
          <button size="mini" :disabled="page * pageSize >= total" @click="changePage(page + 1)">下一页</button>
        </view>
      </view>

      <view v-else class="content-card">
        <view class="section-title"><text>知识图谱</text><text class="hint">按学生历史作答聚合</text></view>
        <view class="legend"><text><i class="dot mastered"></i>已掌握</text><text><i class="dot reviewing"></i>巩固中</text><text><i class="dot weak"></i>薄弱</text><text><i class="dot not-started"></i>无有效判定</text></view>
        <view v-if="!knowledgeRows.length" class="empty">暂无可形成的知识点数据</view>
        <view v-for="node in knowledgeRows" :key="`${node.id}-${node.depth}`" class="knowledge-row" :class="['knowledge-' + node.type, node.mastery || '']" :style="{ paddingLeft: `${node.depth * 26 + 18}px` }">
          <view class="knowledge-name">
            <text v-if="node.type !== 'knowledge'" class="tree-mark">{{ node.type === 'subject' ? '◆' : '└' }}</text>
            <text v-else :class="['tree-mark', 'mastery-mark-' + (node.mastery || 'not_started')]">●</text>
            <text>{{ node.name }}</text>
          </view>
          <view v-if="node.type === 'knowledge'" class="knowledge-metrics">
            <text>练习 {{ node.attempt }} 次</text>
            <text>正确率 {{ numberValue(node.accuracy) }}%</text>
            <text class="mastery-text">{{ masteryLabel(node.mastery) }}</text>
            <text>最近 {{ formatDateTime(node.last_practiced_at) }}</text>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'
import { formatDateOnly, formatDateTime } from '@/utils/display-format'

const classId = ref('')
const studentId = ref('')
const routeMissionId = ref('')
const loading = ref(true)
const errorMessage = ref('')
const activeTab = ref<'history' | 'knowledge'>('history')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const classInfo = ref<any>({})
const student = ref<any>({})
const summary = ref<any>({})
const missions = ref<any[]>([])
const knowledgeGraph = ref<any>({ tree: [], items: [] })
const expandedMissions = ref<Record<string, boolean>>({})
const expandedQuestions = ref<Record<string, boolean>>({})

const knowledgeRows = computed(() => {
  const rows: any[] = []
  function visit(nodes: any[], depth = 0) {
    for (const node of nodes || []) {
      rows.push({ ...node, depth })
      if (Array.isArray(node.children)) visit(node.children, depth + 1)
    }
  }
  visit(Array.isArray(knowledgeGraph.value.tree) ? knowledgeGraph.value.tree : [])
  return rows
})

onLoad((options: any) => {
  classId.value = String(options?.classId || '').trim()
  studentId.value = String(options?.studentId || '').trim()
  routeMissionId.value = String(options?.missionId || '').trim()
})

onMounted(() => {
  if (!classId.value || !studentId.value) {
    errorMessage.value = '缺少班级或学生信息'
    loading.value = false
    return
  }
  loadStats(1)
})

async function loadStats(targetPage: number) {
  loading.value = true
  try {
    const params: any = { page: targetPage, page_size: pageSize }
    if (targetPage === 1 && routeMissionId.value) params.mission_id = routeMissionId.value
    const response: any = await classApi.studentLearningStats(classId.value, studentId.value, params)
    if (response?.code !== undefined && response.code !== 0) throw new Error(response.message || '加载学生学情失败')
    const data = response?.data || {}
    classInfo.value = data.class || {}
    student.value = data.student || {}
    summary.value = data.summary || {}
    missions.value = Array.isArray(data.missions) ? data.missions : []
    knowledgeGraph.value = data.knowledge_graph || { tree: [], items: [] }
    total.value = Number(response?.meta?.total || data.meta?.total || missions.value.length || 0)
    page.value = targetPage
    const missionKey = routeMissionId.value || missions.value[0]?.mission_id
    if (missionKey) expandedMissions.value[missionKey] = true
  } catch (error: any) {
    console.error('加载学生学情失败:', error)
    errorMessage.value = error?.message || '加载学生学情失败'
  } finally {
    loading.value = false
  }
}

function changePage(targetPage: number) {
  if (targetPage < 1 || targetPage * pageSize - pageSize >= total.value) return
  loadStats(targetPage)
}

function missionKey(missionId: string) {
  return String(missionId || '')
}
function questionKey(missionId: string, questionId: string) {
  return `${missionKey(missionId)}:${String(questionId || '')}`
}
function toggleMission(missionId: string) {
  const key = missionKey(missionId)
  expandedMissions.value[key] = !expandedMissions.value[key]
}
function isMissionExpanded(missionId: string) {
  return expandedMissions.value[missionKey(missionId)] === true
}
function toggleQuestion(missionId: string, questionId: string) {
  const key = questionKey(missionId, questionId)
  expandedQuestions.value[key] = !expandedQuestions.value[key]
}
function isQuestionExpanded(missionId: string, questionId: string) {
  return expandedQuestions.value[questionKey(missionId, questionId)] === true
}
function numberValue(value: any) {
  const number = Number(value || 0)
  return Number.isInteger(number) ? String(number) : number.toFixed(2)
}
function statusLabel(status?: string) {
  return ({
    correct: '正确', wrong: '错误', pending: '待批改', unanswered: '未作答',
    mastered: '已掌握', reviewing: '巩固中', weak: '薄弱',
    not_started: '无有效判定', '已批改': '已批改', '已提交': '已提交',
    '进行中': '进行中', '未开始': '未开始',
  } as Record<string, string>)[status || ''] || status || '未知'
}
function statusClass(status?: string) {
  return 'status-' + (status || 'unanswered')
}
function masteryLabel(status?: string) {
  return ({ mastered: '已掌握', reviewing: '巩固中', weak: '薄弱', not_started: '无有效判定' } as Record<string, string>)[status || ''] || '无有效判定'
}
function goBack() {
  if (getCurrentPages().length > 1) uni.navigateBack()
  else uni.redirectTo({ url: '/pages/teacher/layout?section=learning-stats' })
}
</script>

<style scoped>
.stats-page { min-height: 100vh; padding: 30rpx 40rpx; box-sizing: border-box; background: #f0f2f5; }
.state, .empty { padding: 100rpx 20rpx; text-align: center; color: #909399; }.error { color: #f56c6c; }
.page-header { display: flex; align-items: center; gap: 24rpx; margin-bottom: 24rpx; }.back-btn { margin: 0; color: #409eff; background: #fff; border: 1px solid #dcdfe6; }.student-title { display: flex; align-items: baseline; gap: 18rpx; }.page-title { color: #303133; font-size: 38rpx; font-weight: 700; }.class-name { color: #909399; font-size: 25rpx; }
.summary-card { display: flex; flex-wrap: wrap; margin-bottom: 24rpx; padding: 26rpx 12rpx; background: #fff; border-radius: 12rpx; }.summary-item { flex: 1; min-width: 150rpx; padding: 0 10rpx; text-align: center; border-right: 1px solid #ebeef5; }.summary-item:last-child { border-right: 0; }.summary-label { display: block; color: #909399; font-size: 23rpx; }.summary-value { display: block; margin-top: 8rpx; color: #303133; font-size: 32rpx; font-weight: 700; }.summary-value.correct, .correct { color: #67c23a; }.summary-value.pending, .pending { color: #e6a23c; }.summary-time { display: block; margin-top: 12rpx; color: #606266; font-size: 20rpx; }
.tabs { display: flex; gap: 30rpx; margin-bottom: 18rpx; padding: 0 8rpx; }.tab { padding: 12rpx 6rpx; color: #909399; font-size: 28rpx; cursor: pointer; }.tab.active { color: #409eff; font-weight: 700; border-bottom: 4rpx solid #409eff; }.content-card { padding: 24rpx; background: #fff; border-radius: 12rpx; }.section-title { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; color: #303133; font-size: 30rpx; font-weight: 700; }.hint { color: #909399; font-size: 23rpx; font-weight: 400; }
.mission-card { margin-bottom: 18rpx; border: 1px solid #ebeef5; border-radius: 10rpx; }.mission-header { display: flex; justify-content: space-between; align-items: center; gap: 20rpx; padding: 20rpx; cursor: pointer; }.mission-main { min-width: 0; }.mission-name { display: block; overflow: hidden; color: #303133; font-size: 28rpx; font-weight: 700; white-space: nowrap; text-overflow: ellipsis; }.mission-meta, .mission-summary { color: #909399; font-size: 22rpx; }.mission-meta { display: block; margin-top: 8rpx; }.mission-result { display: flex; align-items: center; gap: 14rpx; flex-shrink: 0; }.mission-status { padding: 4rpx 10rpx; border-radius: 18rpx; font-size: 21rpx; }.mission-rate { color: #67c23a; font-size: 27rpx; font-weight: 700; }.expand-icon { color: #409eff; font-size: 22rpx; }.mission-summary { display: flex; flex-wrap: wrap; gap: 18rpx; padding: 0 20rpx 18rpx; }
.question-list { padding: 0 18rpx 18rpx; }.question-card { padding: 16rpx; margin-top: 12rpx; background: #f8fafc; border-radius: 8rpx; }.question-header { display: flex; align-items: center; gap: 12rpx; }.question-no { color: #409eff; font-size: 25rpx; font-weight: 700; }.source-no { color: #909399; font-size: 21rpx; }.question-status { margin-left: auto; font-size: 21rpx; }.question-stem { display: block; margin-top: 10rpx; color: #303133; font-size: 24rpx; line-height: 1.55; }.question-missing { display: block; margin-top: 10rpx; color: #909399; font-size: 23rpx; }.answer-row { display: flex; flex-wrap: wrap; gap: 18rpx; margin-top: 12rpx; color: #606266; font-size: 22rpx; }.history-toggle { margin-top: 12rpx; color: #409eff; font-size: 22rpx; }.attempt-list { margin-top: 12rpx; padding-top: 10rpx; border-top: 1px solid #ebeef5; }.attempt-row { display: flex; flex-wrap: wrap; gap: 18rpx; padding: 10rpx 0; color: #606266; font-size: 21rpx; border-bottom: 1px dashed #ebeef5; }.attempt-row:last-child { border-bottom: 0; }.wrong, .status-wrong { color: #f56c6c; }.status-correct { color: #67c23a; }.status-pending { color: #e6a23c; }.status-unanswered, .status-not_started { color: #909399; }.pagination { display: flex; justify-content: center; align-items: center; gap: 18rpx; margin-top: 20rpx; color: #606266; font-size: 23rpx; }.pagination button { margin: 0; color: #409eff; background: #ecf5ff; border: 1px solid #b3d8ff; }
.legend { display: flex; flex-wrap: wrap; gap: 24rpx; margin-bottom: 20rpx; color: #606266; font-size: 22rpx; }.dot { display: inline-block; width: 14rpx; height: 14rpx; margin-right: 6rpx; border-radius: 50%; }.dot.mastered { background: #67c23a; }.dot.reviewing { background: #e6a23c; }.dot.weak { background: #f56c6c; }.dot.not-started { background: #909399; }.knowledge-row { display: flex; justify-content: space-between; align-items: center; gap: 20rpx; min-height: 64rpx; padding-top: 8rpx; padding-right: 18rpx; padding-bottom: 8rpx; border-bottom: 1px solid #f2f6fc; box-sizing: border-box; }.knowledge-subject { color: #303133; font-weight: 700; }.knowledge-stage, .knowledge-grade { color: #606266; }.knowledge-knowledge { color: #303133; }.knowledge-name { display: flex; align-items: center; min-width: 0; gap: 10rpx; }.tree-mark { color: #b3d8ff; font-size: 18rpx; }.mastery-mark-mastered { color: #67c23a; }.mastery-mark-reviewing { color: #e6a23c; }.mastery-mark-weak { color: #f56c6c; }.mastery-mark-not_started { color: #909399; }.knowledge-metrics { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 16rpx; color: #909399; font-size: 21rpx; }.mastery-text { color: inherit; }.knowledge-mastered .mastery-text { color: #67c23a; }.knowledge-reviewing .mastery-text { color: #e6a23c; }.knowledge-weak .mastery-text { color: #f56c6c; }
@media screen and (max-width: 700px) { .stats-page { padding: 20rpx; }.page-header { align-items: flex-start; flex-wrap: wrap; }.student-title { flex-direction: column; align-items: flex-start; gap: 6rpx; }.summary-item { flex: 0 0 33.333%; min-width: 0; margin-bottom: 20rpx; }.summary-item:nth-child(3), .summary-item:nth-child(6) { border-right: 0; }.mission-header { align-items: flex-start; flex-direction: column; }.mission-result { width: 100%; justify-content: space-between; }.knowledge-row { align-items: flex-start; flex-direction: column; gap: 6rpx; }.knowledge-metrics { justify-content: flex-start; padding-left: 28rpx; } }
</style>
