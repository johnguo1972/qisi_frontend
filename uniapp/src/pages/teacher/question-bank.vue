<template>
  <view class="question-bank">
    <view class="main-layout">
      <!-- 左侧：知识树 -->
      <view class="left-panel">
        <view class="subject-selector">
          <picker mode="selector" :range="subjectRange" :value="subjectIndex" @change="onSubjectChange"><view class="subject-select">{{ selectedSubject === 'physics' ? '物理' : '数学' }}</view></picker>
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
                        :class="['tree-node kp-node', { active: selectedKP === kp.id }]"
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
            <input v-model="tagSearch" class="tag-search" placeholder="自定义标签" />
            <input v-model="uuidSearch" class="uuid-search" placeholder="按UUID模糊查询" />
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
            :show-answer="showAnswerMap[q.id]"
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
        @refresh="handleRefresh"
        @toggle-answer="toggleAllAnswers"
        :compact-mode="viewMode === 'compact'"
        @toggle-mode="toggleViewMode"
        @basket="handleBasket"
        @batch-ai="handleBatchAi"
        @ai-explore="handleAiExplore"
        @ai-mode-a="handleAiModeA"
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

    <view v-if="relatedVisible" class="modal-overlay" @click.self="relatedVisible = false">
      <view class="data-modal"><view class="modal-title">类似题</view><view v-if="relatedLoading">加载中...</view><view v-else-if="!relatedQuestions.length">暂无符合条件的类似题</view><view v-for="item in relatedQuestions" :key="item.id" class="related-item" @click="goEdit(item.id)">{{ item.question_no }}：{{ item.stem_preview || item.stem }}</view><button size="mini" @click="relatedVisible = false">关闭</button></view>
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
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { questionApi, importJsonPackage, getQuestionTags, addQuestionTag, removeQuestionTag } from '@/api/questions'
import { knowledgeApi } from '@/api/knowledge'
import { favoriteApi } from '@/api/favorites'
import { useUserStore } from '@/store/index.ts'

import QuestionDetailCard from '@/components/QuestionDetailCard.vue'
import AddMenuModal from '@/components/AddMenuModal.vue'
import RightActionPanel from '@/components/RightActionPanel.vue'
import AiAnswerModal from '@/components/AiAnswerModal.vue'

const userStore = useUserStore()

// === 状态 ===
const selectedSubject = ref('physics')
const selectedKP = ref<number | null>(null)
const activeKnowledgePoint = ref('')
const tagSearch = ref('')
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
const subjectRange = ['物理', '数学']
const subjectIndex = computed(() => selectedSubject.value === 'math' ? 1 : 0)
const pageRangeLabels = computed(() => pageNumbers.value.map(pageOptionLabel))
const pageSizeRange = pageSizeOptions.map((size) => `${size} 个 / 页`)

const activeType = ref('')
const activeDifficulty = ref('')
const showAnswerMap = ref<Record<string, boolean>>({})
const selectedQuestionIds = ref<string[]>([])
const viewMode = ref<'compact' | 'detail'>('detail')

const addMenuVisible = ref(false)
const relatedVisible = ref(false)
const relatedLoading = ref(false)
const relatedQuestions = ref<any[]>([])
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

// Reload on every return from the edit page so saved changes are visible
// without a manual refresh, while preserving the current filters and page.
onShow(() => {
  loadKnowledgeTree()
  loadQuestions()
})

// === 知识树 ===
async function loadKnowledgeTree() {
  treeLoading.value = true
  try {
    const subject = userStore.userInfo?.subject || selectedSubject.value
    const res: any = await knowledgeApi.getTree({ subject })
    const grades = res.data?.grades || res.data || []
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
function selectKP(kp: any) { selectedKP.value = kp.id; currentPage.value = 1; jumpPage.value = 1; loadQuestions() }
function onTreeSearch() { /* 过滤树节点 */ }
function toggleSelectMode() { selectMode.value = !selectMode.value }
function onSubjectChange(event?: any) {
  selectedSubject.value = Number(event?.detail?.value ?? subjectIndex.value) === 1 ? 'math' : 'physics'
  loadKnowledgeTree()
  loadQuestions()
}

// === 题目加载 ===
async function loadQuestions() {
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value }
    if (selectedKP.value) params.knowledge_point_id = selectedKP.value
    if (activeType.value) params.question_type = activeType.value
    if (activeDifficulty.value) params.difficulty = activeDifficulty.value
    if (activeKnowledgePoint.value) params.knowledge_point_id = activeKnowledgePoint.value
    if (tagSearch.value.trim()) params.tag = tagSearch.value.trim()
    if (uuidSearch.value.trim()) params.uuid = uuidSearch.value.trim()
    const subject = userStore.userInfo?.subject || selectedSubject.value
    if (subject) params.subject = subject

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
  activeKnowledgePoint.value = knowledgeOptions.value[Number(event?.detail?.value ?? 0) - 1]?.id || ''
}

// === 筛选 ===
function applyFilters() { currentPage.value = 1; jumpPage.value = 1; loadQuestions() }

function resetFilters() {
  selectedKP.value = null
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
  relatedVisible.value = true
  relatedLoading.value = true
  try { const res: any = await questionApi.similar(id); relatedQuestions.value = res.data || [] }
  catch { relatedQuestions.value = [] }
  finally { relatedLoading.value = false }
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
  catch { uni.showToast({ title: '批量AI提交失败', icon: 'none' }) }
}
function handleAiExplore() { handleBatchAi() }
async function handleAiModeA() {
  if (!selectedQuestionIds.value.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return }
  try {
    await Promise.all(selectedQuestionIds.value.map(id => questionApi.aiProcessMode(id, 'A')))
    uni.showToast({ title: 'AI-A模式任务已提交', icon: 'success' })
  } catch { uni.showToast({ title: 'AI-A模式提交失败', icon: 'none' }) }
}

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
