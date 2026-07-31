<template>
  <view class="question-bank">
    <!-- 顶部筛选工具栏 -->
    <view class="filter-bar">
      <view class="filter-left">
        <view class="filter-chips">
          <view
            v-for="item in filterItems"
            :key="item.key"
            :class="['chip', { active: item.active }]"
            @click="toggleFilter(item.key)"
          >
            {{ item.label }}
            <text v-if="item.active" class="chip-remove">&times;</text>
          </view>
        </view>
      </view>
      <view class="filter-right">
        <view class="pagination">
          <select v-model.number="currentPage" class="page-select" @change="goToPage">
            <option v-for="page in totalPages" :key="page" :value="page">第 {{ page }} 页</option>
          </select>
          <select v-model.number="pageSize" class="page-size-select" @change="changePageSize">
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }} 条/页</option>
          </select>
          <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
          <text class="page-info">{{ currentPage }}/{{ totalPages }}页</text>
          <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
        </view>
        <button size="mini" @click="resetFilters">重置</button>
      </view>
    </view>

    <view class="main-layout">
      <!-- 左侧：知识树 -->
      <view class="left-panel">
        <view class="subject-selector">
          <select v-model="selectedSubject" @change="onSubjectChange" class="subject-select">
            <option value="physics">初中物理</option>
            <option value="math">数学</option>
          </select>
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
          <button size="mini" type="primary" @click="queryRelatedData">查询相关数据</button>
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
            <button class="btn-import" @click="showImportModal">&#128229; 导入题目</button>
            <button class="btn-add" @click="showAddMenu">+ 新增</button>
          </view>
        </view>

        <!-- 题型/难度快捷筛选 -->
        <view class="quick-filters">
          <view class="filter-group">
            <text class="filter-label">题型：</text>
            <view
              v-for="t in questionTypes"
              :key="t.value"
              :class="['filter-chip', { active: activeType === t.value }]"
              @click="setType(t.value)"
            >
              {{ t.label }}
            </view>
          </view>
          <view class="filter-group">
            <text class="filter-label">难度：</text>
            <view
              v-for="d in difficultyLevels"
              :key="d.value"
              :class="['filter-chip', { active: activeDifficulty === d.value }]"
              @click="setDifficulty(d.value)"
            >
              {{ d.stars }}
            </view>
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
            @whiteboard="goEdit(q.id)"
            @related="handleRelated"
            @toggle-answer="toggleAnswer(q.id)"
            @add-favorite="addFavorite(q.id)"
            @add-basket="addSelectedToBasket"
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
        :basket-count="basketCount"
        :all-shown="allAnswersShown"
        @random="handleRandom"
        @query-params="showQueryParams"
        @refresh="handleRefresh"
        @toggle-answer="toggleAllAnswers"
        @share-multiple="handleShareMultiple"
        @share-history="handleShareHistory"
        @basket="handleBasket"
        @ai-process="handleAiProcess"
      />
    </view>

    <!-- 导入弹窗 -->
    <ImportModal
      v-if="importVisible"
      @close="importVisible = false"
      @photo-import="handlePhotoImport"
      @file-import="handleFileImport"
      @json-import="handleJsonImport"
    />

    <!-- 新增菜单 -->
    <AddMenuModal
      v-if="addMenuVisible"
      @close="addMenuVisible = false"
      @photo="goPhotoUpload"
      @file="handleFileImport"
      @json="handleJsonImport"
      @manual="goManualCreate"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { questionApi, importJsonPackage, getBasket, addToBasket as apiAddToBasket } from '@/api/questions'
import { knowledgeApi } from '@/api/knowledge'
import { favoriteApi } from '@/api/favorites'
import { useUserStore } from '@/store/index.ts'

import QuestionDetailCard from '@/components/QuestionDetailCard.vue'
import ImportModal from '@/components/ImportModal.vue'
import AddMenuModal from '@/components/AddMenuModal.vue'
import RightActionPanel from '@/components/RightActionPanel.vue'

const userStore = useUserStore()

// === 状态 ===
const selectedSubject = ref('physics')
const selectedKP = ref<number | null>(null)
const knowledgeTree = ref<any[]>([])
const treeLoading = ref(false)
const treeSearch = ref('')
const selectMode = ref(false)

const questions = ref<any[]>([])
const loading = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const pageSize = ref(20)
const pageSizeOptions = [10, 20, 30, 50]

const activeType = ref('')
const activeDifficulty = ref('')
const showAnswerMap = ref<Record<string, boolean>>({})
const basketCount = ref(0)
const selectedQuestionIds = ref<string[]>([])

const importVisible = ref(false)
const addMenuVisible = ref(false)

// === 筛选项 ===
const filterItems = ref([
  { key: 'question', label: '题目', active: false },
  { key: 'knowledge', label: '知识', active: false },
  { key: 'year', label: '年份', active: false },
  { key: 'title', label: '标题', active: false },
  { key: 'questionNo', label: '题号', active: false },
  { key: 'tag', label: '标签', active: false },
  { key: 'kp', label: '知识点', active: false },
  { key: 'keyword', label: '关键词查询', active: false },
  { key: 'sort', label: '排序', active: false },
  { key: 'id', label: 'ID', active: false },
  { key: 'similar', label: '相似题', active: false },
])

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

const allAnswersShown = computed(() => {
  return questions.value.length > 0 && questions.value.every(q => showAnswerMap.value[q.id])
})

// === 初始化 ===
onMounted(() => {
  loadKnowledgeTree()
  loadQuestions()
  loadBasketCount()
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
function selectKP(kp: any) { selectedKP.value = kp.id; currentPage.value = 1; loadQuestions() }
function onTreeSearch() { /* 过滤树节点 */ }
function toggleSelectMode() { selectMode.value = !selectMode.value }
function queryRelatedData() { /* 查询相关数据 */ }
function onSubjectChange() { loadKnowledgeTree(); loadQuestions() }

// === 题目加载 ===
async function loadQuestions() {
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value }
    if (selectedKP.value) params.knowledge_point_id = selectedKP.value
    if (activeType.value) params.question_type = activeType.value
    if (activeDifficulty.value) params.difficulty = activeDifficulty.value
    const subject = userStore.userInfo?.subject || selectedSubject.value
    if (subject) params.subject = subject

    const res: any = await questionApi.list(params)
    const data = res.data
    questions.value = data?.items || data || []
    selectedQuestionIds.value = selectedQuestionIds.value.filter(id => questions.value.some(q => String(q.id) === id))
    totalCount.value = data?.total || questions.value.length
    totalPages.value = Math.max(1, Math.ceil(totalCount.value / pageSize.value))
  } catch (e) {
    console.error('加载题目失败:', e)
  } finally {
    loading.value = false
  }
}

function loadMore() { if (currentPage.value < totalPages.value) { currentPage.value++; loadQuestions() } }
function prevPage() { if (currentPage.value > 1) { currentPage.value--; loadQuestions() } }
function nextPage() { if (currentPage.value < totalPages.value) { currentPage.value++; loadQuestions() } }
function goToPage() { loadQuestions() }
function changePageSize() { currentPage.value = 1; loadQuestions() }

// === 筛选 ===
function toggleFilter(key: string) { const item = filterItems.value.find(f => f.key === key); if (item) item.active = !item.active }
function setType(val: string) { activeType.value = activeType.value === val ? '' : val; currentPage.value = 1; loadQuestions() }
function setDifficulty(val: string) { activeDifficulty.value = activeDifficulty.value === val ? '' : val; currentPage.value = 1; loadQuestions() }
function resetFilters() { activeType.value = ''; activeDifficulty.value = ''; selectedKP.value = null; currentPage.value = 1; filterItems.value.forEach(f => f.active = false); loadQuestions() }

// === 答案控制 ===
function toggleAnswer(id: string) { showAnswerMap.value[id] = !showAnswerMap.value[id] }
function toggleAllAnswers() { const allShown = allAnswersShown.value; questions.value.forEach(q => { showAnswerMap.value[q.id] = !allShown }) }

// === 操作 ===
function goEdit(id: string) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }
function handleRelated() { uni.showToast({ title: '关联功能开发中', icon: 'none' }) }
function goPhotoUpload() { uni.navigateTo({ url: '/pages/teacher/photo-upload' }); addMenuVisible.value = false }
function goManualCreate() { addMenuVisible.value = false; uni.showToast({ title: '手动创建功能开发中', icon: 'none' }) }

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
  let added = 0
  let favorited = 0
  for (const id of selectedQuestionIds.value) {
    try { await apiAddToBasket(id); added++ } catch (e: any) { if (e?.statusCode !== 409) console.warn(e) }
    try { await favoriteApi.add(id); favorited++ } catch (e: any) { if (e?.statusCode !== 409) console.warn(e) }
  }
  await loadBasketCount()
  uni.showToast({ title: `篮子 ${added} 题，精选 ${favorited} 题`, icon: 'success' })
}

async function addToBasket(id: number) {
  try { await apiAddToBasket(String(id)); basketCount.value++; uni.showToast({ title: '已加入篮子', icon: 'success' }) }
  catch (e) { uni.showToast({ title: '加入失败', icon: 'none' }) }
}

async function loadBasketCount() { try { const res = await getBasket(); basketCount.value = res.data?.length || 0 } catch {} }

// === 导入 ===
function showImportModal() { importVisible.value = true }
function handlePhotoImport() { importVisible.value = false; goPhotoUpload() }
function handleFileImport() { importVisible.value = false; uni.navigateTo({ url: '/pages/teacher/import' }) }

async function handleJsonImport(file: any) {
  importVisible.value = false
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
function showQueryParams() { uni.showToast({ title: '查询参数功能开发中', icon: 'none' }) }
function handleRandom() { uni.showToast({ title: '随机选题功能开发中', icon: 'none' }) }
async function handleRefresh() {
  currentPage.value = 1
  showAnswerMap.value = {}
  await loadQuestions()
  uni.showToast({ title: '已刷新', icon: 'success', duration: 1000 })
}
function handleShareMultiple() { uni.showToast({ title: '分享功能开发中', icon: 'none' }) }
function handleShareHistory() { uni.showToast({ title: '分享历史功能开发中', icon: 'none' }) }
function handleBasket() { addSelectedToBasket() }
async function handleAiProcess() {
  uni.showLoading({ title: 'AI处理中...' })
  if (!selectedQuestionIds.value.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return }
  for (const id of selectedQuestionIds.value) {
    try {
      const started: any = await questionApi.aiProcess(id)
      const taskId = started?.data?.task_id || started?.data?.data?.task_id
      if (taskId) {
        for (let attempt = 0; attempt < 120; attempt++) {
          await new Promise(resolve => setTimeout(resolve, 1000))
          const status: any = await questionApi.getTaskStatus(taskId)
          const state = status?.data?.status || status?.data?.data?.status
          if (state === 'complete' || state === 'partial' || state === 'failed') break
        }
      }
    } catch (e) { console.warn('AI处理失败', id, e) }
  }
  uni.hideLoading()
  await loadKnowledgeTree()
  await loadQuestions()
  uni.showToast({ title: `已提交 ${selectedQuestionIds.value.length} 题AI处理`, icon: 'success' })
}
</script>

<style scoped>
.question-bank { display: flex; flex-direction: column; height: 100vh; background: #f0f2f5; overflow: hidden; }

.filter-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.filter-left { flex: 1; min-width: 0; }
.filter-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.filter-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { padding: 4px 12px; border-radius: 12px; font-size: 12px; background: #f0f0f0; cursor: pointer; display: flex; align-items: center; gap: 4px; }
.chip.active { background: #409eff; color: #fff; }
.chip-remove { font-size: 14px; margin-left: 2px; }
.pagination { display: flex; align-items: center; gap: 8px; }
.page-info { font-size: 13px; color: #606266; }
.page-select, .page-size-select {
  height: 28px; min-width: 88px; padding: 0 8px;
  border: 1px solid #dcdfe6; border-radius: 4px;
  background: #fff; color: #606266; font-size: 12px;
}
.page-size-select { min-width: 82px; }

.main-layout { display: flex; flex: 1; overflow: hidden; }

.left-panel { width: 260px; background: #fff; border-right: 1px solid #e4e7ed; display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0; }
.left-panel .tree-content { overflow-y: auto; flex: 1; }
.subject-selector { padding: 12px; border-bottom: 1px solid #f0f0f0; }
.subject-select { width: 100%; padding: 6px 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; background: #ecf5ff; color: #409eff; }
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

.center-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.panel-title { font-size: 16px; font-weight: 600; color: #303133; }
.total-count { font-size: 13px; color: #909399; margin-left: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.btn-import { background: #fff; color: #409eff; border: 1px solid #409eff; border-radius: 4px; padding: 6px 14px; font-size: 13px; }
.btn-add { background: #409eff; color: #fff; border: none; border-radius: 4px; padding: 6px 14px; font-size: 13px; }

.quick-filters { padding: 10px 20px; background: #fff; border-bottom: 1px solid #f0f0f0; }
.filter-group { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.filter-label { font-size: 12px; color: #909399; }
.filter-chip { padding: 3px 10px; border-radius: 10px; font-size: 11px; background: #f0f0f0; cursor: pointer; }
.filter-chip.active { background: #409eff; color: #fff; }

.question-scroll { flex: 1; overflow-y: auto; padding: 16px 20px; background: #f5f7fa; }
.loading-more, .empty-state { text-align: center; padding: 40px 0; color: #909399; }
.loading { text-align: center; color: #909399; padding: 20px 0; }
</style>
