<template>
  <view class="question-bank">
    <view class="main-layout">
      <!-- 左侧：知识树 -->
      <view class="left-panel">
        <view class="subject-selector">
          <picker v-if="allowedSubjects.length > 1" mode="selector" :range="subjectRange" :value="subjectIndex" @change="onSubjectChange"><view class="subject-select">{{ selectedSubjectLabel }}</view></picker>
          <view v-else class="subject-select">{{ selectedSubjectLabel }}</view>
        </view>

        <view class="tree-header">
          <text class="tree-title">知识点</text>
          <input
            v-model="treeSearch"
            class="tree-search"
            placeholder="搜索"
            @input="onTreeSearch"
          />
        </view>

        <view class="tree-actions">
          <button size="mini" @click="toggleSelectMode">{{ selectMode ? '单选' : '多选' }}目录集合</button>
        </view>

        <view v-if="treeLoading" class="loading">加载中...</view>
        <view v-else class="tree-content">
          <view v-for="grade in knowledgeTree" :key="grade.name" class="tree-grade">
            <view class="tree-node grade-node" @click="toggleNode(grade)">
              <text class="arrow">{{ grade.expanded ? '▼' : '▶' }}</text>
              <text class="label">{{ grade.name }}</text>
            </view>
            <view v-if="grade.expanded" class="tree-children">
              <view v-for="sem in grade.semesters" :key="sem.name" class="tree-semester">
                <view class="tree-node semester-node" @click="toggleNode(sem)">
                  <text class="arrow">{{ sem.expanded ? '&#9660;' : '&#9654;' }}</text>
                  <text class="label">{{ sem.name }}</text>
                  <text v-if="sem.question_count" class="count">({{ sem.question_count }})</text>
                </view>
                <view v-if="sem.expanded" class="tree-children">
                  <view v-for="ch in sem.chapters" :key="ch.name" class="tree-chapter">
                    <view class="tree-node chapter-node" @click="toggleNode(ch)">
                      <text class="arrow">{{ ch.expanded ? '&#9660;' : '&#9654;' }}</text>
                      <text class="label">{{ ch.name }}</text>
                      <text v-if="ch.question_count" class="count">({{ ch.question_count }})</text>
                    </view>
                    <view v-if="ch.expanded" class="tree-children">
                      <view
                        v-for="kp in ch.knowledge_points"
                        :key="kp.id"
                        :class="['tree-node kp-node', { active: String(activeKnowledgePoint) === String(kp.id) }]"
                        @click.stop="selectKP(kp)"
                      >
                        <text class="label">{{ kp.name }}</text>
                        <text v-if="kp.question_count" class="count">({{ kp.question_count }})</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 中间：题目列表 -->
      <view class="center-panel">
        <view class="panel-header">
          <view class="header-left">
            <text class="panel-title">题库列表</text>
            <text class="total-count">({{ totalCount }}题)</text>
          </view>
          <view class="header-right">
            <button size="mini" class="btn-add" @click="goKnowledgeMatches">知识点待确认</button>
            <button size="mini" class="btn-add" @click="goHandoutList">讲义管理</button>
            <view class="pagination-new">
              <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
              <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
              <picker mode="selector" :range="pageRangeLabels" :value="currentPage - 1" @change="selectPage"><view class="page-picker">{{ pageOptionLabel(currentPage) }}</view></picker>
              <picker mode="selector" :range="pageSizeRange" :value="pageSizeOptions.indexOf(pageSize)" @change="changePageSize"><view class="page-size-picker">{{ pageSizeOptionLabel(pageSize) }}</view></picker>
            </view>
            <view class="pagination">
              <text class="page-total">共 {{ totalCount }} 题</text>
              <text class="page-size-label">每页</text>
              <picker mode="selector" :range="pageSizeRange" :value="pageSizeOptions.indexOf(pageSize)" @change="changePageSize"><view class="page-size-select">{{ pageSize }} </view></picker>
              <input v-model.number="jumpPage" class="jump-page-input" type="number" min="1" :max="totalPages" placeholder="页码" />
              <button size="mini" @click="goToPage">跳转</button>
              <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
              <text class="page-info">{{ currentPage }}/{{ totalPages }}页</text>
              <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
            </view>
            <button v-if="selectedQuestionIds.length" class="btn-add" @click="goCreateHandout">生成讲义 ({{ selectedQuestionIds.length }})</button>
            <button class="btn-add" @click="showAddMenu">+ 新增</button>
          </view>
        </view>

        <!-- 题目筛选 -->
        <view class="quick-filters">
          <view class="filter-group">
            <text class="filter-label">题型</text>
            <picker mode="selector" :range="questionTypeRange" :value="questionTypeIndex" @change="onQuestionTypeChange"><view class="filter-select">{{ questionTypeLabel }}</view></picker>
            <text class="filter-label">难度</text>
            <picker mode="selector" :range="difficultyRange" :value="difficultyIndex" @change="onDifficultyChange"><view class="filter-select">{{ difficultyLabel }}</view></picker>
          </view>
          <view class="filter-group">
            <text class="filter-label">知识点</text>
            <picker mode="selector" :range="knowledgeRange" :value="knowledgeIndex" @change="onKnowledgePointChange"><view class="filter-select">{{ knowledgeLabel }}</view></picker>
            <text class="filter-label">标签</text>
            <picker mode="selector" :range="tagPickerRange" :value="tagPickerIndex" @change="onTagChange">
              <view class="filter-select tag-filter-select">{{ tagFilterLabel }}</view>
            </picker>
            <button size="mini" class="tag-refresh-btn" :loading="tagLoading" @click="loadTags">刷新标签</button>
            <input v-model="uuidSearch" class="uuid-search" placeholder="输入关键字（可多个）进行查询" />
            <button size="mini" type="primary" @click="applyFilters">查询</button>
            <button size="mini" class="reset-filter-btn" @click="resetFilters">重置</button>
          </view>
        </view>

        <!-- 题目滚动列表 -->
        <scroll-view scroll-y class="question-scroll" @scrolltolower="loadMore">
          <QuestionDetailCard
            v-for="(q, index) in questions"
            :key="q.id"
            :question="q"
            :index="index + 1"
            :show-answer="normalizeAnswerVisibility(showAnswerMap[q.id])"
            :selected="selectedQuestionIds.includes(String(q.id))"
            :compact="viewMode === 'compact'"
            @edit="goEdit"
            @related="handleRelated"
            @edit-tags="openTagEditor"
            @ai-answer="(mode) => openAiAnswer(q, mode)"
            @toggle-answer="toggleAnswer(q.id)"
            @add-favorite="addFavorite(q.id)"
            @check="toggleQuestionSelection"
          />
          <view v-if="loading" class="loading-more">加载中...</view>
          <view v-else-if="questions.length === 0" class="empty-state">
            <text>暂无题目{{ !selectedKP ? '，请选择知识点' : '' }}</text>
          </view>
        </scroll-view>
      </view>

      <!-- 右侧：操作面板 -->
      <RightActionPanel
        :all-shown="allAnswersShown"
        :ai-mode-running="aiModeRunning"
        @refresh="handleRefresh"
        @toggle-answer="toggleAllAnswers"
        :compact-mode="viewMode === 'compact'"
        @toggle-mode="toggleViewMode"
        @basket="handleBasket"
        @batch-ai="handleBatchAi"
        @ai-explore="handleAiExplore"
        @ai-mode-a="handleAiMode('A')"
        @ai-mode-b="handleAiMode('B')"
        @ai-mode-c="handleAiMode('C')"
      />
    </view>

    <!-- 导入弹窗 -->
    <!-- 新增菜单 -->
    <AddMenuModal
      v-if="addMenuVisible"
      @close="addMenuVisible = false"
      @photo="goPhotoUpload"
      @json="handleJsonImport"
    />

    <view v-if="relationState.visible" class="modal-overlay" @click.self="closeRelations">
      <view class="data-modal relation-modal" @click.stop>
        <view class="relation-modal-header">
          <view class="modal-title">关联题</view>
          <button size="mini" class="relation-close" @click="closeRelations">关闭</button>
        </view>
        <view class="relation-tabs">
          <button size="mini" :class="{ 'relation-tab-active': relationState.tab === 'candidates' }" @click="relationController.selectTab('candidates')">可关联题</button>
          <button size="mini" :class="{ 'relation-tab-active': relationState.tab === 'linked' }" @click="relationController.selectTab('linked')">已关联题</button>
        </view>
        <view v-if="relationState.loading" class="relation-empty">加载中...</view>
        <view v-else>
          <view v-if="relationState.error" class="relation-error">{{ relationState.error }}</view>
          <view v-if="relationState.warning" class="relation-warning">{{ relationState.warning }}</view>
          <template v-if="relationState.tab === 'candidates'">
            <view v-if="relationState.reason" class="relation-empty">{{ relationState.reason }}</view>
            <view v-else-if="!relationState.candidates.length" class="relation-empty">暂无可关联题</view>
            <view v-else class="relation-list">
              <view v-for="item in relationState.candidates" :key="item.id" class="related-item relation-candidate-item">
                <checkbox :checked="relationState.selectedIds.includes(item.id)" @click.stop="relationController.toggleSelection(item.id)" />
                <view class="relation-item-main">
                  <text>{{ item.question_no }}：{{ item.stem_preview }}</text>
                  <text v-if="item.common_knowledge_point_names?.length" class="relation-item-meta">共同知识点：{{ item.common_knowledge_point_names.join('、') }}</text>
                </view>
              </view>
            </view>
            <view v-if="relationState.candidateTotal > relationState.candidatePageSize" class="relation-pagination">
              <button size="mini" :disabled="relationState.candidatePage <= 1" @click="relationController.previousCandidatePage">上一页</button>
              <text>{{ relationState.candidatePage }} / {{ relationCandidatePages }} 页（{{ relationState.candidateTotal }}题）</text>
              <button size="mini" :disabled="relationState.candidatePage >= relationCandidatePages" @click="relationController.nextCandidatePage">下一页</button>
            </view>
            <view class="modal-actions"><button size="mini" type="primary" :disabled="!relationState.selectedIds.length" @click="createRelations">关联</button></view>
          </template>
          <template v-else>
            <view v-if="!relationState.linked.length" class="relation-empty">暂无已关联题</view>
            <view v-else class="relation-list">
              <view v-for="item in relationState.linked" :key="item.id" class="related-item relation-linked-item">
                <view class="relation-item-main"><text>{{ item.question_no }}：{{ item.stem_preview }}</text></view>
                <button size="mini" class="relation-remove" @click.stop="confirmRemoveRelation(item.id)">解除关联</button>
              </view>
            </view>
            <view v-if="relationState.linkedTotal > relationState.linkedPageSize" class="relation-pagination">
              <button size="mini" :disabled="relationState.linkedPage <= 1" @click="relationController.previousLinkedPage">上一页</button>
              <text>{{ relationState.linkedPage }} / {{ relationLinkedPages }} 页（{{ relationState.linkedTotal }}题）</text>
              <button size="mini" :disabled="relationState.linkedPage >= relationLinkedPages" @click="relationController.nextLinkedPage">下一页</button>
            </view>
          </template>
        </view>
      </view>
    </view>

    <view v-if="tagVisible" class="modal-overlay" @click.self="tagVisible = false">
      <view class="data-modal"><view class="modal-title">标签编辑</view><view class="tag-editor"><text v-for="tag in questionTags" :key="tag.id" class="tag-chip">{{ tag.name }} <text @click="removeQuestionTagFromCurrent(tag.id)">×</text></text></view><input v-model="newTag" placeholder="输入标签后添加" @confirm="addQuestionTagToCurrent" /><view class="modal-actions"><button size="mini" @click="addQuestionTagToCurrent">添加</button><button size="mini" type="primary" @click="tagVisible = false">完成</button></view></view>
    </view>

    <AiAnswerModal
      :visible="answerVisible"
      :question="answerQuestion"
      :mode="answerMode"
      @close="answerVisible = false"
      @saved="refreshAnswerQuestion"
      @reprocessed="refreshAnswerQuestion"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { onHide, onShow, onUnload } from '@dcloudio/uni-app'
import { questionApi, aiProcessProbe, importJsonPackage, getQuestionTags, addQuestionTag, removeQuestionTag, getTagList } from '@/api/questions'
import { createQuestionRelationsController } from './question-relations'
import { knowledgeApi } from '@/api/knowledge'
import { favoriteApi } from '@/api/favorites'
import { normalizeAnswerVisibility } from '@/utils/answer-visibility'

import QuestionDetailCard from '@/components/QuestionDetailCard.vue'
import AddMenuModal from '@/components/AddMenuModal.vue'
import RightActionPanel from '@/components/RightActionPanel.vue'
import AiAnswerModal from '@/components/AiAnswerModal.vue'

// === 状态 ===
const selectedSubject = ref('')
const activeKnowledgePoint = ref('')
const allowedSubjects = ref<string[]>([])
const tagSearch = ref('')
const allTags = ref<any[]>([])
const tagLoading = ref(false)
const uuidSearch = ref('')
const knowledgeTree = ref<any[]>([])
const treeLoading = ref(false)
const treeSearch = ref('')
const selectMode = ref(false)

const questions = ref<any[]>([])
const loading = ref(false)
const currentPage = ref(1)
const jumpPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(20)
const pageSizeOptions = [10, 20, 30, 50]
const pageNumbers = computed(() => Array.from({ length: totalPages.value }, (_, index) => index + 1))
const subjectLabels: Record<string, string> = {
  chinese: '语文', math: '数学', english: '英语', physics: '物理',
  chemistry: '化学', biology: '生物', geography: '地理', history: '历史',
}
const subjectRange = computed(() => allowedSubjects.value.map((subject) => subjectLabels[subject] || subject))
const subjectIndex = computed(() => Math.max(0, allowedSubjects.value.indexOf(selectedSubject.value)))
const selectedSubjectLabel = computed(() => subjectLabels[selectedSubject.value] || selectedSubject.value || '未配置科目')
const pageRangeLabels = computed(() => pageNumbers.value.map(pageOptionLabel))
const pageSizeRange = pageSizeOptions.map((size) => `${size} 个 / 页`)

const activeType = ref('')
const activeDifficulty = ref('')
const showAnswerMap = ref<Record<string, boolean>>({})
const selectedQuestionIds = ref<string[]>([])
const viewMode = ref<'compact' | 'detail'>('detail')
type AiMode = 'A' | 'B' | 'C'
type AiModeTerminalStatus = 'complete' | 'partial' | 'failed' | 'skipped' | 'cancelled'
type AiModePoll = {
  taskId: string
  mode: AiMode
  generation: number
  timer?: ReturnType<typeof setTimeout>
  releaseDelay?: () => void
  cancelled: boolean
}
const aiModeRunning = ref<Record<AiMode, boolean>>({ A: false, B: false, C: false })
const aiModeTaskIds = ref<Record<AiMode, string[]>>({ A: [], B: [], C: [] })
const aiModeRunGeneration = ref<Record<AiMode, number | null>>({ A: null, B: null, C: null })
const aiModePolls = new Map<string, AiModePoll>()
let aiModePageActive = true
let aiModeGeneration = 0

function isCurrentAiModeGeneration(generation: number) {
  return aiModePageActive && generation === aiModeGeneration
}

const addMenuVisible = ref(false)
const relationController = createQuestionRelationsController(questionApi)
const relationState = relationController.state
const relationCandidatePages = computed(() => Math.max(1, Math.ceil(relationState.candidateTotal / relationState.candidatePageSize)))
const relationLinkedPages = computed(() => Math.max(1, Math.ceil(relationState.linkedTotal / relationState.linkedPageSize)))
const tagVisible = ref(false)
const editingQuestion = ref<any>(null)
const questionTags = ref<any[]>([])
const newTag = ref('')
const answerVisible = ref(false)
const answerQuestion = ref<any | null>(null)
const answerMode = ref<'ALL' | 'A' | 'B' | 'C'>('ALL')

const questionTypes = [
  { label: '选择题', value: 'single_choice' },
  { label: '填空题', value: 'fill_blank' },
  { label: '解答题', value: 'solution' },
]

const difficultyLevels = [
  { label: '简单', value: '1', stars: '★★★★★' },
  { label: '较易', value: '2', stars: '★★★★★' },
  { label: '中等', value: '3', stars: '★★★★★' },
  { label: '较难', value: '4', stars: '★★★★★' },
  { label: '困难', value: '5', stars: '★★★★★' },
]
difficultyLevels.forEach((item, index) => {
  item.stars = '★'.repeat(index + 1) + '☆'.repeat(4 - index)
})
const questionTypeRange = ['全部题型', ...questionTypes.map((item) => item.label)]
const difficultyRange = ['全部难度', ...difficultyLevels.map((item) => item.stars)]

const allAnswersShown = computed(() => {
  return questions.value.length > 0 && questions.value.every(q => showAnswerMap.value[q.id])
})

const knowledgeOptions = computed(() => {
  const result: any[] = []
  knowledgeTree.value.forEach((grade: any) => {
    grade.semesters?.forEach((sem: any) => {
      sem.chapters?.forEach((chapter: any) => {
        chapter.knowledge_points?.forEach((kp: any) => result.push(kp))
      })
    })
  })
  return result
})
const knowledgeRange = computed(() => ['全部知识点', ...knowledgeOptions.value.map((item) => item.name)])
const questionTypeIndex = computed(() => Math.max(0, questionTypes.findIndex((item) => item.value === activeType.value) + 1))
const difficultyIndex = computed(() => Math.max(0, difficultyLevels.findIndex((item) => item.value === activeDifficulty.value) + 1))
const knowledgeIndex = computed(() => Math.max(0, knowledgeOptions.value.findIndex((item) => String(item.id) === String(activeKnowledgePoint.value)) + 1))
const questionTypeLabel = computed(() => activeType.value ? questionTypes.find((item) => item.value === activeType.value)?.label || '全部题型' : '全部题型')
const difficultyLabel = computed(() => activeDifficulty.value ? difficultyLevels.find((item) => item.value === activeDifficulty.value)?.stars || '全部难度' : '全部难度')
const knowledgeLabel = computed(() => activeKnowledgePoint.value ? knowledgeOptions.value.find((item) => String(item.id) === String(activeKnowledgePoint.value))?.name || '全部知识点' : '全部知识点')
const tagPickerRange = computed(() => [
  '全部标签',
  ...allTags.value.map((tag: any) => `${tag.name}（${tag.question_count ?? 0}）`),
])
const tagPickerIndex = computed(() => {
  if (!tagSearch.value) return 0
  const index = allTags.value.findIndex((tag: any) => tag.name === tagSearch.value)
  return index >= 0 ? index + 1 : 0
})
const tagFilterLabel = computed(() => tagSearch.value || '全部标签')

// Reload on every return from the edit page so saved changes are visible
// without a manual refresh, while preserving the current filters and page.
onShow(() => {
  aiModePageActive = true
  loadKnowledgeTree()
  loadTags()
  loadQuestions()
})

// === 知识树 ===
async function loadKnowledgeTree() {
  treeLoading.value = true
  try {
    const res: any = await knowledgeApi.getTree(selectedSubject.value ? { subject: selectedSubject.value } : undefined)
    const treeData = res.data || {}
    const returnedSubjects = Array.isArray(treeData.allowed_subjects) ? treeData.allowed_subjects.filter((subject: unknown): subject is string => typeof subject === 'string' && subject.length > 0) : []
    if (returnedSubjects.length) allowedSubjects.value = returnedSubjects
    const returnedSubject = typeof treeData.selected_subject === 'string' ? treeData.selected_subject : ''
    const nextSubject = returnedSubject || allowedSubjects.value[0] || selectedSubject.value
    if (nextSubject) selectedSubject.value = nextSubject
    const grades = treeData.grades || (Array.isArray(treeData) ? treeData : [])
    knowledgeTree.value = grades.map((g: any) => ({
      ...g,
      expanded: false,
      semesters: (g.semesters || []).map((s: any) => ({
        ...s,
        expanded: false,
        chapters: (s.chapters || []).map((c: any) => ({ ...c, expanded: false })),
      })),
    }))
  } catch (e) {
    console.error('加载知识树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

function toggleNode(node: any) { node.expanded = !node.expanded }
function selectKnowledgePoint(knowledgePointId: unknown) {
  activeKnowledgePoint.value = knowledgePointId === null || knowledgePointId === undefined ? '' : String(knowledgePointId)
  currentPage.value = 1
  jumpPage.value = 1
  loadQuestions()
}
function selectKP(kp: any) { selectKnowledgePoint(kp.id) }
function onTreeSearch() { /* 过滤树节点 */ }
function toggleSelectMode() { selectMode.value = !selectMode.value }
function onSubjectChange(event?: any) {
  selectedSubject.value = allowedSubjects.value[Number(event?.detail?.value ?? subjectIndex.value)] || selectedSubject.value
  activeKnowledgePoint.value = ''
  loadKnowledgeTree()
  loadQuestions()
}

async function loadTags() {
  tagLoading.value = true
  try {
    // No search parameter: the backend returns all tags in the current database.
    const res: any = await getTagList()
    const data = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    allTags.value = data
    if (tagSearch.value && !allTags.value.some((tag: any) => tag.name === tagSearch.value)) {
      tagSearch.value = ''
    }
  } catch (e) {
    console.error('加载标签列表失败:', e)
    uni.showToast({ title: '加载标签失败，请检查网络', icon: 'none' })
  } finally {
    tagLoading.value = false
  }
}

function onTagChange(event?: any) {
  const index = Number(event?.detail?.value ?? 0)
  tagSearch.value = index > 0 ? (allTags.value[index - 1]?.name || '') : ''
  currentPage.value = 1
  jumpPage.value = 1
  loadQuestions()
}

// === 题目加载 ===
async function loadQuestions() {
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value }
    if (activeType.value) params.question_type = activeType.value
    if (activeDifficulty.value) params.difficulty = activeDifficulty.value
    if (activeKnowledgePoint.value) params.knowledge_point_id = activeKnowledgePoint.value
    if (tagSearch.value.trim()) params.tag = tagSearch.value.trim()
    if (uuidSearch.value.trim()) {
      params.keyword = uuidSearch.value.trim()
    }
    if (selectedSubject.value) params.subject = selectedSubject.value

    const res: any = await questionApi.list(params)
    const data = res.data
    questions.value = data?.items || data || []
    selectedQuestionIds.value = selectedQuestionIds.value.filter(id => questions.value.some(q => String(q.id) === id))
    totalCount.value = data?.total || questions.value.length
    totalPages.value = Math.max(1, Math.ceil(totalCount.value / pageSize.value))
    jumpPage.value = currentPage.value
  } catch (e) {
    console.error('加载题目失败:', e)
  } finally {
    loading.value = false
  }
}

function loadMore() { if (currentPage.value < totalPages.value) { currentPage.value++; loadQuestions() } }
function prevPage() { if (currentPage.value > 1) { currentPage.value--; loadQuestions() } }
function nextPage() { if (currentPage.value < totalPages.value) { currentPage.value++; loadQuestions() } }
function pageOptionLabel(page: number) { return page === currentPage.value ? `${page} / ${totalPages.value}页` : `第 ${page} 页` }
function pageSizeOptionLabel(size: number) { return size === pageSize.value ? `${size} / ${totalCount.value}` : `${size} 个 / 页` }
function selectPage(event?: any) {
  currentPage.value = Math.max(1, Math.min(totalPages.value, Number(event?.detail?.value ?? currentPage.value - 1) + 1))
  jumpPage.value = currentPage.value
  loadQuestions()
}
function goToPage() {
  const target = Math.max(1, Math.min(totalPages.value, Number(jumpPage.value) || 1))
  currentPage.value = target
  jumpPage.value = target
  loadQuestions()
}
function changePageSize(event?: any) {
  const index = Number(event?.detail?.value ?? pageSizeOptions.indexOf(pageSize.value))
  pageSize.value = pageSizeOptions[index] || pageSizeOptions[0]
  currentPage.value = 1
  jumpPage.value = 1
  loadQuestions()
}

function onQuestionTypeChange(event: any) {
  activeType.value = questionTypes[Number(event?.detail?.value ?? 0) - 1]?.value || ''
}

function onDifficultyChange(event: any) {
  activeDifficulty.value = difficultyLevels[Number(event?.detail?.value ?? 0) - 1]?.value || ''
}

function onKnowledgePointChange(event: any) {
  selectKnowledgePoint(knowledgeOptions.value[Number(event?.detail?.value ?? 0) - 1]?.id)
}

// === 筛选 ===
function applyFilters() { currentPage.value = 1; jumpPage.value = 1; loadQuestions() }

function resetFilters() {
  activeType.value = ''
  activeDifficulty.value = ''
  activeKnowledgePoint.value = ''
  tagSearch.value = ''
  uuidSearch.value = ''
  currentPage.value = 1
  jumpPage.value = 1
  loadQuestions()
}

// === 答案控制 ===
function toggleAnswer(id: string) { showAnswerMap.value[id] = !showAnswerMap.value[id] }
function toggleAllAnswers() { const allShown = allAnswersShown.value; questions.value.forEach(q => { showAnswerMap.value[q.id] = !allShown }) }

// === 操作 ===
function goEdit(id: string) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }
async function handleRelated(id: string) {
  await relationController.open(String(id))
  if (relationState.error) uni.showToast({ title: relationState.error, icon: 'none' })
}
function closeRelations() { relationController.close() }
async function createRelations() {
  if (!relationState.selectedIds.length) {
    uni.showToast({ title: '请先选择要关联的题目', icon: 'none' })
    return
  }
  const result = await relationController.createSelected()
  if (result.status === 'success') {
    uni.showToast({ title: result.message, icon: 'success' })
  } else if (result.status === 'partial' || result.status === 'invalid') {
    uni.showToast({ title: result.message, icon: 'none', duration: 3000 })
  } else if (result.status === 'failed') {
    uni.showToast({ title: result.message || relationState.error, icon: 'none' })
  }
}
function confirmRemoveRelation(relatedId: string) {
  uni.showModal({
    title: '解除关联',
    content: '解除后仅取消两题的关联，不会删除题目或答案。是否继续？',
    success: async (result) => {
      if (!result.confirm) return
      try {
        const removeResult = await relationController.remove(relatedId)
        if (removeResult.success) {
          uni.showToast({
            title: removeResult.warning ? '已解除关联，列表刷新失败' : removeResult.message,
            icon: removeResult.warning ? 'none' : 'success',
          })
        }
      } catch {
        uni.showToast({ title: relationState.error || '解除关联失败，请稍后重试', icon: 'none' })
      }
    },
  })
}
function goPhotoUpload() { uni.navigateTo({ url: '/pages/teacher/photo-upload' }); addMenuVisible.value = false }

async function addFavorite(id: number) {
  try { await favoriteApi.add(id); uni.showToast({ title: '已加入精选', icon: 'success' }) }
  catch (e: any) { if (e?.statusCode === 409) uni.showToast({ title: '已在精选中', icon: 'none' }) }
}

function toggleQuestionSelection(id: string) {
  const key = String(id)
  const index = selectedQuestionIds.value.indexOf(key)
  if (index >= 0) selectedQuestionIds.value.splice(index, 1)
  else selectedQuestionIds.value.push(key)
}

async function addSelectedToBasket() {
  if (!selectedQuestionIds.value.length) {
    uni.showToast({ title: '请先选择题目', icon: 'none' })
    return
  }
  let favorited = 0
  for (const id of selectedQuestionIds.value) {
    try { await favoriteApi.add(id); favorited++ } catch (e: any) { if (e?.statusCode !== 409) console.warn(e) }
  }
  uni.showToast({ title: `已加入精选 ${favorited} 题`, icon: 'success' })
}

// === 导入 ===
async function handleJsonImport(file: any) {
  uni.showLoading({ title: '正在导入...' })
  try {
    // 处理 uni.chooseFile 返回的对象 { path, name } 或原生 File 对象
    let actualFile: File
    if (file instanceof File) {
      actualFile = file
    } else if (file?.path) {
      // uni.chooseFile 返回的临时文件
      const response = await fetch(file.path)
      const blob = await response.blob()
      actualFile = new File([blob], file.name || 'import.zip', { type: blob.type })
    } else {
      throw new Error('无效的文件对象')
    }
    const res = await importJsonPackage(actualFile)
    uni.hideLoading()
    if (res.code === 0) {
      const data = res.data
      uni.showModal({ title: '导入完成', content: `成功导入 ${data.imported} 题，失败 ${data.errors} 题`, showCancel: false, success: () => { loadQuestions() } })
    } else { uni.showToast({ title: res.message || '导入失败', icon: 'none' }) }
  } catch (e: any) { uni.hideLoading(); uni.showToast({ title: e?.message || '导入失败', icon: 'none' }) }
}

// === 其他 ===
function showAddMenu() { addMenuVisible.value = true }

function goCreateHandout() {
  if (!selectedQuestionIds.value.length) {
    uni.showToast({ title: '请先选择题目', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/pages/teacher/handout-create?questionIds=${encodeURIComponent(selectedQuestionIds.value.join(','))}&subject=${encodeURIComponent(selectedSubject.value)}`,
  })
}

function goKnowledgeMatches() { uni.navigateTo({ url: '/pages/teacher/knowledge-matches' }) }
function goHandoutList() { uni.navigateTo({ url: '/pages/teacher/handout-list' }) }
function toggleViewMode() { viewMode.value = viewMode.value === 'compact' ? 'detail' : 'compact' }
async function handleRefresh() {
  currentPage.value = 1
  showAnswerMap.value = {}
  await loadQuestions()
  uni.showToast({ title: '已刷新', icon: 'success', duration: 1000 })
}
function handleBasket() { addSelectedToBasket() }
async function handleBatchAi(model?: string) {
  if (!selectedQuestionIds.value.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return }
  try { await questionApi.batchAi(selectedQuestionIds.value, model); uni.showToast({ title: '批量AI任务已提交', icon: 'success' }) }
  catch { uni.showToast({ title: '批量AI任务提交失败', icon: 'none' }) }
}
async function handleAiExplore() {
  if (!selectedQuestionIds.value.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return }
  try {
    await Promise.all(selectedQuestionIds.value.map(id => aiProcessProbe(id)))
    uni.showToast({ title: 'AI探索任务已提交', icon: 'success' })
  } catch { uni.showToast({ title: 'AI探索提交失败', icon: 'none' }) }
}
async function handleAiMode(mode: 'A' | 'B' | 'C') {
  const selectedIds = selectedQuestionIds.value || []
  const fallbackModeState = { value: { A: false, B: false, C: false } }
  const fallbackTaskState = { value: { A: [], B: [], C: [] } }
  const fallbackGenerationState = { value: { A: null, B: null, C: null } }
  const modeRunningRef = typeof aiModeRunning === 'undefined' ? fallbackModeState : aiModeRunning
  const modeTaskIdsRef = typeof aiModeTaskIds === 'undefined' ? fallbackTaskState : aiModeTaskIds
  const modeRunGenerationRef = typeof aiModeRunGeneration === 'undefined' ? fallbackGenerationState : aiModeRunGeneration
  const requestGeneration = typeof aiModeGeneration === 'number' ? aiModeGeneration : 0
  const isCurrent = typeof isCurrentAiModeGeneration === 'function'
    ? isCurrentAiModeGeneration
    : () => true
  const loadQuestionsSafely = typeof loadQuestions === 'function'
    ? loadQuestions
    : () => Promise.resolve()
  const pollSafely = async (taskId, taskMode, generation) => {
    if (typeof pollAiModeTask === 'function') {
      return pollAiModeTask(taskId, taskMode, generation)
    }
    return 'in_progress'
  }

  if (!selectedIds.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return }
  if (modeRunningRef.value[mode]) {
    uni.showToast({ title: `AI-${mode}模式正在处理中`, icon: 'none' })
    return
  }
  if (!isCurrent(requestGeneration)) return
  modeRunningRef.value[mode] = true
  modeRunGenerationRef.value[mode] = requestGeneration
  modeTaskIdsRef.value[mode] = []
  try {
    const submissions = await Promise.all(selectedIds.map(async (id) => {
      try {
        const response = await questionApi.aiProcessMode(id, mode)
        if (!isCurrent(requestGeneration)) return null
        const taskId = response?.data?.task_id
        if (response?.success === false) return null
        return String(taskId || id)
      } catch {
        return null
      }
    }))
    if (!isCurrent(requestGeneration)) return

    const taskIds = submissions.filter(taskId => Boolean(taskId))
    modeTaskIdsRef.value[mode] = taskIds
    if (!taskIds.length) {
      uni.showToast({ title: `AI-${mode}模式提交失败`, icon: 'none' })
      return
    }
    if (taskIds.length < selectedIds.length) {
      uni.showToast({ title: `AI-${mode}部分任务提交失败`, icon: 'none' })
    } else {
      uni.showToast({ title: `AI-${mode}模式任务已提交`, icon: 'success' })
    }

    const terminalStatuses = await Promise.all(
      taskIds.map(taskId => pollSafely(taskId, mode, requestGeneration))
    )
    if (!isCurrent(requestGeneration)) return
    const completed = terminalStatuses.some(
      status => status === 'complete' || status === 'partial'
    )
    if (completed) {
      await loadQuestionsSafely()
      if (!isCurrent(requestGeneration)) return
    }
    if (terminalStatuses.some(status => status === 'failed')) {
      uni.showToast({ title: `AI-${mode}模式处理失败，请稍后重试`, icon: 'none' })
    } else if (terminalStatuses.some(status => status === 'skipped')) {
      uni.showToast({ title: `AI-${mode}模式任务已跳过，请刷新后重试`, icon: 'none' })
    } else if (completed) {
      uni.showToast({ title: `AI-${mode}模式处理完成`, icon: 'success' })
    }
  } finally {
    if (modeRunGenerationRef.value[mode] === requestGeneration) {
      modeRunningRef.value[mode] = false
      modeTaskIdsRef.value[mode] = []
      modeRunGenerationRef.value[mode] = null
    }
  }
}

function waitForAiModePoll(poll: AiModePoll, milliseconds: number): Promise<boolean> {
  if (poll.cancelled || !isCurrentAiModeGeneration(poll.generation)) {
    return Promise.resolve(false)
  }
  return new Promise<boolean>((resolve) => {
    const release = () => {
      poll.timer = undefined
      poll.releaseDelay = undefined
      resolve(!poll.cancelled && isCurrentAiModeGeneration(poll.generation))
    }
    poll.releaseDelay = release
    if (poll.cancelled || !isCurrentAiModeGeneration(poll.generation)) {
      release()
      return
    }
    poll.timer = setTimeout(release, milliseconds)
  })
}

async function pollAiModeTask(
  taskId: string,
  mode: AiMode,
  generation: number,
): Promise<AiModeTerminalStatus> {
  if (!isCurrentAiModeGeneration(generation)) return 'cancelled'
  const poll: AiModePoll = { taskId, mode, generation, cancelled: false }
  aiModePolls.set(taskId, poll)
  try {
    for (let attempt = 0; attempt < 900; attempt += 1) {
      const shouldPoll = await waitForAiModePoll(poll, attempt === 0 ? 1000 : 5000)
      if (!shouldPoll || poll.cancelled || !isCurrentAiModeGeneration(generation)) return 'cancelled'
      try {
        const response: any = await questionApi.getTaskStatus(taskId)
        if (poll.cancelled || !isCurrentAiModeGeneration(generation)) return 'cancelled'
        if (response?.success === false) return 'failed'
        const status = response?.data?.status
        if (status === 'complete' || status === 'partial' || status === 'failed' || status === 'skipped') {
          return status
        }
      } catch {
        if (poll.cancelled || !isCurrentAiModeGeneration(generation)) return 'cancelled'
        if (attempt >= 899) return 'failed'
      }
    }
    return 'failed'
  } finally {
    if (poll.timer) clearTimeout(poll.timer)
    if (aiModePolls.get(taskId) === poll) aiModePolls.delete(taskId)
  }
}

function stopAiModePolling() {
  aiModeGeneration += 1
  aiModePageActive = false
  aiModePolls.forEach((poll) => {
    poll.cancelled = true
    if (poll.timer) clearTimeout(poll.timer)
    poll.releaseDelay?.()
  })
  aiModePolls.clear()
  ;(['A', 'B', 'C'] as AiMode[]).forEach((mode) => {
    aiModeRunning.value[mode] = false
    aiModeTaskIds.value[mode] = []
    aiModeRunGeneration.value[mode] = null
  })
}

onUnload(stopAiModePolling)
onHide(stopAiModePolling)
onUnmounted(stopAiModePolling)

function openAiAnswer(question: any, mode: 'ALL' | 'A' | 'B' | 'C' = 'ALL') {
  answerQuestion.value = question
  answerMode.value = mode
  answerVisible.value = true
}

async function refreshAnswerQuestion() {
  const questionId = answerQuestion.value?.id
  await loadQuestions()
  if (questionId) {
    answerQuestion.value = questions.value.find(item => String(item.id) === String(questionId)) || answerQuestion.value
  }
}

async function openTagEditor(question: any) {
  editingQuestion.value = question
  tagVisible.value = true
  newTag.value = ''
  try { const res: any = await getQuestionTags(String(question.id)); questionTags.value = res.data || [] }
  catch { questionTags.value = [] }
}
async function addQuestionTagToCurrent() {
  if (!editingQuestion.value || !newTag.value.trim()) return
  try { await addQuestionTag(String(editingQuestion.value.id), { tag_name: newTag.value.trim() }); await openTagEditor(editingQuestion.value); newTag.value = '' }
  catch { uni.showToast({ title: '标签添加失败', icon: 'none' }) }
}
async function removeQuestionTagFromCurrent(tagId: string) {
  if (!editingQuestion.value) return
  try { await removeQuestionTag(String(editingQuestion.value.id), tagId); await openTagEditor(editingQuestion.value) }
  catch { uni.showToast({ title: '标签移除失败', icon: 'none' }) }
}
</script>

<style scoped>
.question-bank { display: flex; flex-direction: column; width: 100%; height: 100%; min-width: 0; min-height: 0; box-sizing: border-box; background: #f0f2f5; overflow: hidden; }

.pagination { display: none; }
.pagination-new { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.page-info { font-size: 13px; color: #606266; }
.page-total, .page-size-label { font-size: 12px; color: #606266; }
.page-size-select, .jump-page-input { height: 26px; box-sizing: border-box; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 12px; color: #606266; background: #fff; }
.page-size-select { width: 58px; }
.jump-page-input { width: 54px; padding: 0 6px; }
.page-picker, .page-size-picker { display: flex; align-items: center; justify-content: center; height: 28px; box-sizing: border-box; min-width: 0; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 12px; line-height: 1.2; text-align: center; color: #303133; background: #fff; padding: 0 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-picker { width: 92px; }
.page-size-picker { width: 112px; }

.main-layout { display: flex; flex: 1 1 auto; width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: hidden; }

.left-panel { width: 260px; box-sizing: border-box; background: #fff; border-right: 1px solid #e4e7ed; display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0; }
.left-panel .tree-content { overflow-y: auto; flex: 1; }
.subject-selector { padding: 12px; border-bottom: 1px solid #f0f0f0; }
.subject-select { display: flex; align-items: center; justify-content: center; width: 100%; min-width: 0; box-sizing: border-box; padding: 6px 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; line-height: 1.2; text-align: center; background: #ecf5ff; color: #409eff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-header { display: flex; justify-content: space-between; align-items: center; padding: 12px; }
.tree-title { font-size: 14px; font-weight: 600; color: #303133; }
.tree-search { width: 120px; padding: 4px 8px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 12px; }
.tree-actions { display: flex; gap: 6px; padding: 0 12px 8px; }
.tree-content { flex: 1; overflow-y: auto; padding: 0 8px 12px; }
.tree-node { display: flex; align-items: center; padding: 5px 8px; border-radius: 4px; cursor: pointer; font-size: 13px; color: #606266; }
.tree-node:hover { background: #f5f7fa; }
.tree-node.active { background: #ecf5ff; color: #409eff; font-weight: 500; }
.arrow { margin-right: 4px; font-size: 10px; color: #909399; flex-shrink: 0; width: 12px; }
.label { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.count { font-size: 10px; color: #909399; margin-left: 4px; flex-shrink: 0; }
.tree-children { padding-left: 12px; }

.center-panel { flex: 1 1 auto; display: flex; flex-direction: column; overflow: hidden; min-width: 0; min-height: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; min-width: 0; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.panel-title { font-size: 16px; font-weight: 600; color: #303133; }
.total-count { font-size: 13px; color: #909399; margin-left: 8px; }
.header-right { display: flex; align-items: center; justify-content: flex-end; gap: 8px; min-width: 0; flex-wrap: wrap; }
.btn-import { background: #fff; color: #409eff; border: 1px solid #409eff; border-radius: 4px; padding: 6px 14px; font-size: 13px; }
.btn-add { background: #409eff; color: #fff; border: none; border-radius: 4px; padding: 6px 14px; font-size: 13px; }

.quick-filters { padding: 10px 20px; background: #fff; border-bottom: 1px solid #f0f0f0; }
.quick-filters { display: flex; align-items: center; gap: 8px; min-width: 0; box-sizing: border-box; flex-wrap: wrap; overflow: visible; }
.filter-group { display: flex; align-items: center; gap: 8px; min-width: 0; margin-bottom: 0; flex: 0 1 auto; flex-wrap: wrap; }
.filter-label { font-size: 12px; color: #909399; }
.filter-select { display: flex; align-items: center; justify-content: center; width: 88px; min-width: 0; box-sizing: border-box; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px; background: #fff; color: #606266; font-size: 12px; line-height: 1.2; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-filter-select { width: 180px; }
.tag-refresh-btn { margin: 0; color: #409eff; background: #fff; border: 1px solid #dcdfe6; }
.tag-search { width: 130px; max-width: 100%; box-sizing: border-box; height: 28px; padding: 0 8px; border: 1px solid #dcdfe6; border-radius: 4px; background: #fff; color: #606266; font-size: 12px; }
.uuid-search {
  width: 340px;
  max-width: 100%;
  min-width: 180px;
  flex: 1 1 220px;
  height: 28px;
  box-sizing: border-box;
  padding: 0 10px;
  border: 1px solid #c0c4cc;
  border-radius: 4px;
  background: #fff;
  color: #303133;
  font-size: 12px;
  outline: none;
}
.uuid-search:focus { border-color: #409eff; box-shadow: 0 0 0 1px rgba(64, 158, 255, .15); }
.reset-filter-btn {
  background: #fff;
  color: #606266;
  border: 1px solid #c0c4cc;
  border-radius: 4px;
  padding: 0 14px;
  height: 28px;
  line-height: 26px;
  font-size: 12px;
}
.reset-filter-btn:active { background: #f5f7fa; }
.filter-chip { padding: 3px 10px; border-radius: 10px; font-size: 11px; background: #f0f0f0; cursor: pointer; }
.filter-chip.active { background: #409eff; color: #fff; }

.question-scroll { flex: 1 1 auto; width: 100%; min-width: 0; box-sizing: border-box; overflow-y: auto; padding: 10px; background: #f5f7fa; }
.loading-more, .empty-state { text-align: center; padding: 40px 0; color: #909399; }
.loading { text-align: center; color: #909399; padding: 20px 0; }
.modal-overlay { position: fixed; inset: 0; z-index: 1001; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.45); }
.data-modal { width: 520px; max-width: 90vw; max-height: 80vh; overflow-y: auto; padding: 20px; background: #fff; border-radius: 8px; }
.modal-title { margin-bottom: 16px; font-size: 18px; font-weight: 600; color: #303133; }
.related-item { padding: 10px 0; border-bottom: 1px solid #f0f0f0; color: #606266; cursor: pointer; }
.relation-modal { min-height: 280px; }
.relation-modal-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.relation-modal-header .modal-title { margin-bottom: 0; }
.relation-close { flex: 0 0 auto; }
.relation-tabs { display: flex; gap: 8px; margin: 16px 0; }
.relation-tabs button { flex: 1; }
.relation-tab-active { color: #fff; background: #409eff; border-color: #409eff; }
.relation-list { max-height: 46vh; overflow-y: auto; }
.relation-pagination { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 12px; color: #606266; font-size: 13px; }
.relation-candidate-item, .relation-linked-item { display: flex; align-items: center; gap: 10px; }
.relation-item-main { display: flex; flex: 1; min-width: 0; flex-direction: column; gap: 4px; }
.relation-item-meta { color: #909399; font-size: 12px; }
.relation-empty { padding: 24px 0; text-align: center; color: #909399; }
.relation-error { margin-bottom: 10px; padding: 8px 10px; border-radius: 4px; color: #f56c6c; background: #fef0f0; }
.relation-warning { margin-bottom: 10px; padding: 8px 10px; border-radius: 4px; color: #e6a23c; background: #fdf6ec; }
.relation-remove { flex: 0 0 auto; color: #f56c6c; }
.tag-editor { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.tag-chip { padding: 4px 8px; border-radius: 12px; background: #ecf5ff; color: #409eff; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

@media (max-width: 1100px) {
  .main-layout { overflow-y: auto; }
  .left-panel { width: 220px; }
  .panel-header { align-items: flex-start; flex-wrap: wrap; }
  .header-right { width: 100%; justify-content: flex-start; }
  .quick-filters { align-items: flex-start; }
  .quick-filters > .filter-group:last-child { flex: 1 1 100%; }
  .uuid-search { flex: 1 1 220px; }
}

@media (max-width: 768px) {
  .main-layout { flex-direction: column; overflow-y: auto; }
  .left-panel { width: 100%; max-height: 280px; border-right: 0; border-bottom: 1px solid #e4e7ed; }
  .center-panel { min-height: 520px; overflow: visible; }
  .panel-header { padding: 10px 12px; }
  .quick-filters { padding: 10px 12px; }
  .filter-group { width: 100%; }
  .filter-select { flex: 1 1 100px; }
  .tag-search, .uuid-search { flex: 1 1 150px; }
}
</style>
