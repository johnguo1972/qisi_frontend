<template>
  <view class="container">
    <TeacherSidebar activeItem="bank" />

    <!-- Main content -->
    <view class="main">
      <!-- Paper selector -->
      <view class="paper-selector">
        <text class="label">试卷：</text>
        <picker @change="onPaperChange" :value="paperIndex" :range="paperNames">
          <view class="picker-value">{{ currentPaperName || '请选择试卷' }}</view>
        </picker>
      </view>

      <!-- Filter bar -->
      <view class="filter-bar">
        <text class="filter-label">状态：</text>
        <view
          v-for="opt in filterOptions"
          :key="opt.value"
          :class="['filter-chip', { active: filter === opt.value }]"
          @click="setFilter(opt.value)"
        >
          {{ opt.label }}
        </view>
        <view v-if="selectedIds.length > 0" class="batch-actions">
          <text class="batch-count">已选 {{ selectedIds.length }}</text>
          <button size="mini" @click="selectAll" v-if="selectedIds.length < questions.length">全选</button>
          <button size="mini" @click="clearSelect">取消</button>
          <button size="mini" type="primary" @click="handleBatchAiProcess">批量AI处理</button>
          <button size="mini" type="warn" @click="handleBatchDelete">批量删除</button>
        </view>
      </view>

      <!-- Question list -->
      <view v-if="loading" class="loading">加载中...</view>
      <view v-else-if="questions.length === 0" class="empty">暂无题目{{ currentPaperName ? '' : '，请先选择试卷' }}</view>
      <view v-else class="question-list">
        <view v-for="q in questions" :key="q.id" class="question-row" :class="{ 'row-selected': selectedIds.includes(q.id) }">
          <view class="row-checkbox" @click.stop="toggleSelect(q.id)">
            <text v-if="selectedIds.includes(q.id)" class="check-mark">✓</text>
          </view>
          <view class="question-info" @click="navigateTo(`/pages/teacher/question-edit?id=${q.id}`)">
            <text class="question-no">{{ q.question_no }}</text>
            <text class="question-type">{{ typeLabel(q.question_type) }}</text>
            <text class="question-stem">{{ truncate(q.stem, 60) }}</text>
          </view>
          <view class="q-meta">
            <text class="meta-chip" title="难度">难度{{ q.difficulty || '-' }}</text>
            <text class="meta-chip" title="知识点数">知识点{{ q.knowledge_points_count ?? 0 }}</text>
          </view>
          <view class="ai-status">
            <text :class="['badge', q.ai_answer_a ? 'done' : '']" title="A模式">A</text>
            <text :class="['badge', q.ai_answer_b ? 'done' : '']" title="B模式">B</text>
            <text :class="['badge', q.ai_answer_c ? 'done' : '']" title="C模式">C</text>
          </view>
          <view class="actions">
            <button size="mini" @click="navigateTo(`/pages/teacher/question-edit?id=${q.id}`)">编辑</button>
            <button size="mini" type="primary" @click="handleAiProcess(q.id)">AI处理</button>
            <button size="mini" type="success" @click="showAiConfirmModal(q)">AI确认</button>
            <button size="mini" type="warn" @click="handleDeleteQuestion(q)">删除</button>
          </view>
        </view>
      </view>
    </view>

    <!-- AI answer confirmation modal -->
    <view v-if="aiConfirmVisible" class="modal-overlay" @click.self="aiConfirmVisible = false">
      <view class="modal">
        <text class="modal-title">AI 答案确认</text>
        <view class="modal-columns">
          <view class="column">
            <text class="column-title">A 模式 - 详细解答</text>
            <scroll-view class="column-content" scroll-y>
              <text>{{ formatAiAnswer(currentQuestion?.ai_answer_a) }}</text>
            </scroll-view>
            <view class="column-actions">
              <button size="mini" type="primary" @click="handleModeAiProcess('A')" :disabled="modeAiState.loading && modeAiState.mode === 'A'">
                {{ modeAiState.loading && modeAiState.mode === 'A' ? modeAiState.label : 'AI处理' }}
              </button>
              <button size="mini" type="success" @click="doConfirmAiAnswer('a')">确认</button>
            </view>
          </view>
          <view class="column">
            <text class="column-title">B 模式 - 苏格拉底多选</text>
            <scroll-view class="column-content" scroll-y>
              <text>{{ formatAiAnswer(currentQuestion?.ai_answer_b) }}</text>
            </scroll-view>
            <view class="column-actions">
              <button size="mini" type="primary" @click="handleModeAiProcess('B')" :disabled="modeAiState.loading && modeAiState.mode === 'B'">
                {{ modeAiState.loading && modeAiState.mode === 'B' ? modeAiState.label : 'AI处理' }}
              </button>
              <button size="mini" type="success" @click="doConfirmAiAnswer('b')">确认</button>
            </view>
          </view>
          <view class="column">
            <text class="column-title">C 模式 - 苏格拉底开放式</text>
            <scroll-view class="column-content" scroll-y>
              <text>{{ formatAiAnswer(currentQuestion?.ai_answer_c) }}</text>
            </scroll-view>
            <view class="column-actions">
              <button size="mini" type="primary" @click="handleModeAiProcess('C')" :disabled="modeAiState.loading && modeAiState.mode === 'C'">
                {{ modeAiState.loading && modeAiState.mode === 'C' ? modeAiState.label : 'AI处理' }}
              </button>
              <button size="mini" type="success" @click="doConfirmAiAnswer('c')">确认</button>
            </view>
          </view>
        </view>
        <view class="modal-footer">
          <button size="mini" @click="aiConfirmVisible = false">关闭</button>
        </view>
      </view>
    </view>

    <!-- AI处理已改为后台静默轮询：启动后不阻塞界面，完成时弹 toast 并刷新列表 -->
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  getReviewPapers,
  getPaperQuestions,
  confirmAiAnswer,
  aiProcessQuestion,
  aiProcessSingleMode,
  getAiTaskStatus,
} from '@/api/questions'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

interface Question {
  id: number
  question_no: string
  question_type: string
  stem: string
  review_status: string
  ai_answer_a: any
  ai_answer_b: any
  ai_answer_c: any
  difficulty: number
  knowledge_points_count: number
}

interface Paper {
  id: number
  paper_code: string
  title?: string
}

const questions = ref<Question[]>([])
const selectedIds = ref<number[]>([])
const papers = ref<Paper[]>([])
const paperIndex = ref(0)
const loading = ref(false)
const filter = ref('all')

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '需审阅', value: 'need_review' },
  { label: '已确认', value: 'confirmed' },
  { label: '已拒绝', value: 'rejected' },
]

const paperNames = computed(() => papers.value.map(p => p.paper_code || `#${p.id}`))
const currentPaperName = computed(() => papers.value[paperIndex.value]?.paper_code || '')
const currentPaperId = computed(() => papers.value[paperIndex.value]?.id)

// AI confirm modal
const aiConfirmVisible = ref(false)
const currentQuestion = ref<Question | null>(null)

// AI 后台轮询（支持多任务并行）：{ taskId, timer }
const aiPollTimers: Array<{ taskId: string; timer: ReturnType<typeof setInterval> }> = []

// 单模式 AI 处理轮询：{ mode, taskId, timer, loading }
const modeAiState = ref<{
  mode: 'A' | 'B' | 'C' | null;
  taskId: string | null;
  loading: boolean;
  label: string;
  timer: ReturnType<typeof setInterval> | null;
}>({ mode: null, taskId: null, loading: false, label: '', timer: null })

function navigateTo(url: string) {
  uni.navigateTo({ url })
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    single_choice: '单选', multiple_choice: '多选', fill_blank: '填空',
    short_answer: '简答', essay: '论述', true_false: '判断',
    computation: '计算', proof: '证明',
  }
  return map[type] || type
}

function truncate(str: string, len: number): string {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function formatAiAnswer(answer: any): string {
  if (!answer) return '未生成'
  if (typeof answer === 'string') return answer
  try {
    if (answer.steps) {
      // Mode A: structured steps
      return answer.steps.map((s: any) => {
        const num = s.step_number ?? s.step ?? '?'
        const desc = s.description ? `（${s.description}）\n` : ''
        return `步骤${num}: ${desc}${s.content || ''}`
      }).join('\n\n') +
        `\n\n最终答案: ${answer.final_answer || '-'}` +
        `\n\n总结: ${answer.summary || ''}`
    }
    if (answer.questions) {
      // Mode B/C: guided questions (options can be dict or array)
      return answer.questions.map((q: any, i: number) => {
        let optionsText = ''
        if (q.options) {
          if (Array.isArray(q.options)) {
            optionsText = '选项: ' + q.options.join('\n') + '\n'
          } else {
            optionsText = Object.entries(q.options).map(([k, v]) => `${k}. ${v}`).join('\n') + '\n'
          }
        }
        return `问题${i + 1}: ${q.question}\n${optionsText}${q.correct_option ? '正确答案: ' + q.correct_option + '\n' : ''}${q.reference_answer ? '参考答案: ' + q.reference_answer + '\n' : ''}${q.analysis ? '解析: ' + q.analysis + '\n' : ''}`
      }).join('\n\n') +
        `\n\n最终答案: ${answer.final_answer || '-'}` +
        `\n\n总结: ${answer.summary || ''}`
    }
    return JSON.stringify(answer, null, 2)
  } catch { return String(answer) }
}

function handleDeleteQuestion(q: Question) {
  uni.showModal({ title: '确认删除', content: `确定删除题目「${q.question_no}」？此操作不可恢复。`, success: async (res) => {
    if (!res.confirm) return;
    try {
      const { del } = await import('@/utils/request');
      await del(`/review/questions/${q.id}/delete/`);
      uni.showToast({ title: '删除成功', icon: 'success' });
      loadQuestions();
    } catch (e: any) {
      uni.showToast({ title: e?.message || '删除失败', icon: 'none' });
    }
  } });
}
function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}
function selectAll() { selectedIds.value = questions.value.map(q => q.id) }
function clearSelect() { selectedIds.value = [] }
function handleBatchDelete() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  uni.showModal({ title: '批量删除', content: `确定删除选中的 ${ids.length} 道题？此操作不可恢复。`, success: async (res) => {
    if (!res.confirm) return
    uni.showLoading({ title: '删除中...' })
    try {
      const { del } = await import('@/utils/request')
      for (const id of ids) { await del(`/review/questions/${id}/delete/`) }
      uni.hideLoading()
      uni.showToast({ title: `已删除 ${ids.length} 题`, icon: 'success' })
    } catch (e: any) {
      uni.hideLoading()
      uni.showToast({ title: e?.message || '部分删除失败', icon: 'none' })
    }
    selectedIds.value = []
    loadQuestions()
  } })
}
function handleBatchAiProcess() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  uni.showToast({ title: `已开始 ${ids.length} 题AI处理，可继续操作`, icon: 'none', duration: 2000 })
  for (const id of ids) { handleAiProcess(id) }
  selectedIds.value = []
}
function setFilter(value: string) {
  filter.value = value
  loadQuestions()
}

function onPaperChange(e: any) {
  paperIndex.value = e.detail.value
  loadQuestions()
}

async function loadPapers() {
  try {
    const res: any = await getReviewPapers()
    const list = res.data?.results || res.data || []
    papers.value = Array.isArray(list) ? list : []
    if (papers.value.length > 0) loadQuestions()
  } catch (e) {
    console.error('加载试卷列表失败:', e)
  }
}

async function loadQuestions() {
  if (!currentPaperId.value) return
  loading.value = true
  try {
    const res: any = await getPaperQuestions(currentPaperId.value, filter.value)
    let list = res.data?.results || res.data || []
    questions.value = Array.isArray(list) ? list : []
  } catch (e) {
    console.error('加载题目列表失败:', e)
  } finally {
    loading.value = false
  }
}

function showAiConfirmModal(q: Question) {
  currentQuestion.value = q
  aiConfirmVisible.value = true
}

async function doConfirmAiAnswer(mode: string) {
  if (!currentQuestion.value) return
  try {
    await confirmAiAnswer(currentQuestion.value.id, mode)
    uni.showToast({ title: `${mode.toUpperCase()} 已确认`, icon: 'success' })
    loadQuestions()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '确认失败', icon: 'none' })
  }
}

/**
 * 单模式 AI 处理（针对弹窗中某个模式）
 */
async function handleModeAiProcess(mode: string) {
  if (!currentQuestion.value) return
  const modeKey = mode.toLowerCase()
  const state = modeAiState.value

  // 防止重复点击
  if (state.loading && state.mode === mode) return

  state.mode = mode as 'A' | 'B' | 'C'
  state.loading = true
  state.label = '准备中...'
  state.taskId = null

  try {
    const res: any = await aiProcessSingleMode(currentQuestion.value.id, mode)
    const taskId = res.data?.task_id
    if (!taskId) throw new Error('No task ID')
    state.taskId = taskId
    state.label = '处理中...'

    state.timer = setInterval(async () => {
      try {
        const statusRes: any = await getAiTaskStatus(taskId)
        if (statusRes.success === false || !statusRes.data) {
          clearInterval(state.timer!)
          state.timer = null
          state.loading = false
          uni.showToast({ title: `任务失效（${mode}模式）`, icon: 'none' })
          loadQuestions()
          return
        }
        const data = statusRes.data
        state.label = data.step_label || '处理中...'

        if (data.status === 'complete' || data.status === 'failed') {
          clearInterval(state.timer!)
          state.timer = null
          state.loading = false
          if (data.status === 'complete') {
            uni.showToast({ title: `${mode}模式处理完成`, icon: 'success' })
          } else {
            uni.showToast({ title: data.error || `${mode}模式处理失败`, icon: 'none' })
          }
          loadQuestions()
        }
      } catch (e) { /* silent */ }
    }, 2000)
  } catch (e: any) {
    state.loading = false
    state.mode = null
    uni.showToast({ title: e?.message || '启动失败', icon: 'none' })
  }
}

async function handleAiProcess(questionId: number) {
  uni.showToast({ title: `已开始AI处理（题${questionId}），可继续其他操作`, icon: 'none', duration: 2000 })
  try {
    const res: any = await aiProcessQuestion(questionId)
    const taskId = res.data?.task_id
    if (!taskId) throw new Error('No task ID')
    const timer = setInterval(async () => {
      try {
        const statusRes: any = await getAiTaskStatus(taskId)
        if (statusRes.success === false || !statusRes.data) {
          clearInterval(timer)
          const idx = aiPollTimers.findIndex(t => t.taskId === taskId)
          if (idx >= 0) aiPollTimers.splice(idx, 1)
          uni.showToast({ title: `任务进度已失效（题${questionId}），请重新AI处理`, icon: 'none' })
          loadQuestions()
          return
        }
        const data = statusRes.data
        if (data.status === 'complete' || data.status === 'failed' || data.status === 'partial') {
          clearInterval(timer)
          const idx = aiPollTimers.findIndex(t => t.taskId === taskId)
          if (idx >= 0) aiPollTimers.splice(idx, 1)
          if (data.status === 'complete') {
            uni.showToast({ title: `AI处理完成（题${questionId}）`, icon: 'success' })
          } else if (data.status === 'partial') {
            uni.showToast({ title: `AI处理完成，部分步骤失败（题${questionId}）`, icon: 'none' })
          } else {
            uni.showToast({ title: data.error || `AI处理失败（题${questionId}）`, icon: 'none' })
          }
          loadQuestions()
        }
      } catch (e) { /* silent */ }
    }, 3000)
    aiPollTimers.push({ taskId, timer })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '启动失败', icon: 'none' })
  }
}

onMounted(() => {
  loadPapers()
})
onUnmounted(() => {
  aiPollTimers.forEach(t => clearInterval(t.timer)); aiPollTimers.length = 0
  if (modeAiState.value.timer) clearInterval(modeAiState.value.timer)
})

// Accept paper_id from URL query and auto-select
onLoad((options: any) => {
  if (options && options.paper_id) {
    const targetId = parseInt(options.paper_id)
    const unwatch = watch(papers, (list) => {
      if (list.length > 0) {
        const idx = list.findIndex(p => p.id === targetId)
        if (idx >= 0) {
          paperIndex.value = idx
          loadQuestions()
        }
        unwatch()
      }
    }, { immediate: false })
  }
})
</script>

<style scoped>
.container { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 240px; flex: 1; padding: 24px; overflow-y: auto; }
.paper-selector { display: flex; align-items: center; margin-bottom: 12px; background: #fff; padding: 12px 16px; border-radius: 8px; }
.paper-selector .label { font-size: 14px; color: #606266; margin-right: 8px; }
.picker-value { font-size: 14px; color: #409eff; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
.filter-label { font-size: 14px; color: #606266; }
.filter-chip { padding: 4px 12px; border-radius: 12px; font-size: 12px; background: #f0f0f0; cursor: pointer; }
.filter-chip.active { background: #409eff; color: #fff; }
.question-row { display: flex; align-items: center; padding: 12px 16px; background: #fff; border: 1px solid #ebeef5; border-radius: 4px; margin-bottom: 8px; }
.question-info { flex: 1; display: flex; gap: 8px; align-items: center; cursor: pointer; }
.question-no { font-weight: 500; color: #303133; min-width: 40px; }
.question-type { font-size: 11px; padding: 2px 6px; background: #f0f0f0; border-radius: 4px; color: #909399; }
.question-stem { color: #606266; font-size: 13px; }
.ai-status { display: flex; gap: 4px; margin: 0 12px; }
.badge { width: 20px; height: 20px; border-radius: 50%; background: #f0f0f0; color: #909399; font-size: 10px; display: flex; align-items: center; justify-content: center; }
.badge.done { background: #67c23a; color: #fff; }
.actions { display: flex; gap: 4px; }
.batch-actions { display: flex; gap: 6px; align-items: center; margin-left: auto; }
.batch-count { font-size: 12px; color: #409eff; margin-right: 2px; white-space: nowrap; }
.row-checkbox { width: 18px; height: 18px; border: 1.5px solid #c0c4cc; border-radius: 3px; margin-right: 10px; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
.row-checkbox .check-mark { color: #fff; font-size: 13px; line-height: 1; }
.question-row.row-selected { background: #ecf5ff; border-color: #409eff; }
.question-row.row-selected .row-checkbox { background: #409eff; border-color: #409eff; }
.q-meta { display: flex; gap: 4px; margin: 0 10px; flex-shrink: 0; }
.meta-chip { font-size: 11px; padding: 2px 6px; background: #f4f4f5; border-radius: 4px; color: #67c23a; white-space: nowrap; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 24px; max-width: 90vw; width: 800px; max-height: 80vh; overflow-y: auto; }
.modal-title { font-size: 16px; font-weight: 500; margin-bottom: 16px; display: block; }
.modal-columns { display: flex; gap: 16px; }
.column { flex: 1; }
.column-title { font-size: 13px; font-weight: 500; color: #409eff; margin-bottom: 8px; display: block; }
.column-content { font-size: 12px; color: #606266; max-height: 500px; margin-bottom: 8px; white-space: pre-wrap; }
.column-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.column-actions button { flex: 1; }
.modal-footer { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
.loading, .empty { text-align: center; color: #909399; padding: 40px 0; }
</style>