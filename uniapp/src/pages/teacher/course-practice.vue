<template>
  <view class="course-practice">
    <TeacherSidebar activeItem="course-list" @navigate="handleSidebarNavigate" />

    <view class="main">
      <!-- #ifndef MP-WEIXIN -->
      <view class="page-topbar">
        <button class="back-btn" @click="goCourseList">返回课程管理</button>
        <text class="page-topbar-title">课程练习</text>
      </view>
      <!-- #endif -->
      <view class="practice-body">
      <!-- Left: Directory tree -->
      <view class="sidebar-tree">
        <view class="tree-header">
          <text class="tree-title">课程目录</text>
          <text class="course-name">{{ courseName }}</text>
        </view>
        <DirTree
          :nodes="treeNodes"
          :loading="treeLoading"
          @select="onSelectNode"
          @add-root="onAddRoot"
          @add-child="onAddChild"
          @rename="onRename"
          @delete-node="onDeleteNode"
          @move-up="onMoveUp"
          @move-down="onMoveDown"
        />
      </view>

      <!-- Center: Question list -->
      <view class="question-panel">
        <view class="panel-header">
          <view>
            <text class="panel-title">习题列表</text>
            <text class="total-count">（{{ total }} 题）</text>
          </view>
          <view class="header-actions">
            <button class="btn-action" size="mini" @click="showAddPanel">+ 新增习题</button>
            <view class="pagination-new">
              <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
              <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
              <picker mode="selector" :range="pageRangeLabels" :value="currentPage - 1" @change="selectPage"><view class="page-picker">{{ pageOptionLabel(currentPage) }}</view></picker>
              <picker mode="selector" :range="pageSizeRange" :value="pageSizeOptions.indexOf(pageSize)" @change="changePageSize"><view class="page-size-picker">{{ pageSizeOptionLabel(pageSize) }}</view></picker>
            </view>
          </view>
        </view>

        <view class="quick-filters">
          <view class="filter-group">
            <text class="filter-label">题型</text>
            <picker mode="selector" :range="questionTypeRange" :value="questionTypeIndex" @change="onQuestionTypeChange"><view class="filter-select">{{ questionTypeLabel }}</view></picker>
            <text class="filter-label">难度</text>
            <picker mode="selector" :range="difficultyRange" :value="difficultyIndex" @change="onDifficultyChange"><view class="filter-select">{{ difficultyLabel }}</view></picker>
            <text class="filter-label">知识点</text>
            <picker mode="selector" :range="knowledgeRange" :value="knowledgeIndex" @change="onKnowledgePointChange"><view class="filter-select">{{ knowledgeLabel }}</view></picker>
            <text class="filter-label">标签</text>
            <picker mode="selector" :range="tagPickerRange" :value="tagPickerIndex" @change="onTagChange"><view class="filter-select tag-filter-select">{{ tagFilterLabel }}</view></picker>
            <button size="mini" class="tag-refresh-btn" :loading="tagLoading" @click="loadTags">刷新标签</button>
            <input v-model="keyword" class="keyword-search" placeholder="输入关键词进行查询" @confirm="applyFilters" />
            <button size="mini" type="primary" @click="applyFilters">查询</button>
            <button size="mini" class="reset-filter-btn" @click="resetFilters">重置</button>
          </view>
        </view>

        <!-- Batch action bar -->
        <view v-if="selectedIds.length > 0 && !loading" class="batch-bar">
          <text class="batch-text">已选 {{ selectedIds.length }} 题</text>
          <button size="mini" @click="showMoveDialog">移动节点</button>
          <button size="mini" type="warn" @click="batchRemove">从课程移除</button>
          <button size="mini" @click="selectedIds = []">取消选择</button>
        </view>

        <scroll-view scroll-y class="question-scroll">
          <view v-if="loading" class="loading">加载中...</view>
          <view v-else-if="questions.length === 0" class="empty">暂无题目{{ !selectedNode ? '，请选择目录节点' : '' }}</view>
          <QuestionDetailCard
            v-for="(question, index) in questions"
            :key="question.id"
            :question="question"
            :index="pageOffset + index + 1"
            :show-answer="Boolean(showAnswerMap[question.id])"
            :selected="selectedIds.includes(question.id)"
            :compact="viewMode === 'compact'"
            @check="toggleSelect"
            @toggle-answer="toggleAnswer(question.id)"
            @ai-answer="mode => openAiAnswer(question, mode)"
            @edit="goEdit"
            @related="handleRelated"
            @edit-tags="openTagEditor"
            @add-favorite="addFavorite"
          >
            <template #course-footer-actions>
              <button data-test="remove-course" size="mini" type="warn" :disabled="loading" @click.stop="handleRemove(question.id)">从课程移除</button>
              <button data-test="disabled-variant" size="mini" disabled @click.stop="handleDisabledVariantAction">生成变式题</button>
            </template>
          </QuestionDetailCard>
        </scroll-view>
      </view>
      <RightActionPanel
        :all-shown="allAnswersShown"
        :compact-mode="viewMode === 'compact'"
        :ai-mode-running="aiModeRunning"
        :ai-action-running="aiActionRunning"
        @refresh="refreshQuestions"
        @toggle-answer="toggleAllAnswers"
        @toggle-mode="toggleViewMode"
        @basket="addSelectedToFavorites"
        @batch-ai="submitBatchAi"
        @ai-explore="submitAiExplore"
        @ai-mode-a="submitAiMode('A')"
        @ai-mode-b="submitAiMode('B')"
        @ai-mode-c="submitAiMode('C')"
      >
        <template #course-actions>
          <button class="course-action-btn" @click="goAssignMission">布置作业</button>
          <button class="course-action-btn" @click="showGenerateMission">生成作业</button>
          <button class="course-action-btn" disabled @click="handleDisabledVariantAction">批量生成变式题</button>
        </template>
      </RightActionPanel>
      </view>
    </view>

    <!-- Add question panel (slide-in) -->
    <view v-if="addPanelVisible" class="panel-overlay" @click.self="closeAddPanel">
      <view class="add-panel">
        <view class="add-panel-header">
          <text class="add-panel-title">新增习题</text>
          <view class="btn-close" @click="closeAddPanel">×</view>
        </view>

        <!-- Tabs -->
        <view class="tab-bar">
          <view :class="['tab', { active: activeTab === 'upload' }]" @click="activeTab = 'upload'">拍照/上传</view>
          <view class="tab" @click="importJsonPackage">JSON数据包导入</view>
        </view>

        <!-- Tab: Upload -->
        <scroll-view v-show="activeTab === 'upload'" class="tab-content" scroll-y>
          <view class="upload-area">
            <text class="upload-hint">拍照或上传图片创建新试题</text>
            <view class="upload-buttons">
              <button class="btn-upload" @click="openCamera">📷 拍照新增</button>
              <button class="btn-upload" @click="chooseImage">📁 上传图片</button>
            </view>
            <text class="upload-note">将跳转至新增试题页面完成编辑</text>
          </view>
        </scroll-view>

        <!-- Tab: From materials -->
        <scroll-view v-if="false" v-show="activeTab === 'material'" class="tab-content" scroll-y>
          <view v-if="materialsLoading" class="loading-sm">加载中...</view>
          <view v-else-if="materials.length === 0" class="empty-sm">暂无课程资料</view>
          <view v-else class="material-list">
            <view v-for="m in materials" :key="m.id" class="material-item">
              <view class="material-info">
                <text class="material-icon">📄</text>
                <text class="material-name">{{ m.name }}</text>
              </view>
              <button size="mini" type="primary" @click="importFromMaterial(m)">引入</button>
            </view>
          </view>
        </scroll-view>

        <!-- Tab: From bank -->
        <scroll-view v-if="false" v-show="activeTab === 'bank'" class="tab-content" scroll-y>
          <view class="bank-search">
            <input class="search-input" placeholder="搜索题干或题号..." v-model="bankSearchText" @confirm="searchBank" />
            <button size="mini" type="primary" @click="searchBank">搜索</button>
          </view>
          <view v-if="bankLoading" class="loading-sm">加载中...</view>
          <view v-else-if="bankQuestions.length === 0" class="empty-sm">未找到题目</view>
          <view v-else class="bank-list">
            <view v-for="q in bankQuestions" :key="q.id" class="bank-item">
              <view class="bank-check" @click="toggleBankSelect(q.id)">
                <text>{{ bankSelectedIds.includes(q.id) ? '☑' : '☐' }}</text>
              </view>
              <view class="bank-info" @click="toggleBankSelect(q.id)">
                <text class="bank-stem">{{ q.stem_preview }}</text>
                <text class="bank-meta">难度 {{ q.difficulty_label || '未评定' }} | 知识点 {{ q.knowledge_points_count || '-' }}</text>
              </view>
            </view>
          </view>
          <view v-if="bankSelectedIds.length > 0" class="bank-footer">
            <text>已选 {{ bankSelectedIds.length }} 题</text>
            <button size="mini" type="primary" @click="importFromBank">引入到课程</button>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- Add/Rename node dialog -->
    <view v-if="nodeDialogVisible" class="modal-overlay" @click.self="nodeDialogVisible = false">
      <view class="modal">
        <text class="modal-title">{{ nodeDialogTitle }}</text>
        <view class="form-group">
          <text class="form-label">节点名称</text>
          <input class="form-input" v-model="nodeFormName" placeholder="请输入节点名称" maxlength="50" @confirm="confirmNodeAction" />
        </view>
        <view class="modal-footer">
          <button size="default" @click="nodeDialogVisible = false">取消</button>
          <button size="default" type="primary" @click="confirmNodeAction">确定</button>
        </view>
      </view>
    </view>

    <!-- Move dialog -->
    <view v-if="moveDialogVisible" class="modal-overlay" @click.self="moveDialogVisible = false">
      <view class="modal">
        <text class="modal-title">移动习题</text>
        <view class="form-group">
          <text class="form-label">目标节点</text>
          <picker :range="moveTargetOptions" range-key="label" @change="onMoveTargetChange">
            <view class="picker-value">
              <text :class="moveTarget ? 'picker-text' : 'picker-placeholder'">
                {{ moveTargetLabel || '请选择目标节点' }}
              </text>
            </view>
          </picker>
        </view>
        <view class="modal-footer">
          <button size="default" @click="moveDialogVisible = false">取消</button>
          <button size="default" type="primary" @click="confirmMove" :disabled="!moveTarget || loading">确定移动</button>
        </view>
      </view>
    </view>

    <!-- Generate mission dialog -->
    <view v-if="missionDialogVisible" class="modal-overlay" @click.self="missionDialogVisible = false">
      <view class="modal">
        <text class="modal-title">生成任务关卡</text>
        <view class="form-group">
          <text class="form-label">作业名称</text>
          <input class="form-input" v-model="missionForm.name" placeholder="请输入作业名称" />
        </view>
        <view class="form-group">
          <text class="form-label">关卡类型</text>
          <picker :range="levelTypeOptions" range-key="label" @change="onLevelTypeChange">
            <view class="picker-value">
              <text>{{ missionForm.levelTypeLabel }}</text>
            </view>
          </picker>
        </view>
        <view class="form-group">
          <text class="form-label">通过条件（正确率）</text>
          <input class="form-input" type="number" v-model="missionForm.correctRate" placeholder="0.6" />
        </view>
        <view class="form-group">
          <text class="form-label">分配班级</text>
          <picker :range="classList" range-key="name" @change="onClassChange">
            <view class="picker-value">
              <text :class="missionForm.classId ? 'picker-text' : 'picker-placeholder'">
                {{ missionForm.classId ? classList.find(c => c.id === missionForm.classId)?.name : '请选择班级（可选）' }}
              </text>
            </view>
          </picker>
        </view>
        <view class="form-group">
          <text class="form-label">截止日期</text>
          <input class="form-input" type="date" v-model="missionForm.deadline" placeholder="选择日期（可选）" />
        </view>
        <view class="selected-nodes" v-if="selectedNodeIds.length > 0">
          <text class="form-label">已选节点（{{ selectedNodeIds.length }}）：</text>
          <text class="node-list">{{ selectedNodeNames }}</text>
        </view>
        <view class="modal-footer">
          <button size="default" @click="missionDialogVisible = false">取消</button>
          <button size="default" type="primary" @click="confirmGenerateMission">
            确认生成
          </button>
        </view>
      </view>
    </view>

    <view v-if="relationState.visible" class="modal-overlay" @click.self="closeRelations">
      <view class="modal relation-modal" @click.stop>
        <view class="relation-modal-header"><text class="modal-title">关联题</text><button size="mini" @click="closeRelations">关闭</button></view>
        <view class="relation-tabs">
          <button size="mini" :class="{ 'relation-tab-active': relationState.tab === 'candidates' }" @click="relationController.selectTab('candidates')">可关联题</button>
          <button size="mini" :class="{ 'relation-tab-active': relationState.tab === 'linked' }" @click="relationController.selectTab('linked')">已关联题</button>
        </view>
        <view v-if="relationState.loading" class="relation-empty">加载中...</view>
        <view v-else-if="relationState.error" class="relation-error">{{ relationState.error }}</view>
        <template v-else-if="relationState.tab === 'candidates'">
          <view v-if="relationState.reason" class="relation-empty">{{ relationState.reason }}</view>
          <view v-else-if="!relationState.candidates.length" class="relation-empty">暂无可关联题</view>
          <view v-else class="relation-list">
            <view class="relation-candidate-toolbar">
              <text>每批 10 题</text>
              <button
                size="mini"
                :disabled="relationState.selectedIds.length > 0 || relationState.candidatePage >= relationCandidatePages"
                @click="relationController.nextCandidateBatch"
              >换一批</button>
            </view>
            <RelationQuestionPreview v-for="item in relationState.candidates" :key="item.id" :item="item">
              <template #leading><checkbox :checked="relationState.selectedIds.includes(item.id)" @click.stop="relationController.toggleSelection(item.id)" /></template>
            </RelationQuestionPreview>
          </view>
          <view class="modal-footer"><button size="mini" type="primary" :disabled="!relationState.selectedIds.length" @click="createRelations">关联</button></view>
        </template>
        <template v-else>
          <view v-if="!relationState.linked.length" class="relation-empty">暂无已关联题</view>
          <view v-else class="relation-list">
            <RelationQuestionPreview v-for="item in relationState.linked" :key="item.id" :item="item">
              <template #trailing><button size="mini" class="relation-remove" @click="confirmRemoveRelation(item.id)">解除关联</button></template>
            </RelationQuestionPreview>
          </view>
          <view v-if="relationState.linkedTotal > relationState.linkedPageSize" class="relation-pagination"><button size="mini" :disabled="relationState.linkedPage <= 1" @click="relationController.previousLinkedPage">上一页</button><text>{{ relationState.linkedPage }} / {{ relationLinkedPages }} 页</text><button size="mini" :disabled="relationState.linkedPage >= relationLinkedPages" @click="relationController.nextLinkedPage">下一页</button></view>
        </template>
      </view>
    </view>

    <view v-if="tagVisible" class="modal-overlay" @click.self="tagVisible = false">
      <view class="modal"><text class="modal-title">标签编辑</text><view class="tag-editor"><text v-for="tag in questionTags" :key="tag.id" class="tag-chip">{{ tag.name }} <text @click="removeQuestionTagFromCurrent(tag.id)">×</text></text></view><input v-model="newTag" class="form-input" placeholder="输入标签后添加" @confirm="addQuestionTagToCurrent" /><view class="modal-footer"><button size="mini" @click="addQuestionTagToCurrent">添加</button><button size="mini" type="primary" @click="tagVisible = false">完成</button></view></view>
    </view>

    <AiAnswerModal :visible="answerVisible" :question="answerQuestion" :mode="answerMode" @close="answerVisible = false" @saved="refreshAnswerQuestion" @reprocessed="refreshAnswerQuestion" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { onHide, onShow, onUnload } from '@dcloudio/uni-app'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import DirTree from '@/components/DirTree.vue'
import { courseApi, treeApi, courseQuestionApi, materialApi, variantApi } from '@/api/courses'
import {
  createCourseQuestionListController,
  loadCourseKnowledgePointOptions,
  handleDisabledVariantAction as ignoreDisabledVariantAction,
  normalizeBackgroundAiStatus,
  submitCourseAiTasks,
  submitCourseBatchAi,
} from './course-practice-list'
import { questionApi, aiProcessProbe, getQuestionTags, addQuestionTag, getTagList, removeQuestionTag, importJsonPackage as importJsonPackageApi } from '@/api/questions'
import { favoriteApi } from '@/api/favorites'
import { createQuestionRelationsController } from './question-relations'
import QuestionDetailCard from '@/components/QuestionDetailCard.vue'
import RelationQuestionPreview from '@/components/RelationQuestionPreview.vue'
import RightActionPanel from '@/components/RightActionPanel.vue'
import AiAnswerModal from '@/components/AiAnswerModal.vue'
import { navigateRoleSection } from '@/utils/role-navigation'

const TEACHER_ROUTES: Record<string, string> = {
  workbench: '/pages/teacher/layout',
  'question-bank': '/pages/teacher/question-bank',
  favorites: '/pages/teacher/favorites',
  'student-management': '/pages/teacher/my-classes',
  'assignment-list': '/pages/teacher/mission-list',
  'learning-stats': '/pages/teacher/learning-stats',
  'course-list': '/pages/teacher/course-list',
}

function handleSidebarNavigate(page: string) {
  // #ifndef MP-WEIXIN
  navigateRoleSection('teacher', page)
  // #endif
  // #ifdef MP-WEIXIN
  const url = TEACHER_ROUTES[page]
  if (url) uni.redirectTo({ url })
  // #endif
}

function goCourseList() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else {
    // #ifndef MP-WEIXIN
    navigateRoleSection('teacher', 'course-list')
    // #endif
    // #ifdef MP-WEIXIN
    uni.redirectTo({ url: '/pages/teacher/course-list' })
    // #endif
  }
}

// ============================================================
// Course info
// ============================================================
const courseId = ref<string>('')
const courseName = ref('课程加载中...')
const courseSubject = ref('')

async function loadCourseInfo() {
  try {
    const res: any = await courseApi.detail(courseId.value)
    if (res?.data?.name) {
      courseName.value = res.data.name
      courseSubject.value = String(res.data.subject || '')
    } else if (res?.name) {
      courseName.value = res.name
      courseSubject.value = String(res.subject || '')
    }
  } catch (e) {
    console.error('加载课程信息失败:', e)
    courseName.value = `课程 #${courseId.value}`
  }
}

onMounted(async () => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const id = currentPage.options?.id
  if (id) {
    courseId.value = String(id)
    await loadCourseInfo()
  }
  await loadTree()
  void loadKnowledgeOptions()
  void loadTags()
  await loadQuestions()
})

// Refresh the current directory after returning from question-edit so the
// saved review status and variant action are immediately reflected.
onShow(() => {
  if (courseId.value) void loadQuestions()
})

// ============================================================
// Tree
// ============================================================
interface TreeNodeData {
  id: number
  name: string
  children?: TreeNodeData[]
  _expanded?: boolean
  parent_id?: number | null
}

const treeNodes = ref<TreeNodeData[]>([])
const treeLoading = ref(false)
const selectedNode = ref<TreeNodeData | null>(null)

async function loadTree() {
  treeLoading.value = true
  try {
    const res: any = await treeApi.list(courseId.value)
    const data = res.data || res || []
    console.log('[loadTree] raw data:', data.map((n: any) => ({ id: n.id, name: n.name, sort_order: n.sort_order, children: n.children?.length })))
    // 递归排序所有节点
    sortTree(data)
    console.log('[loadTree] sorted data:', data.map((n: any) => ({ id: n.id, name: n.name, sort_order: n.sort_order })))
    treeNodes.value = data.map(flattenTree)
  } catch (e) {
    console.error('加载目录树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

/** 递归按 sort_order 排序树节点 */
function sortTree(nodes: any[]) {
  nodes.sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0))
  for (const n of nodes) {
    if (n.children && n.children.length > 0) {
      sortTree(n.children)
    }
  }
}

function flattenTree(node: any): TreeNodeData {
  return {
    ...node,
    _expanded: false,
    children: (node.children || []).map(flattenTree),
  }
}

async function onSelectNode(node: TreeNodeData) {
  selectedNode.value = node
  selectedIds.value = []
  questions.value = []
  total.value = 0
  pageNo.value = 1
  questionListController.resetForNode(String(node.id), pageSize.value)
  loading.value = true
  await loadQuestions()
}

// Node actions
const nodeDialogVisible = ref(false)
const nodeDialogTitle = ref('')
const nodeFormName = ref('')
let nodeActionType: 'add-root' | 'add-child' | 'rename' = 'add-root'
let nodeActionParent: TreeNodeData | null = null

function onAddRoot() {
  nodeActionType = 'add-root'
  nodeActionParent = null
  nodeDialogTitle.value = '添加根节点'
  nodeFormName.value = ''
  nodeDialogVisible.value = true
}

function onAddChild(parent: TreeNodeData) {
  nodeActionType = 'add-child'
  nodeActionParent = parent
  nodeDialogTitle.value = `添加子节点 → ${parent.name}`
  nodeFormName.value = ''
  nodeDialogVisible.value = true
}

function onRename(node: TreeNodeData) {
  nodeActionType = 'rename'
  nodeActionParent = node
  nodeDialogTitle.value = '重命名'
  nodeFormName.value = node.name
  nodeDialogVisible.value = true
}

function onDeleteNode(node: TreeNodeData) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除目录「${node.name}」及其所有子目录吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await treeApi.remove(courseId.value, node.id)
          uni.showToast({ title: '已删除', icon: 'success' })
          await loadTree()
          if (selectedNode.value?.id === node.id) {
            selectedNode.value = null
            loadQuestions()
          }
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    },
  })
}

// ── 同级节点排序 ──

/** 收集所有同级节点（展平树查找相同 parent 的节点） */
function findSiblings(nodes: TreeNodeData[], targetId: number, parentId: number | null): TreeNodeData[] {
  const result: TreeNodeData[] = []
  for (const n of nodes) {
    // 根节点（parent=null）
    if (parentId === null && n.parent === undefined) {
      result.push(n)
    }
    // 子节点（parent 匹配）
    if (parentId !== null && n.parent === parentId) {
      result.push(n)
    }
    if (n.children) {
      result.push(...findSiblings(n.children, targetId, n.id))
    }
  }
  return result
}

async function onMoveUp(node: TreeNodeData) {
  try {
    const res: any = await treeApi.list(courseId.value)
    const allNodes = flatTreeToArray(res.data || [])
    const parentId = node.parent !== undefined && node.parent !== null ? node.parent : null
    const siblings = allNodes
      .filter((n: any) => {
        const nParent = n.parent !== undefined && n.parent !== null ? n.parent : null
        return nParent === parentId
      })
      .sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0))

    const idx = siblings.findIndex((n: any) => n.id === node.id)
    if (idx <= 0) return

    // 与前一个节点交换 sort_order
    const prev = siblings[idx - 1]
    const prevOrder = Number(prev.sort_order) || 0
    const currOrder = Number(siblings[idx].sort_order) || 0

    // 调用后端 API 更新 sort_order
    await treeApi.move(courseId.value, node.id, { sort_order: prevOrder })
    await treeApi.move(courseId.value, prev.id, { sort_order: currOrder })

    // 重新加载树（后端已更新 sort_order）
    await loadTree()
  } catch (e: any) {
    console.error('[onMoveUp] error:', e)
    uni.showToast({ title: '上移失败', icon: 'none' })
  }
}

async function onMoveDown(node: TreeNodeData) {
  try {
    const res: any = await treeApi.list(courseId.value)
    const allNodes = flatTreeToArray(res.data || [])
    const parentId = node.parent !== undefined && node.parent !== null ? node.parent : null
    const siblings = allNodes
      .filter((n: any) => {
        const nParent = n.parent !== undefined && n.parent !== null ? n.parent : null
        return nParent === parentId
      })
      .sort((a: any, b: any) => (a.sort_order || 0) - (b.sort_order || 0))

    const idx = siblings.findIndex((n: any) => n.id === node.id)
    if (idx < 0 || idx >= siblings.length - 1) return

    // 与后一个节点交换 sort_order
    const next = siblings[idx + 1]
    const nextOrder = Number(next.sort_order) || 0
    const currOrder = Number(siblings[idx].sort_order) || 0

    // 调用后端 API 更新 sort_order
    await treeApi.move(courseId.value, node.id, { sort_order: nextOrder })
    await treeApi.move(courseId.value, next.id, { sort_order: currOrder })

    // 重新加载树（后端已更新 sort_order）
    await loadTree()
  } catch (e: any) {
    console.error('[onMoveDown] error:', e)
    uni.showToast({ title: '下移失败', icon: 'none' })
  }
}

/** 将嵌套树展平为扁平节点列表 */
function flatTreeToArray(nodes: any[]): any[] {
  const result: any[] = []
  for (const n of nodes) {
    result.push(n)
    if (n.children) {
      result.push(...flatTreeToArray(n.children))
    }
  }
  return result
}

async function confirmNodeAction() {
  if (!nodeFormName.value.trim()) {
    uni.showToast({ title: '请输入节点名称', icon: 'none' })
    return
  }
  try {
    if (nodeActionType === 'add-root') {
      await treeApi.create(courseId.value, { name: nodeFormName.value.trim() })
    } else if (nodeActionType === 'add-child' && nodeActionParent) {
      await treeApi.create(courseId.value, {
        name: nodeFormName.value.trim(),
        parent: nodeActionParent.id,
      })
    } else if (nodeActionType === 'rename' && nodeActionParent) {
      await treeApi.update(courseId.value, nodeActionParent.id, {
        name: nodeFormName.value.trim(),
      })
    }
    uni.showToast({ title: '操作成功', icon: 'success' })
    nodeDialogVisible.value = false
    await loadTree()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '操作失败', icon: 'none' })
  }
}

// ============================================================
// Questions
// ============================================================
interface Question {
  id: string
  question_id: string
  question_no?: string
  stem?: string
  stem_preview?: string
  question_type?: string
  difficulty: number | null
  knowledge_points_display?: Array<{ id?: string; name: string }>
  tags?: string[]
  [key: string]: unknown
}

const questions = ref<Question[]>([])
const loading = ref(false)
const selectedIds = ref<string[]>([])
const total = ref(0)
const pageNo = ref(1)
const pageSize = ref(20)
const questionListController = createCourseQuestionListController<any>((query) => courseQuestionApi.list(courseId.value, query))
const currentPage = computed({ get: () => pageNo.value, set: (value: number) => { pageNo.value = value } })
const pageSizeOptions = [10, 20, 30, 50]
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const pageNumbers = computed(() => Array.from({ length: totalPages.value }, (_, index) => index + 1))
const pageRangeLabels = computed(() => pageNumbers.value.map(pageOptionLabel))
const pageSizeRange = pageSizeOptions.map((size) => `${size} 题 / 页`)
const pageOffset = computed(() => (currentPage.value - 1) * pageSize.value)

const activeType = ref('')
const activeDifficulty = ref('')
const activeKnowledgePoint = ref('')
const activeTag = ref('')
const keyword = ref('')
const knowledgeOptions = ref<Array<{ id: string; name: string }>>([])
const allTags = ref<Array<{ id: string; name: string }>>([])
const tagLoading = ref(false)
const showAnswerMap = ref<Record<string, boolean>>({})
const viewMode = ref<'compact' | 'detail'>('detail')

const questionTypes = [
  { label: '选择题', value: 'single_choice' },
  { label: '填空题', value: 'fill_blank' },
  { label: '解答题', value: 'solution' },
]
const difficultyLevels = [
  { label: '简单', value: '1' }, { label: '较易', value: '2' }, { label: '中等', value: '3' }, { label: '较难', value: '4' }, { label: '困难', value: '5' },
]
const questionTypeRange = ['全部题型', ...questionTypes.map(item => item.label)]
const difficultyRange = ['全部难度', ...difficultyLevels.map(item => item.label)]
const knowledgeRange = computed(() => ['全部知识点', ...knowledgeOptions.value.map(item => item.name)])
const tagPickerRange = computed(() => ['全部标签', ...allTags.value.map(item => item.name)])
const questionTypeIndex = computed(() => Math.max(0, questionTypes.findIndex(item => item.value === activeType.value) + 1))
const difficultyIndex = computed(() => Math.max(0, difficultyLevels.findIndex(item => item.value === activeDifficulty.value) + 1))
const knowledgeIndex = computed(() => Math.max(0, knowledgeOptions.value.findIndex(item => item.id === activeKnowledgePoint.value) + 1))
const tagPickerIndex = computed(() => Math.max(0, allTags.value.findIndex(item => item.name === activeTag.value) + 1))
const questionTypeLabel = computed(() => questionTypeRange[questionTypeIndex.value])
const difficultyLabel = computed(() => difficultyRange[difficultyIndex.value])
const knowledgeLabel = computed(() => knowledgeRange.value[knowledgeIndex.value])
const tagFilterLabel = computed(() => tagPickerRange.value[tagPickerIndex.value])
const allAnswersShown = computed(() => questions.value.length > 0 && questions.value.every(question => showAnswerMap.value[question.id]))

function normalizeQuestion(item: any): Question {
  const id = String(item?.id || item?.question_id || '')
  return {
    ...item,
    id,
    question_id: String(item?.question_id || id),
    stem: item?.stem || item?.stem_preview || '',
    tags: Array.isArray(item?.tags) ? item.tags : [],
    knowledge_points_display: Array.isArray(item?.knowledge_points_display) ? item.knowledge_points_display : [],
  }
}

async function loadQuestions() {
  const treeNodeId = selectedNode.value ? String(selectedNode.value.id) : ''
  if (questionListController.state.treeNodeId !== treeNodeId) {
    questionListController.resetForNode(treeNodeId, pageSize.value)
  }
  questionListController.state.page = pageNo.value
  questionListController.state.pageSize = pageSize.value
  questionListController.state.selectedIds = [...selectedIds.value]
  loading.value = true
  try {
    const loaded = await questionListController.load({
      questionType: activeType.value,
      difficulty: activeDifficulty.value,
      knowledgePointId: activeKnowledgePoint.value,
      tag: activeTag.value,
      keyword: keyword.value,
    })
    if (!loaded.applied) return
    questions.value = questionListController.state.items.map(normalizeQuestion)
    total.value = questionListController.state.total
    pageNo.value = questionListController.state.page
    pageSize.value = questionListController.state.pageSize
    selectedIds.value = [...questionListController.state.selectedIds]
  } catch (e) {
    console.error('加载习题列表失败:', e)
  } finally {
    if (!questionListController.state.loading) loading.value = false
  }
}

async function refreshQuestions() {
  if (loading.value) return
  await loadQuestions()
  uni.showToast({ title: '题目已刷新', icon: 'success', duration: 1000 })
}

function pageOptionLabel(page: number) {
  return page === currentPage.value ? `${page} / ${totalPages.value} 页` : `第 ${page} 页`
}

function pageSizeOptionLabel(size: number) {
  return size === pageSize.value ? `${size} / ${total.value}` : `${size} 题 / 页`
}

function prevPage() { if (currentPage.value > 1) { currentPage.value -= 1; void loadQuestions() } }
function nextPage() { if (currentPage.value < totalPages.value) { currentPage.value += 1; void loadQuestions() } }
function selectPage(event: any) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, Number(event?.detail?.value ?? 0) + 1))
  void loadQuestions()
}
function changePageSize(event: any) {
  pageSize.value = pageSizeOptions[Number(event?.detail?.value ?? 0)] || pageSizeOptions[0]
  currentPage.value = 1
  void loadQuestions()
}

function onQuestionTypeChange(event: any) { activeType.value = questionTypes[Number(event?.detail?.value ?? 0) - 1]?.value || '' }
function onDifficultyChange(event: any) { activeDifficulty.value = difficultyLevels[Number(event?.detail?.value ?? 0) - 1]?.value || '' }
function onKnowledgePointChange(event: any) { activeKnowledgePoint.value = knowledgeOptions.value[Number(event?.detail?.value ?? 0) - 1]?.id || '' }
function onTagChange(event: any) { activeTag.value = allTags.value[Number(event?.detail?.value ?? 0) - 1]?.name || '' }
function applyFilters() { currentPage.value = 1; void loadQuestions() }
function resetFilters() {
  activeType.value = ''
  activeDifficulty.value = ''
  activeKnowledgePoint.value = ''
  activeTag.value = ''
  keyword.value = ''
  currentPage.value = 1
  void loadQuestions()
}

async function loadTags() {
  tagLoading.value = true
  try {
    const response: any = await getTagList()
    allTags.value = Array.isArray(response?.data) ? response.data : []
  } catch {
    allTags.value = []
    uni.showToast({ title: '加载标签失败', icon: 'none' })
  } finally {
    tagLoading.value = false
  }
}

async function loadKnowledgeOptions() {
  try {
    knowledgeOptions.value = await loadCourseKnowledgePointOptions(courseSubject.value, subject => questionApi.dictKnowledgePoints(subject))
  } catch {
    knowledgeOptions.value = []
  }
}

function toggleAnswer(id: string) { showAnswerMap.value[id] = !showAnswerMap.value[id] }
function toggleAllAnswers() {
  const allShown = allAnswersShown.value
  questions.value.forEach(question => { showAnswerMap.value[question.id] = !allShown })
}
function toggleViewMode() { viewMode.value = viewMode.value === 'compact' ? 'detail' : 'compact' }
function handleDisabledVariantAction() {
  return ignoreDisabledVariantAction({ generate: () => undefined, batchGenerate: () => undefined })
}

// Selection
function toggleSelect(id: string) {
  if (loading.value) return
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function goEdit(id: string) {
  uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` })
}

// ============================================================
// Add question panel
// ============================================================
const addPanelVisible = ref(false)
const activeTab = ref('upload')

function showAddPanel() {
  addPanelVisible.value = true
  activeTab.value = 'upload'
}

function closeAddPanel() {
  addPanelVisible.value = false
}

function openCamera() {
  // Navigate to existing new-question page
  uni.navigateTo({
    url: `/pages/teacher/new-question?courseId=${courseId.value}`,
    fail: () => {
      console.error('跳转新增试题页面失败')
    },
  })
  closeAddPanel()
}

function chooseImage() {
  // @ts-ignore
  uni.chooseImage({
    count: 1,
    sourceType: ['album'],
    success: (res: any) => {
      uni.navigateTo({
        url: `/pages/teacher/new-question?courseId=${courseId.value}&filePath=${res.tempFilePaths[0]}`,
        fail: () => {
          console.error('跳转新增试题页面失败')
        },
      })
      closeAddPanel()
    },
  })
}

function goAssignMission() {
  uni.navigateTo({ url: `/pages/teacher/mission-create?courseId=${courseId.value}` })
}

function importJsonPackage() {
  // Keep the course entry point limited to the supported JSON package flow.
  // @ts-ignore
  uni.chooseFile({
    count: 1,
    extension: ['zip', 'json'],
    success: async (res: any) => {
      try {
        const file = res.tempFiles?.[0]?.file || res.tempFiles?.[0]
        await importJsonPackageApi(file)
        uni.showToast({ title: '导入任务已提交', icon: 'success' })
        closeAddPanel()
      } catch (e) {
        uni.showToast({ title: 'JSON导入失败', icon: 'none' })
      }
    },
  })
}

// ============================================================
// Materials tab
// ============================================================
const materials = ref<any[]>([])
const materialsLoading = ref(false)
let materialsLoaded = false // Cache flag: only fetch once per page load

async function loadMaterials() {
  if (materialsLoaded) return // Cached - skip redundant API call
  materialsLoading.value = true
  try {
    const res: any = await materialApi.list(courseId.value)
    materials.value = res.data || res || []
    materialsLoaded = true
  } catch (e) {
    console.error('加载课程资料失败:', e)
  } finally {
    materialsLoading.value = false
  }
}

function importFromMaterial(material: any) {
  uni.navigateTo({
    url: `/pages/teacher/course-material-import?course_id=${courseId.value}&material_id=${material.id}`,
    fail: (err) => {
      console.error('跳转导入页面失败:', err)
      uni.showToast({ title: '页面跳转失败', icon: 'none' })
    },
  })
}

// ============================================================
// Bank tab
// ============================================================
const bankQuestions = ref<any[]>([])
const bankLoading = ref(false)
const bankSearchText = ref('')
const bankSelectedIds = ref<string[]>([])

async function loadBankQuestions() {
  bankLoading.value = true
  bankSelectedIds.value = []
  try {
    // Use questionApi list to get all bank questions
    const { questionApi } = await import('@/api/questions')
    const res: any = await questionApi.list({ page: 1, page_size: 100 })
    bankQuestions.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('加载题库失败:', e)
  } finally {
    bankLoading.value = false
  }
}

function searchBank() {
  if (!bankSearchText.value.trim()) {
    loadBankQuestions()
    return
  }
  // Simple client-side filter
  const text = bankSearchText.value.trim().toLowerCase()
  // Reload then filter
  loadBankQuestions().then(() => {
    bankQuestions.value = bankQuestions.value.filter((q: any) =>
      (q.stem_preview || '').toLowerCase().includes(text) ||
      (q.system_id || '').toLowerCase().includes(text) ||
      (q.question_no || '').toLowerCase().includes(text)
    )
  })
}

function toggleBankSelect(id: string) {
  const idx = bankSelectedIds.value.indexOf(id)
  if (idx >= 0) bankSelectedIds.value.splice(idx, 1)
  else bankSelectedIds.value.push(id)
}

async function importFromBank() {
  if (bankSelectedIds.value.length === 0) return
  try {
    await courseQuestionApi.import(courseId.value, {
      question_ids: bankSelectedIds.value,
      tree_node_id: selectedNode.value?.id,
    })
    uni.showToast({ title: `已引入 ${bankSelectedIds.value.length} 题`, icon: 'success' })
    bankSelectedIds.value = []
    closeAddPanel()
    loadQuestions()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '引入失败', icon: 'none' })
  }
}

// ============================================================
// AI processing: submit durable background jobs and poll only their summaries.
// ============================================================
type CourseAiJobPoll = {
  jobId: string
  timer: ReturnType<typeof setInterval>
  isBatch: boolean
}

const courseAiJobPollTimers: CourseAiJobPoll[] = []
const batchAiProcessing = ref(false)
const batchAiProgress = ref({ completed: 0, total: 0, failed: 0 })

function stopBackgroundAiJobPoll(jobId: string) {
  const index = courseAiJobPollTimers.findIndex(poll => poll.jobId === jobId)
  if (index < 0) return
  const [poll] = courseAiJobPollTimers.splice(index, 1)
  clearInterval(poll.timer)
}

function startBackgroundAiJob(jobId: string, total: number, isBatch: boolean) {
  const poll = async () => {
    try {
      const response: any = await questionApi.getAiJobStatus(jobId)
      const data = response?.data
      if (response?.success === false || !data) return

      const completed = data.succeeded + data.partial + data.failed + data.cancelled
      if (isBatch) {
        batchAiProgress.value = {
          completed,
          total: data.total ?? total,
          failed: data.partial + data.failed + data.cancelled,
        }
      }
      if (data.status !== 'completed' && data.status !== 'cancelled') return

      stopBackgroundAiJobPoll(jobId)
      if (isBatch) batchAiProcessing.value = false
      loadQuestions()
      const failed = data.partial + data.failed + data.cancelled
      const title = failed
        ? `AI处理完成：${data.succeeded}题成功，${failed}题未完成`
        : `AI处理完成：${data.succeeded}题成功`
      uni.showToast({ title, icon: failed ? 'none' : 'success', duration: 3000 })
    } catch (_) {
      // Network errors are transient; keep polling the durable server-side job.
    }
  }
  const timer = setInterval(poll, 2000)
  courseAiJobPollTimers.push({ jobId, timer, isBatch })
  void poll()
}

async function handleAiProcess(questionId: string) {
  try {
    const response: any = await questionApi.batchAi([questionId])
    const jobId = response?.data?.job_id
    if (!jobId) throw new Error('AI job was not created')
    startBackgroundAiJob(jobId, 1, false)
    uni.showToast({ title: '已提交后台AI处理', icon: 'none' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || 'AI处理启动失败', icon: 'none' })
  }
}

async function batchAiProcess() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  batchAiProcessing.value = true
  batchAiProgress.value = { completed: 0, total: ids.length, failed: 0 }
  try {
    const response: any = await questionApi.batchAi(ids)
    const jobId = response?.data?.job_id
    if (!jobId) throw new Error('AI job was not created')
    startBackgroundAiJob(jobId, ids.length, true)
    uni.showToast({ title: '已提交后台批量AI处理', icon: 'none' })
  } catch (error: any) {
    batchAiProcessing.value = false
    uni.showToast({ title: error?.message || '批量AI处理启动失败', icon: 'none' })
  }
}

// ============================================================
// Variant generation
// ============================================================
type VariantPoll = {
  taskId: string
  questionId?: string
  timer: ReturnType<typeof setTimeout>
  inFlight: boolean
  attempts: number
}
const variantPollTimers: VariantPoll[] = []

const variantModes = ['数值变化', '情境变化', '条件变化', '综合变式']

async function chooseVariantMode(): Promise<string | null> {
  return new Promise((resolve) => {
    uni.showActionSheet({
      itemList: variantModes,
      success: (result) => resolve(variantModes[result.tapIndex] || null),
      fail: () => resolve(null),
    })
  })
}

function removeVariantPoll(poll: VariantPoll) {
  clearTimeout(poll.timer)
  const index = variantPollTimers.indexOf(poll)
  if (index >= 0) variantPollTimers.splice(index, 1)
}

function hasVariantPoll(questionId: string) {
  return variantPollTimers.some((poll) => poll.questionId === questionId)
}

function startVariantPolling(taskId: string, questionId: string, questionNo: string) {
  if (!taskId || hasVariantPoll(questionId)) return

  const poll: VariantPoll = { taskId, questionId, timer: setTimeout(() => undefined, 0), inFlight: false, attempts: 0 }
  const pollOnce = async () => {
    if (!variantPollTimers.includes(poll) || poll.inFlight) return
    poll.attempts += 1
    if (poll.attempts > 120) {
      removeVariantPoll(poll)
      uni.showToast({ title: '变式任务等待超时，请检查后台任务后重试', icon: 'none' })
      return
    }
    poll.inFlight = true
    try {
      const statusRes: any = await variantApi.getStatus(courseId.value, taskId)
      const status = statusRes.data?.status
      if (status === 'success' || status === 'complete') {
        removeVariantPoll(poll)
        uni.showToast({ title: `变式题已生成（题${questionNo}）`, icon: 'success' })
        loadQuestions()
      } else if (status === 'failed') {
        removeVariantPoll(poll)
        uni.showToast({ title: `变式题生成失败（题${questionNo}）`, icon: 'none' })
      } else if (variantPollTimers.includes(poll)) {
        poll.timer = setTimeout(pollOnce, 3000)
      }
    } catch (error: any) {
      const statusCode = error?.status || error?.response?.status
      const message = String(error?.message || '')
      const isNotFound = statusCode === 404 || message.includes('404') || message.includes('不存在')
      if (isNotFound) {
        // A 404 means this is an obsolete/wrong task ID. Stop permanently;
        // otherwise the old ID would be requested forever every 3 seconds.
        removeVariantPoll(poll)
        uni.showToast({ title: '变式任务已失效，请重新生成', icon: 'none' })
      } else if (variantPollTimers.includes(poll)) {
        poll.timer = setTimeout(pollOnce, 5000)
      }
    } finally {
      poll.inFlight = false
    }
  }
  variantPollTimers.push(poll)
  poll.timer = setTimeout(pollOnce, 1000)
}

async function handleGenerateVariant(question: Question) {
  if (question.review_status !== 'confirmed') {
    uni.showToast({ title: '本题待审核，请先编辑并确认题目', icon: 'none' })
    return
  }
  const mode = await chooseVariantMode()
  if (!mode) return
  if (hasVariantPoll(question.question_id)) {
    uni.showToast({ title: '本题已有变式任务在处理中，请勿重复提交', icon: 'none' })
    return
  }
  try {
    const res: any = await variantApi.generate(courseId.value, question.question_id, mode)
    const taskId = String(res.data?.task_id || '')
    if (!taskId) {
      uni.showToast({ title: '未获取到变式任务编号', icon: 'none' })
      return
    }
    uni.showToast({ title: `变式题生成中（题${question.question_no}）`, icon: 'none', duration: 2000 })
    startVariantPolling(taskId, question.question_id, String(question.question_no || ''))
  } catch (e: any) {
    uni.showToast({ title: e?.message || '生成失败', icon: 'none' })
  }
}

async function batchGenerateVariant() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  const selectedQuestionsForVariant = questions.value.filter((question) => ids.includes(question.question_id))
  if (selectedQuestionsForVariant.some((question) => question.review_status !== 'confirmed')) {
    uni.showToast({ title: '所选题目含待审核题，请先编辑并确认', icon: 'none' })
    return
  }
  const mode = await chooseVariantMode()
  if (!mode) return
  try {
    const res: any = await variantApi.batchGenerate(courseId.value, ids, mode)
    const taskIds = Array.from(new Set((res.data?.task_ids || []).map((id: any) => String(id)).filter(Boolean)))
    if (taskIds.length > 0) {
      uni.showToast({ title: `已启动 ${taskIds.length} 题变式生成`, icon: 'none' })
      // Poll each task
      for (const [index, tid] of taskIds.entries()) {
        const question = selectedQuestionsForVariant[index]
        if (question) startVariantPolling(tid, question.question_id, String(question.question_no || ''))
      }
    } else {
      uni.showToast({ title: '批量变式生成已启动', icon: 'none' })
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || '批量生成失败', icon: 'none' })
  }
}

// ============================================================
// Question-bank AI controls: every request is submitted as a background task.
// ============================================================
type AiMode = 'A' | 'B' | 'C'
type AiModeTerminalStatus = 'complete' | 'partial' | 'failed' | 'skipped' | 'cancelled'
type AiModePoll = { taskId: string; generation: number; timer?: ReturnType<typeof setTimeout>; releaseDelay?: () => void; cancelled: boolean }
const aiModeRunning = ref<Record<AiMode, boolean>>({ A: false, B: false, C: false })
const aiActionRunning = ref<Record<'batch' | 'probe', boolean>>({ batch: false, probe: false })
const aiModePolls = new Map<string, AiModePoll>()
let aiModeGeneration = 0
let aiModePageActive = true

function selectionRequired() {
  uni.showToast({ title: '请先选择题目', icon: 'none' })
}

async function submitBatchAi() {
  if (loading.value || aiActionRunning.value.batch) return
  aiActionRunning.value.batch = true
  try {
    const submitted = await submitCourseBatchAi({
      selectedIds: selectedIds.value,
      batchAi: (ids) => questionApi.batchAi(ids),
      poll: taskId => pollAiTaskUntilTerminal(taskId, questionApi.getAiJobStatus),
      refresh: loadQuestions,
      onTerminal: () => { aiActionRunning.value.batch = false },
    })
    if (!submitted.submitted) {
      aiActionRunning.value.batch = false
      if (selectedIds.value.length === 0) selectionRequired()
      else if (submitted.noNewTask) uni.showToast({ title: '所选题目已有进行中的 AI 任务', icon: 'none' })
      else uni.showToast({ title: '批量AI任务提交失败', icon: 'none' })
      return
    }
    uni.showToast({ title: '批量AI任务已提交', icon: 'success' })
  } catch {
    aiActionRunning.value.batch = false
    uni.showToast({ title: '批量AI任务提交失败', icon: 'none' })
  }
}

async function submitAiExplore() {
  if (loading.value || aiActionRunning.value.probe) return
  if (!selectedIds.value.length) return selectionRequired()
  aiActionRunning.value.probe = true
  try {
    const submitted = await submitCourseAiTasks({
      selectedIds: selectedIds.value,
      submit: id => aiProcessProbe(id),
      poll: taskId => pollAiTaskUntilTerminal(taskId, questionApi.getTaskStatus),
      refresh: loadQuestions,
      onTerminal: () => { aiActionRunning.value.probe = false },
    })
    if (!submitted.submitted) {
      aiActionRunning.value.probe = false
      uni.showToast({ title: 'AI探索提交失败', icon: 'none' })
    }
    else if (submitted.failed) uni.showToast({ title: `AI探索部分提交（${submitted.submitted}题）`, icon: 'none' })
    else uni.showToast({ title: 'AI探索任务已提交', icon: 'success' })
  } catch {
    aiActionRunning.value.probe = false
    uni.showToast({ title: 'AI探索提交失败', icon: 'none' })
  }
}

function isCurrentAiModeGeneration(generation: number) {
  return aiModePageActive && generation === aiModeGeneration
}

function waitForAiModePoll(poll: AiModePoll, milliseconds: number): Promise<boolean> {
  if (poll.cancelled || !isCurrentAiModeGeneration(poll.generation)) return Promise.resolve(false)
  return new Promise(resolve => {
    const release = () => {
      poll.timer = undefined
      poll.releaseDelay = undefined
      resolve(!poll.cancelled && isCurrentAiModeGeneration(poll.generation))
    }
    poll.releaseDelay = release
    poll.timer = setTimeout(release, milliseconds)
  })
}

async function pollAiTaskUntilTerminal(
  taskId: string,
  getStatus: (taskId: string) => Promise<unknown>,
  generation = aiModeGeneration,
): Promise<AiModeTerminalStatus> {
  const poll: AiModePoll = { taskId, generation, cancelled: false }
  aiModePolls.set(taskId, poll)
  try {
    for (let attempt = 0; attempt < 1050; attempt += 1) {
      if (!await waitForAiModePoll(poll, attempt === 0 ? 1000 : 2000)) return 'cancelled'
      try {
        const response: any = await getStatus(taskId)
        const status = normalizeBackgroundAiStatus(response?.data?.status)
        if (status) return status
      } catch {
        if (attempt === 1049) return 'failed'
      }
    }
    return 'failed'
  } finally {
    if (poll.timer) clearTimeout(poll.timer)
    if (aiModePolls.get(taskId) === poll) aiModePolls.delete(taskId)
  }
}

async function submitAiMode(mode: AiMode) {
  if (loading.value) return
  if (!selectedIds.value.length) return selectionRequired()
  if (aiModeRunning.value[mode]) {
    uni.showToast({ title: `AI-${mode}模式正在处理中`, icon: 'none' })
    return
  }
  const generation = aiModeGeneration
  if (!isCurrentAiModeGeneration(generation)) return
  aiModeRunning.value[mode] = true
  try {
    const submissions = await Promise.all(selectedIds.value.map(async (id) => {
      try {
        const response: any = await questionApi.aiProcessMode(id, mode)
        return response?.data?.task_id ? String(response.data.task_id) : null
      } catch {
        return null
      }
    }))
    if (!isCurrentAiModeGeneration(generation)) return
    const taskIds = submissions.filter((id): id is string => Boolean(id))
    if (!taskIds.length) {
      uni.showToast({ title: `AI-${mode}模式提交失败`, icon: 'none' })
      return
    }
    uni.showToast({ title: `AI-${mode}模式任务已提交`, icon: 'success' })
    const statuses = await Promise.all(taskIds.map(taskId => pollAiTaskUntilTerminal(taskId, questionApi.getTaskStatus, generation)))
    if (!isCurrentAiModeGeneration(generation)) return
    if (statuses.some(status => status === 'complete' || status === 'partial')) await loadQuestions()
  } finally {
    aiModeRunning.value[mode] = false
  }
}

function stopAiModePolling() {
  aiModeGeneration += 1
  aiModePageActive = false
  aiModePolls.forEach(poll => {
    poll.cancelled = true
    if (poll.timer) clearTimeout(poll.timer)
    poll.releaseDelay?.()
  })
  aiModePolls.clear()
  ;(['A', 'B', 'C'] as AiMode[]).forEach(mode => { aiModeRunning.value[mode] = false })
}

onShow(() => { aiModePageActive = true })
onHide(stopAiModePolling)
onUnload(stopAiModePolling)

// ============================================================
// Shared question-bank modals.
// ============================================================
const relationController = createQuestionRelationsController(questionApi)
const relationState = relationController.state
const relationCandidatePages = computed(() => Math.max(1, Math.ceil(relationState.candidateTotal / relationState.candidatePageSize)))
const relationLinkedPages = computed(() => Math.max(1, Math.ceil(relationState.linkedTotal / relationState.linkedPageSize)))
const tagVisible = ref(false)
const editingQuestion = ref<Question | null>(null)
const questionTags = ref<Array<{ id: string; name: string }>>([])
const newTag = ref('')
const answerVisible = ref(false)
const answerQuestion = ref<Question | null>(null)
const answerMode = ref<'ALL' | 'A' | 'B' | 'C'>('ALL')

async function handleRelated(id: string) {
  await relationController.open(id)
  if (relationState.error) uni.showToast({ title: relationState.error, icon: 'none' })
}
function closeRelations() { relationController.close() }
async function createRelations() {
  const result = await relationController.createSelected()
  if (result.status === 'success') uni.showToast({ title: result.message, icon: 'success' })
  else if (result.status !== 'cancelled') uni.showToast({ title: result.message || relationState.error, icon: 'none' })
}
function confirmRemoveRelation(relatedId: string) {
  uni.showModal({ title: '解除关联', content: '解除后仅取消题目关联，不会删除题目或答案。是否继续？', success: async result => {
    if (!result.confirm) return
    try { await relationController.remove(relatedId); uni.showToast({ title: '已解除关联', icon: 'success' }) }
    catch { uni.showToast({ title: relationState.error || '解除关联失败', icon: 'none' }) }
  } })
}
function openAiAnswer(question: Question, mode: 'ALL' | 'A' | 'B' | 'C' = 'ALL') { answerQuestion.value = question; answerMode.value = mode; answerVisible.value = true }
async function refreshAnswerQuestion() {
  const questionId = answerQuestion.value?.id
  await loadQuestions()
  if (questionId) answerQuestion.value = questions.value.find(question => question.id === questionId) || answerQuestion.value
}
async function openTagEditor(question: Question) {
  editingQuestion.value = question
  tagVisible.value = true
  newTag.value = ''
  try { const response: any = await getQuestionTags(question.id); questionTags.value = response?.data || [] }
  catch { questionTags.value = [] }
}
async function addQuestionTagToCurrent() {
  if (!editingQuestion.value || !newTag.value.trim()) return
  try { await addQuestionTag(editingQuestion.value.id, { tag_name: newTag.value.trim() }); await openTagEditor(editingQuestion.value); newTag.value = '' }
  catch { uni.showToast({ title: '标签添加失败', icon: 'none' }) }
}
async function removeQuestionTagFromCurrent(tagId: string) {
  if (!editingQuestion.value) return
  try { await removeQuestionTag(editingQuestion.value.id, tagId); await openTagEditor(editingQuestion.value) }
  catch { uni.showToast({ title: '标签移除失败', icon: 'none' }) }
}
async function addFavorite(id: string) {
  if (loading.value) return
  try { await favoriteApi.add(id); uni.showToast({ title: '已加入精选', icon: 'success' }) }
  catch (error: any) { if (error?.statusCode === 409) uni.showToast({ title: '已在精选中', icon: 'none' }) }
}
async function addSelectedToFavorites() {
  if (loading.value) return
  if (!selectedIds.value.length) return selectionRequired()
  await Promise.all(selectedIds.value.map(addFavorite))
}

// ============================================================
// Remove questions
// ============================================================
async function handleRemove(questionId: string) {
  if (loading.value) return
  const sourceNodeId = String(selectedNode.value?.id || '')
  if (!sourceNodeId) return
  uni.showModal({
    title: '确认移除',
    content: '确定要从课程中移除此题目吗？',
    success: async (res) => {
      if (res.confirm) {
        if (loading.value || String(selectedNode.value?.id || '') !== sourceNodeId) {
          uni.showToast({ title: '当前节点已切换，请刷新后重试', icon: 'none' })
          return
        }
        try {
          await courseQuestionApi.batchDelete(courseId.value, [questionId], sourceNodeId)
          uni.showToast({ title: '已移除', icon: 'success' })
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '移除失败', icon: 'none' })
        }
      }
    },
  })
}

async function batchRemove() {
  if (loading.value) return
  const ids = [...selectedIds.value]
  const sourceNodeId = String(selectedNode.value?.id || '')
  if (ids.length === 0 || !sourceNodeId) return
  uni.showModal({
    title: '确认批量移除',
    content: `确定要从课程中移除选中的 ${ids.length} 道题目吗？`,
    success: async (res) => {
      if (res.confirm) {
        if (loading.value || String(selectedNode.value?.id || '') !== sourceNodeId) {
          uni.showToast({ title: '当前节点已切换，请刷新后重试', icon: 'none' })
          return
        }
        try {
          await courseQuestionApi.batchDelete(courseId.value, ids, sourceNodeId)
          uni.showToast({ title: `已移除 ${ids.length} 题`, icon: 'success' })
          selectedIds.value = []
          loadQuestions()
        } catch (e: any) {
          uni.showToast({ title: e?.message || '批量移除失败', icon: 'none' })
        }
      }
    },
  })
}

// ============================================================
// Move dialog
// ============================================================
const moveDialogVisible = ref(false)
const moveTarget = ref<number | null>(null)
const moveSourceNodeId = ref('')
const moveTargetLabel = ref('')

function showMoveDialog() {
  if (loading.value || !selectedIds.value.length) return
  moveTarget.value = null
  moveSourceNodeId.value = String(selectedNode.value?.id || '')
  moveTargetLabel.value = ''
  moveDialogVisible.value = true
}

const moveTargetOptions = computed(() => {
  const result: Array<{ label: string; value: number }> = []
  function walk(nodes: TreeNodeData[]) {
    for (const n of nodes) {
      result.push({ label: n.name, value: n.id })
      if (n.children) walk(n.children)
    }
  }
  walk(treeNodes.value)
  return result
})

function onMoveTargetChange(e: any) {
  const idx = e.detail.value
  const opt = moveTargetOptions.value[idx]
  if (opt) {
    moveTarget.value = opt.value
    moveTargetLabel.value = opt.label
  }
}

async function confirmMove() {
  if (loading.value) return
  if (!moveTarget.value || !moveSourceNodeId.value) return
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  if (String(selectedNode.value?.id || '') !== moveSourceNodeId.value) {
    uni.showToast({ title: '当前节点已切换，请刷新后重试', icon: 'none' })
    moveDialogVisible.value = false
    return
  }
  try {
    await courseQuestionApi.batchMove(courseId.value, ids, moveSourceNodeId.value, moveTarget.value)
    uni.showToast({ title: `已移动 ${ids.length} 题`, icon: 'success' })
    selectedIds.value = []
    moveDialogVisible.value = false
    loadQuestions()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '移动失败', icon: 'none' })
  }
}

// ============================================================
// Generate Mission
// ============================================================
const missionDialogVisible = ref(false)
const missionForm = ref({
  name: '',
  levelType: 'practice',
  levelTypeLabel: '练习',
  correctRate: '0.6',
  classId: null as number | null,
  deadline: '',
})

const levelTypeOptions = [
  { label: '练习', value: 'practice' },
  { label: '复习', value: 'review' },
  { label: '补做', value: 'retry' },
  { label: '变式', value: 'variant' },
  { label: '测验', value: 'check' },
]

const selectedNodeIds = ref<number[]>([])
const selectedNodeNames = computed(() => {
  return selectedNodeIds.value
    .map(id => {
      const node = flatTreeToArray(treeNodes.value).find((n: any) => n.id === id)
      return node?.name || ''
    })
    .filter(Boolean)
    .join('、')
})

// 班级列表
const classList = ref<any[]>([])

function showGenerateMission() {
  missionForm.value = {
    name: `${courseName.value} - 作业`,
    levelType: 'practice',
    levelTypeLabel: '练习',
    correctRate: '0.6',
    classId: null,
    deadline: '',
  }
  // 默认选中当前选中的节点
  selectedNodeIds.value = selectedNode.value ? [selectedNode.value.id] : []
  // 加载班级列表
  loadClassList()
  missionDialogVisible.value = true
}

async function loadClassList() {
  try {
    const token = uni.getStorageSync('accessToken')
    const response = await fetch('/api/v1/classes/simple', {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (response.ok) {
      const data = await response.json()
      classList.value = data.data || []
    }
  } catch (e) {
    console.error('加载班级列表失败:', e)
  }
}

function onLevelTypeChange(e: any) {
  const idx = e.detail.value
  const opt = levelTypeOptions[idx]
  missionForm.value.levelType = opt.value
  missionForm.value.levelTypeLabel = opt.label
}

function onClassChange(e: any) {
  const idx = e.detail.value
  const cls = classList.value[idx]
  if (cls) {
    missionForm.value.classId = cls.id
  }
}

async function confirmGenerateMission() {
  const token = uni.getStorageSync('accessToken')
  try {
    const response = await fetch(`/api/v1/courses/${courseId.value}/generate-mission/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        node_ids: selectedNodeIds.value,
        mission_name: missionForm.value.name,
        level_type: missionForm.value.levelType,
        pass_rule: { correct_rate: parseFloat(missionForm.value.correctRate) || 0.6 },
        class_id: missionForm.value.classId,
        deadline: missionForm.value.deadline || null,
      }),
    })

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.message || '生成作业失败')
    }

    uni.showToast({ title: data.message || '作业生成成功', icon: 'success' })
    missionDialogVisible.value = false
  } catch (e: any) {
    console.error('生成作业失败:', e)
    uni.showToast({ title: e?.message || '生成作业失败', icon: 'none' })
  }
}

// ============================================================
// Cleanup
// ============================================================
onUnmounted(() => {
  courseAiJobPollTimers.forEach(t => clearInterval(t.timer))
  courseAiJobPollTimers.length = 0
  variantPollTimers.forEach(t => clearTimeout(t.timer))
  variantPollTimers.length = 0
})
</script>

<style scoped>
.course-practice {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.main {
  margin-left: 240px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
  height: 100vh;
}

.page-topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 0 0 auto;
}
.back-btn {
  margin: 0;
  padding: 8px 16px;
  color: #606266;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  font-size: 13px;
}
.back-btn::after { border: none; }
.page-topbar-title { color: #303133; font-size: 16px; font-weight: 600; }
.practice-body { flex: 1; min-height: 0; display: flex; gap: 16px; overflow: hidden; }

/* Left sidebar tree */
.sidebar-tree {
  width: 260px;
  background: #fff;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.tree-header {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.tree-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  display: block;
}

.course-name {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Question panel */
.question-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}
.total-count { margin-left: 8px; color: #909399; font-size: 13px; }

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.btn-action {
  font-size: 12px;
  margin: 0;
}

.btn-action::after {
  border: none;
}

.pagination-new { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.page-picker, .page-size-picker { min-width: 78px; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px; color: #606266; font-size: 12px; line-height: 28px; text-align: center; }
.page-size-picker { min-width: 92px; }
.quick-filters { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.filter-group { display: flex; flex: 1; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.filter-label { color: #909399; font-size: 12px; }
.filter-select { min-width: 86px; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px; color: #606266; font-size: 12px; line-height: 28px; text-align: center; }
.tag-filter-select { min-width: 120px; }
.tag-refresh-btn, .reset-filter-btn { margin: 0; font-size: 12px; }
.keyword-search { flex: 1 1 180px; min-width: 160px; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px; box-sizing: border-box; font-size: 12px; }
.question-scroll { flex: 1; min-height: 0; padding: 12px 4px; box-sizing: border-box; background: #f5f7fa; }
.course-action-btn { width: 100%; margin: 0; padding: 8px 6px; border: 1px solid #dcdfe6; border-radius: 4px; background: #fff; color: #606266; font-size: 12px; line-height: 1.2; }
.course-action-btn[disabled] { color: #909399; background: #f4f4f5; border-color: #e9e9eb; }

/* uni-app applies a low-contrast native disabled style to buttons. Keep the
 * disabled action legible while making its unavailable state obvious. */
.btn-action:disabled,
.btn-action[disabled] {
  color: #909399 !important;
  background-color: #f4f4f5 !important;
  border-color: #e9e9eb !important;
  opacity: 1 !important;
}

/* Batch bar */
.batch-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: #ecf5ff;
  border-radius: 8px;
  margin-bottom: 12px;
}

.batch-text {
  font-size: 13px;
  color: #409eff;
  margin-right: 8px;
}

/* Question table */
.question-table {
  flex: 1;
  overflow: auto;
  min-width: 1180px;
}

.table-header {
  display: flex;
  align-items: center;
  min-width: 1180px;
  padding: 8px 12px;
  background: #f5f7fa;
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.table-row {
  display: flex;
  align-items: flex-start;
  min-width: 1180px;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
  cursor: pointer;
}

.table-row:hover {
  background: #fafafa;
}

.table-row.row-selected {
  background: #ecf5ff;
}

.col-check {
  width: 30px;
  text-align: center;
  cursor: pointer;
  flex-shrink: 0;
}

.col-index {
  width: 48px;
  flex-shrink: 0;
  text-align: center;
  line-height: 24px;
  color: #606266;
}

.check-all {
  cursor: pointer;
}

.col-stem {
  flex: 1 1 auto;
  min-width: 420px;
  max-width: none;
  min-height: 24px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.stem-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.question-table-preview {
  margin-top: 8px;
  max-width: 100%;
  overflow-x: auto;
  background: #fff;
}

.table-caption {
  margin-bottom: 4px;
  color: #909399;
  font-size: 11px;
}

.data-grid {
  display: grid;
  width: max-content;
  min-width: 100%;
  border-top: 1px solid #dcdfe6;
  border-left: 1px solid #dcdfe6;
}

.data-cell {
  min-width: 72px;
  min-height: 26px;
  padding: 4px 6px;
  display: flex;
  align-items: center;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  border-right: 1px solid #dcdfe6;
  border-bottom: 1px solid #dcdfe6;
  color: #606266;
  background: #fff;
}

.col-diff {
  width: 50px;
  text-align: center;
  flex-shrink: 0;
  line-height: 24px;
}

.col-kp {
  width: 60px;
  text-align: center;
  flex-shrink: 0;
  line-height: 24px;
}

.col-confirm {
  width: 80px;
  text-align: center;
  flex-shrink: 0;
  line-height: 24px;
}

.col-ai {
  width: 80px;
  display: flex;
  gap: 4px;
  justify-content: center;
  flex-shrink: 0;
  line-height: 24px;
}

.col-actions {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  width: 360px;
  min-width: 360px;
  flex-shrink: 0;
  align-items: center;
  white-space: nowrap;
}

.col-actions button {
  flex: 0 0 auto;
  margin: 0;
  white-space: nowrap;
}

.col-actions button:disabled,
.col-actions button[disabled] {
  color: #909399 !important;
  background-color: #f4f4f5 !important;
  border-color: #e9e9eb !important;
  opacity: 1 !important;
}

.diff-1 { color: #67c23a; }
.diff-2 { color: #409eff; }
.diff-3 { color: #e6a23c; }
.diff-4 { color: #f56c6c; }
.diff-5 { color: #9924ff; }

.confirmed { color: #67c23a; }
.pending { color: #e6a23c; }

.badge {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f0f0f0;
  color: #909399;
  font-size: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.badge.done {
  background: #67c23a;
  color: #fff;
}

.badge.blank {
  opacity: 0.3;
}

.loading, .empty {
  text-align: center;
  color: #909399;
  padding: 40px 0;
}

.relation-modal { width: min(680px, calc(100vw - 32px)); max-height: 80vh; overflow-y: auto; padding: 16px; }
.relation-modal-header, .relation-tabs { display: flex; align-items: center; gap: 8px; }
.relation-modal-header { justify-content: space-between; }
.relation-modal-header .modal-title { font-size: 17px; }
.relation-tabs { margin: 12px 0; }
.relation-tabs button { flex: 1; font-size: 13px; }
.relation-tab-active { color: #fff; background: #409eff; border-color: #409eff; }
.relation-list { display: flex; flex-direction: column; max-height: 48vh; overflow-y: auto; }
.relation-candidate-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px; color: #8b98a8; font-size: 11px; }
.relation-candidate-toolbar button { margin: 0; font-size: 12px; }
.relation-pagination { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 12px; color: #606266; font-size: 13px; }
.relation-empty { padding: 20px 0; color: #909399; text-align: center; font-size: 13px; }
.relation-error { margin: 8px 0; padding: 7px 9px; color: #f56c6c; background: #fef0f0; border-radius: 4px; font-size: 12px; }
.relation-remove { flex: 0 0 auto; color: #f56c6c; }
.tag-editor { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.tag-chip { padding: 4px 8px; border-radius: 12px; background: #ecf5ff; color: #409eff; font-size: 12px; }

/* Add question panel overlay */
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: stretch;
  justify-content: flex-end;
  z-index: 1000;
}

.add-panel {
  width: 480px;
  background: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
}

.add-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.add-panel-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.btn-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #909399;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.15s;
}

.btn-close:hover {
  background: #f5f7fa;
}

/* Tabs */
.tab-bar {
  display: flex;
  border-bottom: 1px solid #ebeef5;
}

.tab {
  flex: 1;
  padding: 12px 8px;
  text-align: center;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}

.tab.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.tab-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

/* Upload tab */
.upload-area {
  text-align: center;
  padding: 20px 0;
}

.upload-hint {
  font-size: 14px;
  color: #606266;
  display: block;
  margin-bottom: 24px;
}

.upload-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.btn-upload {
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  padding: 16px;
}

.btn-upload::after {
  border: none;
}

.upload-note {
  font-size: 12px;
  color: #909399;
  display: block;
  margin-top: 16px;
}

/* Material list */
.material-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.material-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.material-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.material-icon {
  font-size: 18px;
}

.material-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Bank search */
.bank-search {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.search-input {
  flex: 1;
  height: 36px;
  padding: 0 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-size: 13px;
  color: #303133;
}

.search-input:focus {
  border-color: #409eff;
  background: #fff;
}

.bank-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bank-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 6px;
  cursor: pointer;
}

.bank-check {
  width: 24px;
  text-align: center;
  font-size: 14px;
  flex-shrink: 0;
}

.bank-info {
  flex: 1;
  min-width: 0;
}

.bank-stem {
  font-size: 13px;
  color: #303133;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bank-meta {
  font-size: 11px;
  color: #909399;
  display: block;
  margin-top: 4px;
}

.bank-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  margin-top: 12px;
  border-top: 1px solid #f0f0f0;
  font-size: 13px;
  color: #606266;
}

.loading-sm {
  text-align: center;
  color: #909399;
  padding: 24px 0;
  font-size: 13px;
}

.empty-sm {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
  font-size: 13px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: 400px;
}

.modal-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  display: block;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  font-size: 13px;
  color: #606266;
  display: block;
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-size: 13px;
  color: #303133;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: #409eff;
  background: #fff;
}

.picker-value {
  height: 40px;
  padding: 0 12px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  display: flex;
  align-items: center;
}

.picker-text {
  font-size: 13px;
  color: #303133;
}

.picker-placeholder {
  font-size: 13px;
  color: #c0c4cc;
}

.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}

/* Mission dialog */
.selected-nodes {
  margin-top: 12px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.node-list {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
  display: block;
}

.form-label {
  font-size: 13px;
  color: #303133;
  margin-bottom: 4px;
  display: block;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
}
</style>
