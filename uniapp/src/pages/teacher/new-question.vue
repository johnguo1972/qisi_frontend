<template>
  <view class="container">

    <!-- Main: knowledge tree + question list -->
    <view class="main">
      <!-- Left: Knowledge tree (4-level: grade → semester → chapter → KP) -->
      <view class="knowledge-tree">
        <text class="tree-title">知识树</text>
        <view v-if="treeLoading" class="loading">加载中...</view>
        <view v-else class="tree-content">
          <view v-for="grade in tree" :key="grade.name" class="tree-grade">
            <view class="tree-node" @click="grade.expanded = !grade.expanded">
              <text class="arrow">{{ grade.expanded ? '▼' : '▶' }}</text>
              <text class="tree-label">{{ grade.name }}</text>
              <text v-if="grade.question_count" class="kp-count">({{ grade.question_count }})</text>
            </view>
            <view v-if="grade.expanded" class="tree-children">
              <view v-for="sem in grade.semesters" :key="sem.name" class="tree-semester">
                <view class="tree-node" @click="sem.expanded = !sem.expanded">
                  <text class="arrow">{{ sem.expanded ? '▼' : '▶' }}</text>
                  <text class="tree-label">{{ sem.name }}</text>
                  <text v-if="sem.question_count" class="kp-count">({{ sem.question_count }})</text>
                </view>
                <view v-if="sem.expanded" class="tree-children">
                  <view v-for="ch in sem.chapters" :key="ch.name" class="tree-chapter">
                    <view class="tree-node" @click="ch.expanded = !ch.expanded">
                      <text class="arrow">{{ ch.expanded ? '▼' : '▶' }}</text>
                      <text class="tree-label">{{ ch.name }}</text>
                      <text v-if="ch.question_count" class="kp-count">({{ ch.question_count }})</text>
                    </view>
                    <view v-if="ch.expanded" class="tree-children">
                      <view v-for="kp in ch.knowledge_points" :key="kp.id"
                            :class="['tree-kp', {active: selectedKP === kp.id}]"
                            @click.stop="selectKP(kp.id)">
                        <text class="kp-name">{{ kp.name }}</text>
                        <text v-if="kp.question_count" class="kp-count">({{ kp.question_count }})</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Right: Question list -->
      <view class="question-panel">
        <view class="panel-header">
          <text class="panel-title">题目清单</text>
          <button class="btn-add" @click="goPhotoUpload">+ 增加新题</button>
        </view>

        <!-- Tabs -->
        <view class="tab-bar">
          <view :class="['tab', {active: activeTab === 'pending'}]" @click="activeTab='pending'">待审核处理</view>
          <view :class="['tab', {active: activeTab === 'confirmed'}]" @click="activeTab='confirmed'">已审核处理</view>
        </view>

        <!-- Question table -->
        <view v-if="loading" class="loading">加载中...</view>
        <view v-else-if="questions.length === 0" class="empty">暂无题目</view>
        <view v-else class="question-table">
          <view class="table-header">
            <text class="col-stem">题干</text>
            <text class="col-diff">难度</text>
            <text class="col-kp">知识点</text>
            <text class="col-confirm">内容确认</text>
            <text class="col-ai">AI答案</text>
            <text class="col-actions">操作</text>
          </view>
          <view v-for="q in questions" :key="q.id" class="table-row">
            <text class="col-stem" @click="goEdit(q.id)">{{ q.stem_preview }}</text>
            <text :class="['col-diff', 'diff-' + q.difficulty]">L{{ q.difficulty }}</text>
            <text class="col-kp">{{ q.knowledge_points_count }}</text>
            <text :class="['col-confirm', q.review_status === 'confirmed' ? 'confirmed' : 'pending']">
              {{ q.review_status === 'confirmed' ? '✓' : '待审核' }}
            </text>
            <view class="col-ai">
              <text :class="['badge', q.ai_answer_a_confirmed ? 'done' : q.ai_answer_a ? 'blank' : '']">A</text>
              <text :class="['badge', q.ai_answer_b_confirmed ? 'done' : q.ai_answer_b ? 'blank' : '']">B</text>
              <text :class="['badge', q.ai_answer_c_confirmed ? 'done' : q.ai_answer_c ? 'blank' : '']">C</text>
            </view>
            <view class="col-actions">
              <button size="mini" @click="goEdit(q.id)">内容编辑</button>
              <button size="mini" type="primary" @click="handleAiProcess(q.id)">AI处理</button>
              <button size="mini" type="success" @click="showAiConfirm(q)">AI答案确认</button>
              <button size="mini" type="warn" @click="handleDelete(q.id)">删除</button>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- AI confirm modal -->
    <view v-if="aiConfirmVisible" class="modal-overlay" @click.self="aiConfirmVisible=false">
      <view class="modal">
        <text class="modal-title">AI 答案确认</text>
        <view class="modal-columns">
          <view class="column" v-for="mode in modes" :key="mode">
            <text class="column-title">{{ mode.toUpperCase() }} 模式</text>
            <scroll-view class="column-content" scroll-y>
              <rich-text :nodes="aiAnswerHtml[mode]"></rich-text>
            </scroll-view>
            <button size="mini" type="success" @click="doConfirmAiAnswer(mode)">确认</button>
          </view>
        </view>
        <view class="modal-footer">
          <button size="mini" @click="aiConfirmVisible=false">关闭</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { photoListQuestions, confirmAiAnswer as apiConfirmAiAnswer, aiProcessQuestion, getAiTaskStatus, aiProcessSingleMode } from '@/api/questions'
import { knowledgeApi } from '@/api/knowledge'
import { useUserStore } from '@/store/index.ts'
import { renderWithKatex } from '@/utils/katex-renderer'

const userStore = useUserStore()

interface Question {
  id: number
  system_id: string
  question_no: string
  question_type: string
  stem_preview: string
  difficulty: number
  knowledge_points_count: number
  review_status: string
  ai_answer_a: boolean
  ai_answer_b: boolean
  ai_answer_c: boolean
  ai_answer_a_confirmed: boolean
  ai_answer_b_confirmed: boolean
  ai_answer_c_confirmed: boolean
}

interface TreeNode {
  name: string
  expanded?: boolean
  question_count?: number
  semesters?: SemesterNode[]
}
interface SemesterNode { name: string; expanded?: boolean; question_count?: number; chapters: ChapterNode[] }
interface ChapterNode { name: string; expanded?: boolean; question_count?: number; knowledge_points: KPNode[] }
interface KPNode { id: number; name: string; question_count: number }

const activeTab = ref('pending')
const questions = ref<Question[]>([])
const loading = ref(false)
const treeLoading = ref(false)
const selectedKP = ref<number | null>(null)
const tree = ref<TreeNode[]>([])
const modes = ['a', 'b', 'c']

const aiPollTimers: Array<{ taskId: string; timer: ReturnType<typeof setInterval> }> = []

const aiConfirmVisible = ref(false)
const currentQuestion = ref<Question | null>(null)
const aiAnswerHtml = ref<Record<string, string>>({ a: '', b: '', c: '' })

function navigateTo(url: string) { uni.navigateTo({ url }) }
function goPhotoUpload() { uni.navigateTo({ url: '/pages/teacher/photo-upload' }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }

function selectKP(id: number) { selectedKP.value = id; loadQuestions() }

async function loadQuestions() {
  loading.value = true
  try {
    const params: any = { review_status: activeTab.value === 'pending' ? 'need_review' : 'confirmed' }
    if (selectedKP.value) params.knowledge_point_id = selectedKP.value
    const res: any = await photoListQuestions(params)
    questions.value = (res.data || []) as Question[]
  } catch (e) {
    console.error('加载题目列表失败:', e)
    uni.showToast({ title: '加载题目列表失败，请检查网络', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function loadKnowledgeTree() {
  treeLoading.value = true
  try {
    const subject = userStore.userInfo?.subject || ''
    const res: any = await knowledgeApi.getTree({ subject })
    const grades = res.data?.grades || []
    tree.value = grades.map((g: any) => ({
      ...g,
      expanded: false,
      semesters: (g.semesters || []).map((s: any) => ({
        ...s,
        expanded: false,
        chapters: (s.chapters || []).map((c: any) => ({
          ...c,
          expanded: false,
        })),
      })),
    }))
  } catch (e) {
    console.error('加载知识树失败:', e)
    uni.showToast({ title: '加载知识树失败，请检查网络', icon: 'none' })
  } finally {
    treeLoading.value = false
  }
}

function formatAiAnswerText(val: any): string {
  if (!val) return '未生成'
  if (typeof val === 'string') return val
  try {
    const obj = typeof val === 'object' ? val : JSON.parse(val)
    if (obj.steps) {
      return obj.steps.map((s: any) => {
        const num = s.step_number ?? s.step ?? '?'
        return `步骤${num}: ${s.content || ''}`
      }).join('\n\n') + `\n\n最终答案: ${obj.final_answer || '-'}` + `\n\n总结: ${obj.summary || ''}`
    }
    if (obj.questions) {
      return obj.questions.map((q: any, i: number) => {
        let optionsText = ''
        if (q.options) {
          if (Array.isArray(q.options)) {
            optionsText = '选项: ' + q.options.join('\n') + '\n'
          } else {
            optionsText = Object.entries(q.options).map(([k, v]) => `${k}. ${v}`).join('\n') + '\n'
          }
        }
        return `问题${i + 1}: ${q.question}\n${optionsText}${q.correct_option ? '正确答案: ' + q.correct_option + '\n' : ''}${q.reference_answer ? '参考答案: ' + q.reference_answer + '\n' : ''}${q.analysis ? '解析: ' + q.analysis + '\n' : ''}`
      }).join('\n\n') + `\n\n最终答案: ${obj.final_answer || '-'}` + `\n\n总结: ${obj.summary || ''}`
    }
    return JSON.stringify(obj, null, 2).slice(0, 500)
  } catch { return String(val) }
}

async function showAiConfirm(q: Question) {
  currentQuestion.value = q
  aiConfirmVisible.value = true
  for (const mode of modes) {
    const val = (q as any)['ai_answer_' + mode]
    const text = formatAiAnswerText(val)
    aiAnswerHtml.value[mode] = await renderWithKatex(text)
  }
}

async function doConfirmAiAnswer(mode: string) {
  if (!currentQuestion.value) return
  try {
    await apiConfirmAiAnswer(currentQuestion.value.id, mode)
    uni.showToast({ title: mode.toUpperCase() + ' 已确认', icon: 'success' })
    aiConfirmVisible.value = false
    loadQuestions()
  } catch (e) {
    uni.showToast({ title: '确认失败', icon: 'none' })
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
    }, 2000)
    aiPollTimers.push({ taskId, timer })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '启动失败', icon: 'none' })
  }
}

async function handleDelete(questionId: number) {
  uni.showModal({
    title: '确认删除', content: '确定要删除这道题目吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const { post } = await import('@/utils/request')
          await post(`/review/questions/${questionId}/delete/`)
          uni.showToast({ title: '已删除', icon: 'success' })
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    }
  })
}

watch(activeTab, () => loadQuestions())

onMounted(() => {
  loadKnowledgeTree()
  loadQuestions()
})
onUnmounted(() => { aiPollTimers.forEach(t => clearInterval(t.timer)); aiPollTimers.length = 0 })
</script>

<style scoped>
.container { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 0; flex: 1; display: flex; gap: 16px; padding: 16px; overflow: hidden; }
.knowledge-tree { width: 240px; background: #fff; border-radius: 8px; padding: 16px; overflow-y: auto; flex-shrink: 0; }
.tree-title { font-size: 14px; font-weight: 500; color: #303133; margin-bottom: 12px; display: block; }
.tree-content .tree-node { padding: 4px 8px; cursor: pointer; font-size: 13px; color: #606266; display: flex; align-items: center; border-radius: 4px; }
.tree-content .tree-node:hover { background: #f5f7fa; }
.tree-content .arrow { margin-right: 4px; font-size: 10px; color: #909399; flex-shrink: 0; }
.tree-label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-children { padding-left: 12px; }
.tree-kp { padding: 4px 8px 4px 16px; cursor: pointer; font-size: 12px; color: #606266; display: flex; align-items: center; justify-content: space-between; border-radius: 4px; }
.tree-kp:hover { background: #f5f7fa; }
.tree-kp.active { color: #409eff; font-weight: 500; background: #ecf5ff; }
.kp-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kp-count { font-size: 10px; color: #909399; margin-left: 4px; flex-shrink: 0; }

.question-panel { flex: 1; background: #fff; border-radius: 8px; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; min-width: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.panel-title { font-size: 16px; font-weight: 500; color: #303133; }
.btn-add { background: #409eff; color: #fff; border: none; border-radius: 4px; padding: 6px 16px; font-size: 13px; cursor: pointer; }
.tab-bar { display: flex; gap: 0; margin-bottom: 12px; border-bottom: 1px solid #ebeef5; }
.tab { padding: 8px 20px; cursor: pointer; font-size: 13px; color: #606266; border-bottom: 2px solid transparent; }
.tab.active { color: #409eff; border-bottom-color: #409eff; }
.question-table { flex: 1; overflow-y: auto; }
.table-header { display: flex; align-items: center; padding: 8px 12px; background: #f5f7fa; font-size: 12px; color: #909399; font-weight: 500; }
.table-row { display: flex; align-items: center; padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.table-row:hover { background: #fafafa; }
.col-stem { flex: 2; min-width: 100px; cursor: pointer; }
.col-diff { width: 50px; text-align: center; }
.col-kp { width: 60px; text-align: center; }
.col-confirm { width: 80px; text-align: center; }
.col-ai { width: 80px; display: flex; gap: 4px; justify-content: center; }
.col-actions { display: flex; gap: 4px; flex-wrap: wrap; }
.diff-1 { color: #67c23a; } .diff-2 { color: #409eff; } .diff-3 { color: #e6a23c; } .diff-4 { color: #f56c6c; } .diff-5 { color: #9924ff; }
.confirmed { color: #67c23a; } .pending { color: #e6a23c; }
.badge { width: 18px; height: 18px; border-radius: 50%; background: #f0f0f0; color: #909399; font-size: 9px; display: flex; align-items: center; justify-content: center; }
.badge.done { background: #67c23a; color: #fff; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 24px; max-width: 90vw; width: 800px; max-height: 80vh; overflow-y: auto; }
.modal-title { font-size: 16px; font-weight: 500; margin-bottom: 16px; display: block; }
.modal-columns { display: flex; gap: 16px; }
.column { flex: 1; }
.column-title { font-size: 13px; font-weight: 500; color: #409eff; margin-bottom: 8px; display: block; }
.column-content { font-size: 12px; color: #606266; max-height: 200px; margin-bottom: 8px; white-space: pre-wrap; line-height: 1.6; }
.column-content ::deep(.katex) { font-size: 1.1em; }
.column-content ::deep(.katex-display) { margin: 8px 0; overflow-x: auto; }
.modal-footer { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }
.loading, .empty { text-align: center; color: #909399; padding: 40px 0; }
</style>
