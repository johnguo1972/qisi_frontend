<template>
  <view class="course-practice">
    <TeacherSidebar activeItem="course-practice" />

    <view class="main">
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
          <text class="panel-title">习题列表</text>
          <view class="header-actions">
            <button class="btn-action" size="mini" @click="showAddPanel">+ 新增习题</button>
            <button class="btn-action" size="mini" type="primary" @click="batchAiProcess" :disabled="selectedIds.length === 0">批量AI处理</button>
            <button class="btn-action" size="mini" type="success" @click="batchGenerateVariant" :disabled="selectedIds.length === 0">批量生成变式题</button>
            <button class="btn-action" size="mini" type="warning" @click="showGenerateMission">生成任务</button>
          </view>
        </view>

        <!-- Batch action bar -->
        <view v-if="selectedIds.length > 0" class="batch-bar">
          <text class="batch-text">已选 {{ selectedIds.length }} 题</text>
          <button size="mini" @click="showMoveDialog">移动节点</button>
          <button size="mini" type="warn" @click="batchRemove">从课程移除</button>
          <button size="mini" @click="selectedIds = []">取消选择</button>
        </view>

        <!-- Question table -->
        <view v-if="loading" class="loading">加载中...</view>
        <view v-else-if="questions.length === 0" class="empty">暂无题目{{ !selectedNode ? '，请选择目录节点' : '' }}</view>
        <view v-else class="question-table">
          <view class="table-header">
            <view class="col col-check">
              <view class="check-all" @click="toggleSelectAll"><text>{{ isAllSelected ? '☑' : '☐' }}</text></view>
            </view>
            <text class="col-stem">题干</text>
            <text class="col-diff">难度</text>
            <text class="col-kp">知识点</text>
            <text class="col-confirm">内容确认</text>
            <text class="col-ai">AI答案</text>
            <text class="col-actions">操作</text>
          </view>
          <view v-for="q in questions" :key="q.id"
                :class="['table-row', { 'row-selected': selectedIds.includes(q.id) }]"
                @click="toggleSelect(q.id)">
            <view class="col col-check" @click.stop="toggleSelect(q.id)">
              <text>{{ selectedIds.includes(q.id) ? '☑' : '☐' }}</text>
            </view>
            <text class="col-stem" @click.stop="goEdit(q.id)">{{ q.stem_preview }}</text>
            <text :class="['col-diff', 'diff-' + q.difficulty]">L{{ q.difficulty }}</text>
            <text class="col-kp">{{ q.knowledge_points_count || '-' }}</text>
            <text :class="['col-confirm', q.review_status === 'confirmed' ? 'confirmed' : 'pending']">
              {{ q.review_status === 'confirmed' ? '✓' : '待审核' }}
            </text>
            <view class="col-ai" @click.stop>
              <text :class="['badge', q.ai_answer_a_confirmed ? 'done' : q.ai_answer_a ? 'blank' : '']">A</text>
              <text :class="['badge', q.ai_answer_b_confirmed ? 'done' : q.ai_answer_b ? 'blank' : '']">B</text>
              <text :class="['badge', q.ai_answer_c_confirmed ? 'done' : q.ai_answer_c ? 'blank' : '']">C</text>
            </view>
            <view class="col-actions" @click.stop>
              <button size="mini" @click="goEdit(q.id)">编辑</button>
              <button size="mini" type="primary" @click="handleAiProcess(q.id)">AI处理</button>
              <button size="mini" type="success" @click="handleGenerateVariant(q.id)">生成变式</button>
              <button size="mini" type="warn" @click="handleRemove(q.id)">移除</button>
            </view>
          </view>
        </view>
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
          <view :class="['tab', { active: activeTab === 'material' }]" @click="activeTab = 'material'; loadMaterials()">从课程资料选择</view>
          <view :class="['tab', { active: activeTab === 'bank' }]" @click="activeTab = 'bank'; loadBankQuestions()">从题库引入</view>
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
        <scroll-view v-show="activeTab === 'material'" class="tab-content" scroll-y>
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
        <scroll-view v-show="activeTab === 'bank'" class="tab-content" scroll-y>
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
                <text class="bank-meta">难度 L{{ q.difficulty }} | 知识点 {{ q.knowledge_points_count || '-' }}</text>
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
          <button size="default" type="primary" @click="confirmMove" :disabled="!moveTarget">确定移动</button>
        </view>
      </view>
    </view>

    <!-- Generate mission dialog -->
    <view v-if="missionDialogVisible" class="modal-overlay" @click.self="missionDialogVisible = false">
      <view class="modal">
        <text class="modal-title">生成任务关卡</text>
        <view class="form-group">
          <text class="form-label">任务名称</text>
          <input class="form-input" v-model="missionForm.name" placeholder="请输入任务名称" />
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
          <input class="form-input" type="datetime-local" v-model="missionForm.deadline" placeholder="可选" />
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
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import DirTree from '@/components/DirTree.vue'
import { treeApi, courseQuestionApi, variantApi, materialApi } from '@/api/courses'
import { aiProcessQuestion, getAiTaskStatus } from '@/api/questions'

// ============================================================
// Course info
// ============================================================
const courseId = ref<number>(0)
const courseName = ref('课程加载中...')

async function loadCourseInfo() {
  try {
    const res: any = await courseApi.detail(courseId.value)
    if (res?.data?.name) {
      courseName.value = res.data.name
    } else if (res?.name) {
      courseName.value = res.name
    }
  } catch (e) {
    console.error('加载课程信息失败:', e)
    courseName.value = `课程 #${courseId.value}`
  }
}

onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const id = currentPage.options?.id
  if (id) {
    courseId.value = parseInt(id, 10)
    loadCourseInfo()
  }
  loadTree()
  loadQuestions()
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

function onSelectNode(node: TreeNodeData) {
  selectedNode.value = node
  loadQuestions()
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
  id: number
  stem_preview: string
  difficulty: number
  knowledge_points_count?: number
  review_status: string
  ai_answer_a: boolean
  ai_answer_b: boolean
  ai_answer_c: boolean
  ai_answer_a_confirmed: boolean
  ai_answer_b_confirmed: boolean
  ai_answer_c_confirmed: boolean
}

const questions = ref<Question[]>([])
const loading = ref(false)
const selectedIds = ref<number[]>([])

async function loadQuestions() {
  loading.value = true
  try {
    const params: any = {}
    if (selectedNode.value) {
      params.tree_node_id = selectedNode.value.id
    }
    const res: any = await courseQuestionApi.list(courseId.value, params)
    questions.value = res.data || res || []
    selectedIds.value = []
  } catch (e) {
    console.error('加载习题列表失败:', e)
  } finally {
    loading.value = false
  }
}

// Selection
const isAllSelected = computed(() =>
  questions.value.length > 0 && selectedIds.value.length === questions.value.length
)

function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function toggleSelectAll() {
  if (isAllSelected.value) selectedIds.value = []
  else selectedIds.value = questions.value.map((q) => q.id)
}

function goEdit(id: number) {
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
const bankSelectedIds = ref<number[]>([])

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

function toggleBankSelect(id: number) {
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
// AI processing (polling pattern from bank.vue)
// ============================================================
const aiPollTimers: Array<{ taskId: string; timer: ReturnType<typeof setInterval> }> = []

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

async function batchAiProcess() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  for (const id of ids) {
    handleAiProcess(id)
  }
  uni.showToast({ title: `已启动 ${ids.length} 题AI处理`, icon: 'none' })
}

// ============================================================
// Variant generation
// ============================================================
const variantPollTimers: Array<{ taskId: number; timer: ReturnType<typeof setInterval> }> = []

async function handleGenerateVariant(questionId: number) {
  try {
    const res: any = await variantApi.generate(courseId.value, questionId)
    const taskId = res.data?.task_id || res.data?.id
    if (!taskId) {
      uni.showToast({ title: '变式题生成成功', icon: 'success' })
      loadQuestions()
      return
    }
    uni.showToast({ title: `变式题生成中（题${questionId}）`, icon: 'none', duration: 2000 })
    const timer = setInterval(async () => {
      try {
        const statusRes: any = await variantApi.getStatus(courseId.value, taskId)
        const status = statusRes.data?.status
        if (status === 'complete' || status === 'success') {
          clearInterval(timer)
          const idx = variantPollTimers.findIndex(t => t.taskId === taskId)
          if (idx >= 0) variantPollTimers.splice(idx, 1)
          uni.showToast({ title: `变式题已生成（题${questionId}）`, icon: 'success' })
          loadQuestions()
        } else if (status === 'failed') {
          clearInterval(timer)
          const idx = variantPollTimers.findIndex(t => t.taskId === taskId)
          if (idx >= 0) variantPollTimers.splice(idx, 1)
          uni.showToast({ title: `变式题生成失败（题${questionId}）`, icon: 'none' })
        }
      } catch (e) { /* silent */ }
    }, 3000)
    variantPollTimers.push({ taskId, timer })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '生成失败', icon: 'none' })
  }
}

async function batchGenerateVariant() {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  try {
    const res: any = await variantApi.batchGenerate(courseId.value, ids)
    const taskIds = res.data?.task_ids || []
    if (taskIds.length > 0) {
      uni.showToast({ title: `已启动 ${taskIds.length} 题变式生成`, icon: 'none' })
      // Poll each task
      for (const tid of taskIds) {
        const timer = setInterval(async () => {
          try {
            const statusRes: any = await variantApi.getStatus(courseId.value, tid)
            const status = statusRes.data?.status
            if (status === 'complete' || status === 'success' || status === 'failed') {
              clearInterval(timer)
              const idx = variantPollTimers.findIndex(t => t.taskId === tid)
              if (idx >= 0) variantPollTimers.splice(idx, 1)
              if (status !== 'failed') loadQuestions()
            }
          } catch (e) { /* silent */ }
        }, 3000)
        variantPollTimers.push({ taskId: tid, timer })
      }
    } else {
      uni.showToast({ title: '批量变式生成已启动', icon: 'none' })
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || '批量生成失败', icon: 'none' })
  }
}

// ============================================================
// Remove questions
// ============================================================
async function handleRemove(questionId: number) {
  uni.showModal({
    title: '确认移除',
    content: '确定要从课程中移除此题目吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await courseQuestionApi.batchDelete(courseId.value, [questionId])
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
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  uni.showModal({
    title: '确认批量移除',
    content: `确定要从课程中移除选中的 ${ids.length} 道题目吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await courseQuestionApi.batchDelete(courseId.value, ids)
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
const moveTargetLabel = ref('')

function showMoveDialog() {
  moveTarget.value = null
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
  if (!moveTarget.value) return
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  try {
    await courseQuestionApi.batchMove(courseId.value, ids, moveTarget.value)
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
    name: `${courseName.value} - 任务`,
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
      throw new Error(data.message || '生成任务失败')
    }

    uni.showToast({ title: data.message || '任务生成成功', icon: 'success' })
    missionDialogVisible.value = false
  } catch (e: any) {
    console.error('生成任务失败:', e)
    uni.showToast({ title: e?.message || '生成任务失败', icon: 'none' })
  }
}

// ============================================================
// Cleanup
// ============================================================
onUnmounted(() => {
  aiPollTimers.forEach(t => clearInterval(t.timer))
  aiPollTimers.length = 0
  variantPollTimers.forEach(t => clearInterval(t.timer))
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
  gap: 16px;
  padding: 16px;
  overflow: hidden;
  height: 100vh;
}

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

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-action {
  font-size: 12px;
  margin: 0;
}

.btn-action::after {
  border: none;
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
  overflow-y: auto;
}

.table-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #f5f7fa;
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.table-row {
  display: flex;
  align-items: center;
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

.check-all {
  cursor: pointer;
}

.col-stem {
  flex: 2;
  min-width: 100px;
}

.col-diff {
  width: 50px;
  text-align: center;
}

.col-kp {
  width: 60px;
  text-align: center;
}

.col-confirm {
  width: 80px;
  text-align: center;
}

.col-ai {
  width: 80px;
  display: flex;
  gap: 4px;
  justify-content: center;
}

.col-actions {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
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
