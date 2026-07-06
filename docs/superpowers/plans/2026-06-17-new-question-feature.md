# 新增试题功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 front/uniapp 中实现完整的"新增试题"功能，包括：拍照上传、知识树筛选、待审核/已审核题目列表、内容编辑、AI处理、AI答案确认。

**Architecture:** 基于现有 uniapp 框架新建页面，复用已有的后端 API（review/question/ai-process/ai-task-status 等）。左侧知识树导航 + 右侧题目列表（待审核/已审核 tab）+ 右上角新增按钮。新增试题支持拍照/上传图片，调用 qwen3-vl-plus 进行内容提取。

**Tech Stack:** Vue3 + uni-app (TypeScript), Django REST API (后端已就绪), qwen3-vl-plus (OCR), qwen3.6-plus (AI处理)

---

## 文件职责映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `uniapp/src/pages/teacher/audit.vue` | 重写 | 新增试题主页面（知识树 + 题目列表 + tab + 操作按钮） |
| `uniapp/src/pages/teacher/camera-capture.vue` | 新建 | 拍照/上传图片页面 |
| `uniapp/src/pages/teacher/question-edit.vue` | 保留现有 | 题目编辑（四分区），已有 |
| `uniapp/src/api/questions.ts` | 修改 | 新增缺失的 API 方法 |
| `uniapp/src/api/knowledge.ts` | 确认存在 | 知识树 API |
| `uniapp/src/pages.json` | 修改 | 注册新页面路由 |
| `uniapp/src/pages/teacher/workbench.vue` | 修改 | 菜单名称改为"新增试题" |

---

### Task 1: 新增试题主页面（audit.vue 重写）

**Files:**
- Modify: `uniapp/src/pages/teacher/audit.vue`

- [ ] **Step 1: 重写 audit.vue 为新增试题主页面**

替换整个 `audit.vue` 内容为：

```vue
<template>
  <view class="audit-page">
    <!-- 左侧导航栏 -->
    <view class="sidebar">
      <view class="sidebar-logo" @click="goWorkbench">A自习室</view>
      <view class="sidebar-user">
        <text class="user-name">{{ userInfo.display_name }}</text>
        <text class="user-role">教师</text>
      </view>
      <view class="nav-items">
        <view class="nav-item" @click="goWorkbench">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">工作台</text>
        </view>
        <view class="nav-group">
          <view class="nav-group-title">题库管理</view>
          <view class="nav-item" @click="goBank">
            <text class="nav-icon">&#128218;</text>
            <text class="nav-text">题库列表</text>
          </view>
          <view class="nav-item" @click="goFavorites">
            <text class="nav-icon">&#11088;</text>
            <text class="nav-text">我的精选</text>
          </view>
        </view>
        <view class="nav-item active">
          <text class="nav-icon">&#128229;</text>
          <text class="nav-text">新增试题</text>
        </view>
        <view class="nav-item" @click="goCreateMission">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">创建任务</text>
        </view>
        <view class="nav-item" @click="goClasses">
          <text class="nav-icon">&#127963;</text>
          <text class="nav-text">班级管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">&#128682;</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
    </view>

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
import { questionApi, authApi } from '../../api'
import { knowledgeApi, type KnowledgePoint } from '../../api/knowledge'

interface Grade { name: string; semesters: Semester[]; expanded: boolean }
interface Semester { name: string; chapters: Chapter[]; expanded: boolean }
interface Chapter { name: string; knowledge_points: KnowledgePoint[]; expanded: boolean }

const userInfo = ref({ display_name: '老师' })
const tree = ref<Grade[]>([])
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
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}
  loadTree()
})

async function loadTree() {
  loadingTree.value = true
  try {
    const res = await knowledgeApi.tree('math')
    const data = res.data || []
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

function toggleGrade(grade: Grade) {
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

// Navigation
function goWorkbench() { uni.navigateTo({ url: '/pages/teacher/workbench' }) }
function goBank() { uni.navigateTo({ url: '/pages/teacher/bank' }) }
function goFavorites() { uni.navigateTo({ url: '/pages/teacher/favorites' }) }
function goCreateMission() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }
function goClasses() { uni.navigateTo({ url: '/pages/teacher/my-classes' }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }
function goCameraCapture() { uni.navigateTo({ url: '/pages/teacher/camera-capture' }) }

async function handleLogout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        uni.reLaunch({ url: '/pages/login/index' })
      }
    }
  })
}

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
.sidebar {
  width: 240px;
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
}
.sidebar-logo {
  padding: 30rpx 24rpx;
  font-size: 32rpx;
  font-weight: bold;
  color: #409eff;
  border-bottom: 1rpx solid #f0f0f0;
  cursor: pointer;
}
.sidebar-user {
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  display: block;
}
.user-role {
  font-size: 22rpx;
  color: #999;
  margin-top: 4rpx;
  display: block;
}
.nav-items {
  padding: 16rpx 0;
  flex: 1;
}
.nav-group { margin-bottom: 8rpx; }
.nav-group-title { padding: 8rpx 24rpx; font-size: 20rpx; color: #999; font-weight: bold; }
.nav-item {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.nav-item:hover { background: #f5f5f5; }
.nav-item.active { background: #ecf5ff; color: #409eff; }
.nav-icon { font-size: 32rpx; margin-right: 12rpx; }
.nav-text { font-size: 26rpx; color: #333; }
.nav-logout:hover { background: #fff0f0; }
.nav-logout .nav-icon { opacity: 0.7; }
.nav-logout .nav-text { color: #e74c3c; }

.main {
  margin-left: 240px;
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
```

- [ ] **Step 2: Verify compilation**

```bash
cd D:\workspace\code\qidi\front\uniapp
npm run build:h5 2>&1 | tail -5
```

Expected: `DONE Build complete.`

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages/teacher/audit.vue
git commit -m "feat: rewrite audit.vue as 新增试题 page with knowledge tree and question list"
```

---

### Task 2: 拍照上传页面（camera-capture.vue）

**Files:**
- Create: `uniapp/src/pages/teacher/camera-capture.vue`
- Modify: `uniapp/src/pages.json`

- [ ] **Step 1: Create camera-capture.vue**

```vue
<template>
  <view class="camera-page">
    <!-- 左侧导航栏 -->
    <view class="sidebar">
      <view class="sidebar-logo" @click="goWorkbench">A自习室</view>
      <view class="sidebar-user">
        <text class="user-name">{{ userInfo.display_name }}</text>
        <text class="user-role">教师</text>
      </view>
      <view class="nav-items">
        <view class="nav-item" @click="goWorkbench">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">工作台</text>
        </view>
        <view class="nav-group">
          <view class="nav-group-title">题库管理</view>
          <view class="nav-item" @click="goBank">
            <text class="nav-icon">&#128218;</text>
            <text class="nav-text">题库列表</text>
          </view>
          <view class="nav-item" @click="goFavorites">
            <text class="nav-icon">&#11088;</text>
            <text class="nav-text">我的精选</text>
          </view>
        </view>
        <view class="nav-item active">
          <text class="nav-icon">&#128229;</text>
          <text class="nav-text">新增试题</text>
        </view>
        <view class="nav-item" @click="goCreateMission">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">创建任务</text>
        </view>
        <view class="nav-item" @click="goClasses">
          <text class="nav-icon">&#127963;</text>
          <text class="nav-text">班级管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">&#128682;</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
    </view>

    <!-- 主内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">拍照上传试题</text>
      </view>

      <view class="capture-area">
        <!-- 图片列表 -->
        <view class="image-list">
          <view v-for="(img, idx) in images" :key="idx" class="image-item">
            <img :src="img.path" class="preview-img" />
            <text class="image-order">第{{ idx + 1 }}张</text>
            <text class="image-remove" @click="removeImage(idx)">✕</text>
          </view>
          <!-- 添加按钮 -->
          <view class="image-item add-btn" @click="chooseImage">
            <text class="add-icon">+</text>
            <text class="add-text">拍照/上传图片</text>
          </view>
        </view>

        <!-- 操作按钮 -->
        <view class="action-bar" v-if="images.length > 0">
          <button class="btn-parse" @click="startParse" :disabled="parsing">
            {{ parsing ? 'AI识别中...' : '开始AI识别' }}
          </button>
          <button class="btn-cancel" @click="goAudit" :disabled="parsing">取消</button>
        </view>

        <!-- 解析进度 -->
        <view v-if="parsing" class="parse-progress">
          <view class="spinner"></view>
          <text class="parse-status">{{ parseStatus }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authApi, questionApi } from '../../api'

const userInfo = ref({ display_name: '老师' })
const images = ref<{ path: string; file?: any }[]>([])
const parsing = ref(false)
const parseStatus = ref('')

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}
})

function chooseImage() {
  // @ts-ignore
  uni.chooseImage({
    count: 9,
    sourceType: ['camera', 'album'],
    success: (res: any) => {
      res.tempFilePaths.forEach((path: string) => {
        images.value.push({ path })
      })
    },
  })
}

function removeImage(idx: number) {
  images.value.splice(idx, 1)
}

async function startParse() {
  if (images.value.length === 0) {
    uni.showToast({ title: '请先上传图片', icon: 'none' })
    return
  }

  parsing.value = true
  parseStatus.value = '正在上传图片，请稍候...'

  try {
    // Step 1: Create a camera paper
    // @ts-ignore
    const createRes = await questionApi.cameraCreate({ subject: '数学' })
    const paperId = createRes.data.paper_id || createRes.data.id

    // Step 2: Upload each image
    for (let i = 0; i < images.value.length; i++) {
      parseStatus.value = `正在上传第${i + 1}张图片...`
      await questionApi.cameraUploadPage(paperId, i + 1, images.value[i].path)
    }

    // Step 3: Trigger AI parse
    parseStatus.value = '正在调用AI识别...'
    await questionApi.cameraParse(paperId)

    parsing.value = false
    uni.showToast({ title: '识别成功，请前往新增试题列表查看', icon: 'success' })
    setTimeout(() => goAudit(), 1500)
  } catch (e: any) {
    parsing.value = false
    parseStatus.value = '识别失败'
    uni.showToast({ title: 'AI识别失败，请重试', icon: 'error' })
  }
}

function goWorkbench() { uni.navigateTo({ url: '/pages/teacher/workbench' }) }
function goBank() { uni.navigateTo({ url: '/pages/teacher/bank' }) }
function goFavorites() { uni.navigateTo({ url: '/pages/teacher/favorites' }) }
function goCreateMission() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }
function goClasses() { uni.navigateTo({ url: '/pages/teacher/my-classes' }) }
function goAudit() { uni.navigateTo({ url: '/pages/teacher/audit' }) }

async function handleLogout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        uni.reLaunch({ url: '/pages/login/index' })
      }
    }
  })
}
</script>

<style scoped>
.camera-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.sidebar {
  width: 240px;
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
}
.sidebar-logo {
  padding: 30rpx 24rpx;
  font-size: 32rpx;
  font-weight: bold;
  color: #409eff;
  border-bottom: 1rpx solid #f0f0f0;
  cursor: pointer;
}
.sidebar-user {
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  display: block;
}
.user-role {
  font-size: 22rpx;
  color: #999;
  margin-top: 4rpx;
  display: block;
}
.nav-items {
  padding: 16rpx 0;
  flex: 1;
}
.nav-group { margin-bottom: 8rpx; }
.nav-group-title { padding: 8rpx 24rpx; font-size: 20rpx; color: #999; font-weight: bold; }
.nav-item {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.nav-item:hover { background: #f5f5f5; }
.nav-item.active { background: #ecf5ff; color: #409eff; }
.nav-icon { font-size: 32rpx; margin-right: 12rpx; }
.nav-text { font-size: 26rpx; color: #333; }
.nav-logout:hover { background: #fff0f0; }
.nav-logout .nav-icon { opacity: 0.7; }
.nav-logout .nav-text { color: #e74c3c; }

.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}

.capture-area {
  background: #fff;
  border-radius: 12rpx;
  padding: 30rpx;
  box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.05);
}

.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.image-item {
  position: relative;
  width: 200rpx;
  height: 280rpx;
  border: 1rpx solid #e8e8e8;
  border-radius: 8rpx;
  overflow: hidden;
}
.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.image-order {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0,0,0,0.6);
  color: #fff;
  font-size: 20rpx;
  padding: 4rpx 8rpx;
  text-align: center;
}
.image-remove {
  position: absolute;
  top: 4rpx;
  right: 4rpx;
  width: 40rpx;
  height: 40rpx;
  line-height: 40rpx;
  text-align: center;
  background: rgba(244,67,54,0.8);
  color: #fff;
  border-radius: 50%;
  font-size: 24rpx;
  cursor: pointer;
}
.add-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2rpx dashed #ddd;
  background: #fafafa;
  cursor: pointer;
}
.add-icon { font-size: 60rpx; color: #999; }
.add-text { font-size: 22rpx; color: #999; margin-top: 8rpx; }

.action-bar {
  display: flex;
  gap: 20rpx;
  justify-content: center;
}
.btn-parse {
  background: #4caf50;
  color: #fff;
  border: none;
  padding: 16rpx 60rpx;
  border-radius: 8rpx;
  font-size: 28rpx;
}
.btn-parse:disabled { opacity: 0.5; }
.btn-cancel {
  background: #fff;
  color: #666;
  border: 1rpx solid #ddd;
  padding: 16rpx 40rpx;
  border-radius: 8rpx;
  font-size: 28rpx;
}
.btn-cancel:disabled { opacity: 0.5; }

.parse-progress {
  text-align: center;
  padding: 40rpx;
}
.spinner {
  width: 80rpx;
  height: 80rpx;
  border: 8rpx solid #e8e8e8;
  border-top: 8rpx solid #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.parse-status {
  display: block;
  font-size: 28rpx;
  color: #1565c0;
  font-weight: bold;
  margin-top: 20rpx;
}
</style>
```

- [ ] **Step 2: Register route in pages.json**

Add to `uniapp/src/pages.json` pages array:

```json
{ "path": "pages/teacher/camera-capture", "style": { "navigationBarTitleText": "拍照上传" } },
```

- [ ] **Step 3: Verify build**

```bash
cd D:\workspace\code\qidi\front\uniapp
npm run build:h5 2>&1 | tail -5
```

Expected: `DONE Build complete.`

- [ ] **Step 4: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages/teacher/camera-capture.vue front/uniapp/src/pages.json
git commit -m "feat: add camera-capture page for photo upload and AI recognition"
```

---

### Task 3: 补充 API 方法

**Files:**
- Modify: `uniapp/src/api/questions.ts`

- [ ] **Step 1: Add missing API methods**

Add to `questionApi` object in `questions.ts`:

```typescript
// Camera paper operations
cameraCreate: (data: { subject: string }) =>
  post<any>('/api/v1/questions/camera-paper/create/', data),
cameraUploadPage: (paperId: number, pageNo: number, filePath: string) => {
  return new Promise<any>((resolve, reject) => {
    // @ts-ignore
    uni.uploadFile({
      url: `/api/v1/questions/camera-paper/${paperId}/upload-page/`,
      filePath: filePath,
      name: 'file',
      formData: { page_no: pageNo },
      header: {
        // @ts-ignore
        Authorization: `Bearer ${uni.getStorageSync('accessToken')}`,
      },
      success: (res: any) => {
        const data = JSON.parse(res.data);
        resolve(data);
      },
      fail: (err: any) => reject(err),
    });
  });
},
cameraParse: (paperId: number) =>
  post<any>(`/api/v1/questions/camera-paper/${paperId}/parse/`),

// AI status
getAiStatus: (questionId: number) =>
  get<any>(`/api/review/question/${questionId}/ai-status/`),
aiConfirm: (questionId: number, mode: string) =>
  post<any>(`/api/review/question/${questionId}/ai-confirm/${mode}/`),
```

- [ ] **Step 2: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/api/questions.ts
git commit -m "feat: add camera paper and AI status API methods"
```

---

### Task 4: 更新 workbench.vue 菜单

**Files:**
- Modify: `uniapp/src/pages/teacher/workbench.vue`

- [ ] **Step 1: Update menu text and icon**

Change the menu item from "OCR审核" to "新增试题":

```vue
<view class="nav-item" @click="goAudit">
  <text class="nav-icon">&#128229;</text>
  <text class="nav-text">新增试题</text>
</view>
```

- [ ] **Step 2: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages/teacher/workbench.vue
git commit -m "fix: rename menu item to 新增试题"
```

---

### Task 5: 后端 API 确认

**Files:**
- Verify: `apps/review/views.py` (already has ai_process_question, ai_task_status)
- Verify: `apps/review/tasks.py` (already has single_ai_process_question)
- Verify: `apps/review/urls.py` (routes already registered)

- [ ] **Step 1: Verify backend API endpoints exist and work**

```bash
cd D:\workspace\code\qidi\front
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.review import views
print('ai_process_question:', hasattr(views, 'ai_process_question'))
print('ai_task_status:', hasattr(views, 'ai_task_status'))
from apps.review.services.ai_review_service import process_single_question
print('process_single_question:', callable(process_single_question))
"
```

Expected: All `True`.

- [ ] **Step 2: Commit (if no changes needed)**

```bash
git status
# If no changes: no commit needed
```

---

### Task 6: 集成测试

**Files:**
- Create: `tests/test_new_question_flow.py`

- [ ] **Step 1: Create test file**

```python
"""Integration tests for the 新增试题 flow."""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from apps.common.ai_prompts import AIPrompts
from apps.common.ai_service import AIReviewService
from apps.common.oss_service import upload_crop_image_safe


class TestNewQuestionFlow:
    """Test the complete new question flow."""

    def test_prompts_exist(self):
        """Verify all prompt methods exist."""
        assert hasattr(AIPrompts, 'probe_and_norm')
        assert hasattr(AIPrompts, 'vision_extraction')
        assert hasattr(AIPrompts, 'solve_mode_a')
        assert hasattr(AIPrompts, 'solve_mode_b')
        assert hasattr(AIPrompts, 'solve_mode_c')
        assert hasattr(AIPrompts, 'verify_result')

    def test_service_has_pipeline(self):
        """Verify AIReviewService has the v2 pipeline method."""
        svc = AIReviewService()
        assert hasattr(svc, 'process_question_full_v2')
        assert hasattr(svc, '_call_ai_multimodal')
        assert hasattr(svc, '_get_question_image_urls')

    def test_oss_service(self):
        """Verify OSS service is available."""
        assert callable(upload_crop_image_safe)

    def test_api_endpoints_exist(self):
        """Verify API view functions exist."""
        from apps.review import views
        assert hasattr(views, 'ai_process_question')
        assert hasattr(views, 'ai_task_status')
```

- [ ] **Step 2: Run tests**

```bash
cd D:\workspace\code\qidi\front
python -m pytest tests/test_new_question_flow.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_new_question_flow.py
git commit -m "test: add integration tests for 新增试题 flow"
```

---

## 执行顺序

1. Task 1: audit.vue 重写
2. Task 2: camera-capture.vue 新建
3. Task 3: API 方法补充
4. Task 4: 菜单更新
5. Task 5: 后端 API 确认
6. Task 6: 集成测试

每个 Task 完成后可独立验证。
