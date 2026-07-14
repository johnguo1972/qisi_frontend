<template>
  <view class="audit-page">

    <!-- 右侧主内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">新增试题</text>
        <button class="btn-add" @click="goCameraCapture">+ 增加新题</button>
      </view>

      <!-- 知识树（左侧面板） -->
      <view class="left-panel">
        <view class="panel-title">知识点</view>
        <view v-if="loadingTree" class="loading">加载中...</view>
        <view v-else class="tree">
          <view v-for="grade in tree" :key="grade.name" class="tree-grade">
            <view class="tree-node" @click="toggleGrade(grade)">
              <text class="tree-arrow">{{ grade.expanded ? '▼' : '▶' }}</text>
              <text class="tree-label">{{ grade.name }}</text>
            </view>
            <view v-if="grade.expanded" class="tree-children">
              <view v-for="sem in grade.semesters" :key="sem.name" class="tree-semester">
                <view class="tree-node" @click="sem.expanded = !sem.expanded">
                  <text class="tree-arrow">{{ sem.expanded ? '▼' : '▶' }}</text>
                  <text class="tree-label">{{ sem.name }}</text>
                </view>
                <view v-if="sem.expanded" class="tree-children">
                  <view v-for="ch in sem.chapters" :key="ch.name" class="tree-chapter">
                    <view class="tree-node" @click="ch.expanded = !ch.expanded">
                      <text class="tree-arrow">{{ ch.expanded ? '▼' : '▶' }}</text>
                      <text class="tree-label">{{ ch.name }}</text>
                    </view>
                    <view v-if="ch.expanded" class="tree-children">
                      <view v-for="kp in ch.knowledge_points" :key="kp.id"
                            class="tree-kp"
                            :class="{ selected: selectedKpId === kp.id }"
                            @click="selectKp(kp)">
                        <text class="kp-name">{{ kp.name }}</text>
                        <text class="kp-count">({{ kp.question_count }})</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 题目列表（右侧面板） -->
      <view class="right-panel">
        <view class="panel-title">题目列表</view>

        <!-- Tab 切换 -->
        <view class="tab-bar">
          <view v-for="tab in tabs" :key="tab.value" class="tab-item"
                :class="{ active: currentTab === tab.value }"
                @click="switchTab(tab.value)">
            <text>{{ tab.label }}</text>
            <text class="tab-count">({{ tab.count }})</text>
          </view>
        </view>

        <view v-if="!selectedKpId" class="empty">
          <text>请从左侧选择一个知识点</text>
        </view>
        <view v-else-if="loadingQuestions" class="loading">加载中...</view>
        <view v-else-if="questions.length === 0" class="empty">
          <text>该知识点下暂无{{ currentTabLabel }}题目</text>
        </view>
        <view v-else class="question-table">
          <view class="table-header">
            <text class="col col-no">编号</text>
            <text class="col col-stem">题干</text>
            <text class="col col-diff">难度</text>
            <text class="col col-kp">知识点</text>
            <text class="col col-content">内容确认</text>
            <text class="col col-ai">AI答案确认</text>
            <text class="col col-status">状态</text>
            <text v-if="currentTab === 'pending'" class="col col-action">操作</text>
          </view>
          <view v-for="q in questions" :key="q.id" class="table-row">
            <text class="col col-no">{{ q.system_id || q.id }}</text>
            <text class="col col-stem" :title="q.stem || ''">{{ truncate(q.stem, 20) }}</text>
            <text class="col col-diff">{{ q.difficulty ? 'L' + q.difficulty : '-' }}</text>
            <text class="col col-kp">{{ getKpCount(q) }}</text>
            <text class="col col-content">{{ q.review_status === 'confirmed' ? '已确认' : '待确认' }}</text>
            <view class="col col-ai ai-status-cell">
              <text class="ai-mode" :class="getAiModeClass(q, 'a')" @click="showAIConfirm(q.id)">A</text>
              <text class="ai-mode" :class="getAiModeClass(q, 'b')" @click="showAIConfirm(q.id)">B</text>
              <text class="ai-mode" :class="getAiModeClass(q, 'c')" @click="showAIConfirm(q.id)">C</text>
            </view>
            <text class="col col-status">{{ getStatusText(q.review_status) }}</text>
            <view v-if="currentTab === 'pending'" class="col col-action">
              <button class="btn-xs btn-edit" @click="goEdit(q.id)">内容编辑</button>
              <button class="btn-xs btn-ai" @click="processAI(q.id)">AI处理</button>
              <button class="btn-xs btn-confirm" @click="showAIConfirm(q.id)">AI答案确认</button>
              <button class="btn-xs btn-delete" @click="deleteQuestion(q.id)">删除</button>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- AI答案确认弹窗 -->
    <view v-if="showAIModal" class="modal-overlay" @click.self="closeAIModal">
      <view class="modal-box">
        <view class="modal-header">
          <text class="modal-title">AI答案确认 - 题目 #{{ aiModalQId }}</text>
          <text class="modal-close" @click="closeAIModal">✕</text>
        </view>
        <view class="modal-body">
          <view v-if="aiLoading" class="loading">加载中...</view>
          <view v-else class="ai-modes">
            <view v-for="mode in ['a', 'b', 'c']" :key="mode" class="ai-mode-card">
              <view class="ai-mode-header">
                <text class="ai-mode-title">{{ mode.toUpperCase() }} 模式</text>
                <text v-if="getAiData(mode)?.confirmed" class="ai-confirmed">✓ 已确认</text>
                <text v-else class="ai-unconfirmed">未确认</text>
              </view>
              <view v-if="!getAiData(mode)" class="ai-blank">空白（未生成）</view>
              <view v-else class="ai-content">
                <text v-if="getAiData(mode).subject">学科：{{ getAiData(mode).subject }}</text>
                <text v-if="getAiData(mode).difficulty">难度：{{ getAiData(mode).difficulty }}</text>
                <text v-if="getAiData(mode).core_ideas">核心思路：{{ Array.isArray(getAiData(mode).core_ideas) ? getAiData(mode).core_ideas.join('、') : getAiData(mode).core_ideas }}</text>
                <view v-if="mode === 'a' && getAiData(mode).steps" class="ai-steps">
                  <text v-for="(step, idx) in getAiData(mode).steps" :key="idx" class="step-item">
                    第{{ idx + 1 }}步：{{ typeof step === 'string' ? step : step.content }}
                  </text>
                </view>
                <view v-if="mode !== 'a' && getAiData(mode).questions" class="ai-questions">
                  <view v-for="(q, idx) in getAiData(mode).questions" :key="idx" class="ai-q-item">
                    <text class="ai-q-title">Q{{ idx + 1 }}：{{ q.question }}</text>
                    <text v-if="q.reference_answer" class="ai-q-answer">参考答案：{{ q.reference_answer }}</text>
                  </view>
                </view>
                <text v-if="getAiData(mode).final_answer" class="ai-final">最终答案：{{ getAiData(mode).final_answer }}</text>
              </view>
              <view v-if="getAiData(mode) && !getAiData(mode).confirmed" class="ai-actions">
                <button class="btn-confirm-mode" @click="confirmAIAnswer(mode)">确认此答案</button>
              </view>
            </view>
          </view>
        </view>
        <view class="modal-footer">
          <button class="btn-cancel" @click="closeAIModal">取消</button>
          <button class="btn-confirm-all" @click="confirmAllAI">全部确认</button>
        </view>
      </view>
    </view>

    <!-- AI处理弹窗 -->
    <view v-if="showProcessModal" class="modal-overlay" @click.self="closeProcessModal">
      <view class="modal-box modal-sm">
        <view class="modal-header">
          <text class="modal-title">AI处理 - 题目 #{{ processModalQId }}</text>
          <text class="modal-close" @click="closeProcessModal">✕</text>
        </view>
        <view class="modal-body">
          <view v-if="!processing" class="process-form">
            <text class="form-label">选择模型：</text>
            <picker :value="processModelIndex" :range="processModelOptions" @change="onProcessModelChange">
              <view class="picker-value">{{ processModelOptions[processModelIndex] }}</view>
            </picker>
            <text class="process-hint">将依次执行：知识点分析 → A模式答案 → B模式答案 → C模式答案</text>
          </view>
          <view v-else class="process-running">
            <view class="spinner"></view>
            <text class="process-status">{{ processStatus }}</text>
          </view>
        </view>
        <view class="modal-footer">
          <button class="btn-cancel" @click="closeProcessModal" :disabled="processing">取消</button>
          <button class="btn-start" @click="startAIProcess" :disabled="processing">开始处理</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { questionApi } from '@/api/index.ts'
import { knowledgeApi, type KnowledgePoint } from '@/api/knowledge.ts'

interface GradeNode { name: string; semesters: SemesterNode[]; expanded: boolean }
interface SemesterNode { name: string; chapters: ChapterNode[]; expanded: boolean }
interface ChapterNode { name: string; knowledge_points: KnowledgePoint[]; expanded: boolean }

const tree = ref<GradeNode[]>([])
const questions = ref<any[]>([])
const selectedKpId = ref<number | null>(null)
const loadingTree = ref(true)
const loadingQuestions = ref(false)

const tabs = [
  { label: '待审核处理', value: 'pending', count: 0 },
  { label: '已审核处理', value: 'confirmed', count: 0 },
]
const currentTab = ref('pending')
const currentTabLabel = computed(() => {
  const tab = tabs.find(t => t.value === currentTab.value)
  return tab ? tab.label : ''
})

// AI modal
const showAIModal = ref(false)
const aiLoading = ref(false)
const aiModalQId = ref(0)
const aiStatusData = ref<any>(null)

// Process modal
const showProcessModal = ref(false)
const processModalQId = ref(0)
const processing = ref(false)
const processStatus = ref('')
const processModelIndex = ref(0)
const processModelOptions = ['默认模型', 'qwen3.6-plus']
let pollTimer: any = null
let currentTaskId = ''

onMounted(async () => {
  loadTree()
})

async function loadTree() {
  loadingTree.value = true
  try {
    const res = await knowledgeApi.tree('math')
    const data = res.data?.grades || res.data || []
    tree.value = data.map((grade: any) => ({
      name: grade.name,
      semesters: (grade.semesters || []).map((sem: any) => ({
        name: sem.name,
        expanded: false,
        chapters: (sem.chapters || []).map((ch: any) => ({
          name: ch.name,
          expanded: false,
          knowledge_points: ch.knowledge_points || [],
        })),
      })),
      expanded: false,
    }))
  } catch (e) {
    console.error('Failed to load knowledge tree:', e)
  }
  loadingTree.value = false
}

function toggleGrade(grade: GradeNode) {
  grade.expanded = !grade.expanded
}

function selectKp(kp: KnowledgePoint) {
  selectedKpId.value = kp.id
  loadQuestions()
}

function switchTab(tab: string) {
  currentTab.value = tab
  if (selectedKpId.value) loadQuestions()
}

async function loadQuestions() {
  if (!selectedKpId.value) return
  loadingQuestions.value = true
  try {
    const res = await questionApi.list({
      page: 1,
      page_size: 100,
      status: currentTab.value,
      knowledge_point_id: selectedKpId.value,
    })
    questions.value = res.data?.items || []
    // Update tab counts
    tabs[0].count = res.data?.pending_count || 0
    tabs[1].count = res.data?.confirmed_count || 0
  } catch (e) {
    console.error('Failed to load questions:', e)
  }
  loadingQuestions.value = false
}

function truncate(str: string, len: number): string {
  if (!str) return '-'
  return str.length > len ? str.substring(0, len) + '...' : str
}

function getKpCount(q: any): number {
  if (q.ai_knowledge_enrichment && q.ai_knowledge_enrichment.knowledge_points) {
    return q.ai_knowledge_enrichment.knowledge_points.length
  }
  return 0
}

function getAiModeClass(q: any, mode: string): string {
  const key = `ai_answer_${mode}`
  const answer = q[key]
  if (!answer) return 'blank'
  if (answer.error) return 'error'
  if (answer.confirmed) return 'done'
  return 'blank'
}

function getAiData(mode: string): any {
  const key = `answer_${mode}`
  return aiStatusData.value?.[key] || null
}

function getStatusText(status: string): string {
  const map: Record<string, string> = { pending: '待审核', confirmed: '已审核', rejected: '已驳回' }
  return map[status] || status
}

function goEdit(id: number) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }
function goCameraCapture() { uni.navigateTo({ url: '/pages/teacher/camera-capture' }) }

// AI Answer Confirm
async function showAIConfirm(qId: number) {
  aiModalQId.value = qId
  showAIModal.value = true
  aiLoading.value = true
  try {
    const res = await questionApi.getAiStatus(qId)
    aiStatusData.value = res.data
  } catch (e) {
    console.error('Failed to load AI status:', e)
  }
  aiLoading.value = false
}

function closeAIModal() {
  showAIModal.value = false
}

async function confirmAIAnswer(mode: string) {
  try {
    await questionApi.aiConfirm(aiModalQId.value, mode.toUpperCase())
    // Refresh modal data
    const res = await questionApi.getAiStatus(aiModalQId.value)
    aiStatusData.value = res.data
    // Refresh list
    if (selectedKpId.value) loadQuestions()
  } catch (e) {
    uni.showToast({ title: '确认失败', icon: 'none' })
  }
}

async function confirmAllAI() {
  if (!aiStatusData.value) return
  const modes = ['a', 'b', 'c']
  for (const mode of modes) {
    const data = getAiData(mode)
    if (data && !data.error && !data.confirmed) {
      try {
        await questionApi.aiConfirm(aiModalQId.value, mode.toUpperCase())
      } catch {}
    }
  }
  const res = await questionApi.getAiStatus(aiModalQId.value)
  aiStatusData.value = res.data
  if (selectedKpId.value) loadQuestions()
}

// AI Process
function processAI(qId: number) {
  processModalQId.value = qId
  processing.value = false
  processStatus.value = ''
  processModelIndex.value = 0
  showProcessModal.value = true
}

function onProcessModelChange(e: any) {
  processModelIndex.value = e.detail.value
}

function closeProcessModal() {
  if (processing.value) return
  showProcessModal.value = false
}

async function startAIProcess() {
  const qId = processModalQId.value
  const modelIdx = processModelIndex.value
  const model = modelIdx > 0 ? processModelOptions[modelIdx] : undefined

  processing.value = true
  processStatus.value = '正在提交任务，请稍候...'

  try {
    const res = await questionApi.aiProcess(qId, model ? { model } : undefined)
    currentTaskId = res.data.task_id
    startPolling(qId)
  } catch (e) {
    processing.value = false
    processStatus.value = '提交失败'
    uni.showToast({ title: 'AI处理启动失败', icon: 'none' })
  }
}

function startPolling(qId: number) {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    if (!currentTaskId) return
    try {
      const res = await questionApi.getTaskStatus(currentTaskId)
      const data = res.data
      if (data.status === 'pending' || data.status === 'running') {
        processStatus.value = data.step_label || '处理中...'
      } else if (data.status === 'success' || data.status === 'partial') {
        stopPolling()
        processStatus.value = '处理完成！'
        setTimeout(() => {
          closeProcessModal()
          if (selectedKpId.value) loadQuestions()
        }, 1500)
      } else if (data.status === 'failed') {
        stopPolling()
        processStatus.value = '处理失败：' + (data.error || '未知错误')
      }
    } catch {}
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  processing.value = false
  currentTaskId = ''
}

async function deleteQuestion(qId: number) {
  uni.showModal({
    title: '确认删除',
    content: '确定删除此题目？此操作不可撤销。',
    success: async (res) => {
      if (res.confirm) {
        try {
          await questionApi.delete(qId)
          uni.showToast({ title: '删除成功', icon: 'success' })
          if (selectedKpId.value) loadQuestions()
        } catch (e) {
          uni.showToast({ title: '删除失败', icon: 'none' })
        }
      }
    }
  })
}
</script>

<style scoped>
.audit-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  display: flex;
  gap: 20rpx;
  padding: 30rpx 40rpx;
  min-height: 100vh;
}

.page-header {
  position: absolute;
  top: 30rpx;
  right: 40rpx;
  display: flex;
  align-items: center;
  gap: 20rpx;
  z-index: 5;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.btn-add {
  background: #4caf50;
  color: #fff;
  border: none;
  padding: 12rpx 30rpx;
  border-radius: 8rpx;
  font-size: 26rpx;
}

/* Left panel: knowledge tree */
.left-panel {
  width: 280px;
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.05);
  overflow-y: auto;
  max-height: calc(100vh - 120rpx);
}
.panel-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 16rpx;
}
.loading, .empty {
  text-align: center;
  padding: 40rpx;
  color: #999;
  font-size: 24rpx;
}

/* Tree styles */
.tree-node {
  display: flex;
  align-items: center;
  padding: 8rpx 0;
  cursor: pointer;
}
.tree-node:hover { background: #f5f5f5; }
.tree-arrow { font-size: 20rpx; color: #999; margin-right: 8rpx; }
.tree-label { font-size: 24rpx; color: #333; }
.tree-children { padding-left: 24rpx; }
.tree-kp {
  display: flex;
  justify-content: space-between;
  padding: 8rpx 12rpx;
  cursor: pointer;
  border-radius: 4rpx;
}
.tree-kp:hover { background: #e3f2fd; }
.tree-kp.selected { background: #409eff; color: #fff; }
.kp-name { font-size: 22rpx; }
.kp-count { font-size: 20rpx; color: #999; }
.tree-kp.selected .kp-count { color: #e3f2fd; }

/* Right panel: question list */
.right-panel {
  flex: 1;
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.05);
  overflow-y: auto;
  max-height: calc(100vh - 120rpx);
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.tab-item {
  padding: 12rpx 24rpx;
  background: #f5f5f5;
  border-radius: 8rpx;
  font-size: 24rpx;
  color: #666;
  cursor: pointer;
  border: 1rpx solid #e8e8e8;
}
.tab-item.active { background: #409eff; color: #fff; border-color: #409eff; }
.tab-count { margin-left: 8rpx; font-size: 20rpx; }

/* Table */
.question-table { width: 100%; }
.table-header {
  display: flex;
  background: #f5f5f5;
  padding: 12rpx 0;
  font-weight: bold;
  font-size: 22rpx;
  color: #555;
  border-bottom: 1rpx solid #e8e8e8;
}
.table-row {
  display: flex;
  padding: 12rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 22rpx;
  align-items: center;
}
.table-row:hover { background: #fafafa; }
.col { padding: 0 8rpx; }
.col-no { width: 100rpx; }
.col-stem { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-diff { width: 80rpx; text-align: center; }
.col-kp { width: 100rpx; text-align: center; }
.col-content { width: 120rpx; text-align: center; }
.col-ai { width: 140rpx; text-align: center; }
.col-status { width: 100rpx; text-align: center; }
.col-action { width: 360rpx; display: flex; gap: 8rpx; }

/* AI status badges */
.ai-status-cell { display: flex; gap: 4rpx; justify-content: center; }
.ai-mode {
  display: inline-block;
  width: 36rpx;
  height: 36rpx;
  line-height: 36rpx;
  text-align: center;
  border-radius: 4rpx;
  font-size: 20rpx;
  font-weight: bold;
  cursor: pointer;
}
.ai-mode.done { background: #e8f5e9; color: #2e7d32; }
.ai-mode.blank { background: #f5f5f5; color: #bbb; }
.ai-mode.error { background: #fce4ec; color: #c62828; }

/* Buttons */
.btn-xs {
  padding: 4rpx 12rpx;
  border: none;
  border-radius: 4rpx;
  font-size: 20rpx;
  cursor: pointer;
}
.btn-edit { background: #1a73e8; color: #fff; }
.btn-ai { background: #ff9800; color: #fff; }
.btn-confirm { background: #4caf50; color: #fff; }
.btn-delete { background: #f44336; color: #fff; }

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
}
.modal-box {
  background: #fff;
  border-radius: 16rpx;
  width: 90%;
  max-width: 1200px;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.2);
}
.modal-sm { max-width: 500px; }
.modal-header {
  padding: 24rpx 30rpx;
  border-bottom: 1rpx solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-title { font-size: 28rpx; font-weight: bold; color: #333; }
.modal-close { font-size: 36rpx; color: #999; cursor: pointer; }
.modal-body { padding: 30rpx; }
.modal-footer {
  padding: 20rpx 30rpx;
  border-top: 1rpx solid #e8e8e8;
  display: flex;
  justify-content: flex-end;
  gap: 16rpx;
}

/* AI modal content */
.ai-modes { display: flex; gap: 20rpx; }
.ai-mode-card {
  flex: 1;
  border: 1rpx solid #e8e8e8;
  border-radius: 12rpx;
  padding: 20rpx;
  max-height: 70vh;
  overflow-y: auto;
}
.ai-mode-header { display: flex; justify-content: space-between; margin-bottom: 12rpx; }
.ai-mode-title { font-size: 26rpx; font-weight: bold; }
.ai-confirmed { color: #2e7d32; font-size: 22rpx; font-weight: bold; }
.ai-unconfirmed { color: #e65100; font-size: 22rpx; font-weight: bold; }
.ai-blank { color: #bbb; font-size: 22rpx; }
.ai-content { font-size: 22rpx; color: #333; }
.ai-content text { display: block; margin-bottom: 8rpx; }
.ai-steps { margin: 12rpx 0; }
.step-item {
  display: block;
  padding: 10rpx 16rpx;
  background: #f8f9fa;
  border-left: 4rpx solid #1a73e8;
  margin-bottom: 8rpx;
  border-radius: 4rpx;
  font-size: 22rpx;
}
.ai-questions { margin: 12rpx 0; }
.ai-q-item {
  padding: 12rpx;
  background: #f8f9fa;
  border-radius: 8rpx;
  margin-bottom: 12rpx;
}
.ai-q-title { font-weight: bold; font-size: 22rpx; margin-bottom: 4rpx; }
.ai-q-answer { font-size: 20rpx; color: #666; }
.ai-final {
  font-size: 24rpx;
  font-weight: bold;
  padding: 12rpx;
  background: #e8f5e9;
  border-radius: 8rpx;
  margin-top: 12rpx;
}
.ai-actions { margin-top: 16rpx; }
.btn-confirm-mode {
  background: #4caf50;
  color: #fff;
  border: none;
  padding: 8rpx 20rpx;
  border-radius: 6rpx;
  font-size: 22rpx;
}
.btn-cancel {
  background: #fff;
  color: #666;
  border: 1rpx solid #ddd;
  padding: 12rpx 24rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}
.btn-confirm-all {
  background: #4caf50;
  color: #fff;
  border: none;
  padding: 12rpx 24rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}
.btn-start {
  background: #1a73e8;
  color: #fff;
  border: none;
  padding: 12rpx 24rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}
.btn-start:disabled, .btn-cancel:disabled { opacity: 0.5; }

/* Process modal */
.process-form { text-align: center; }
.form-label { font-size: 24rpx; font-weight: bold; margin-bottom: 12rpx; display: block; }
.picker-value {
  padding: 12rpx 20rpx;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  font-size: 24rpx;
  margin-bottom: 16rpx;
}
.process-hint { font-size: 20rpx; color: #999; }
.process-running { text-align: center; padding: 30rpx; }
.spinner {
  width: 60rpx;
  height: 60rpx;
  border: 6rpx solid #e8e8e8;
  border-top: 6rpx solid #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.process-status { font-size: 26rpx; color: #1565c0; font-weight: bold; margin-top: 16rpx; display: block; }
</style>
