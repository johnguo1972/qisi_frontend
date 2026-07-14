<template>
  <view class="favorites">

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

      <!-- Right: Favorites list -->
      <view class="panel">
        <view class="panel-header">
          <text class="panel-title">我的精选</text>
          <text v-if="selectedKP" class="filter-hint">已筛选知识点 · <text class="clear-link" @click="clearKPFilter">清除</text></text>
        </view>

        <!-- Search bar -->
        <view class="search-bar">
          <input
            class="search-input"
            v-model="searchQuery"
            placeholder="搜索题干关键词..."
            @confirm="loadFavorites"
          />
          <button size="mini" type="primary" @click="loadFavorites">搜索</button>
        </view>

        <!-- Filter bar: question type chips -->
        <view class="filter-bar">
          <text class="filter-label">题型：</text>
          <view v-for="opt in typeOptions" :key="opt.value"
                :class="['filter-chip', {active: currentType === opt.value}]"
                @click="setType(opt.value)">
            {{ opt.label }}
          </view>
        </view>

        <!-- Content -->
        <view v-if="loading" class="loading">加载中...</view>
        <view v-else-if="favorites.length === 0" class="empty">
          <text>还没有精选试题，去题库列表添加吧</text>
        </view>
        <view v-else class="question-table">
          <view class="table-header">
            <text class="col col-no">编号</text>
            <text class="col col-type">题型</text>
            <text class="col col-diff">难度</text>
            <text class="col col-stem">题干</text>
            <text class="col col-kp">知识点</text>
            <text class="col col-action">操作</text>
          </view>
          <view v-for="f in favorites" :key="f.id" class="table-row">
            <text class="col col-no">{{ f.question_no }}</text>
            <text class="col col-type">{{ f.question_type_text || '-' }}</text>
            <text class="col col-diff">{{ difficultyText(f.difficulty) }}</text>
            <text class="col col-stem stem-text">{{ f.stem_preview }}</text>
            <text class="col col-kp">{{ f.knowledge_points_count }}</text>
            <view class="col col-action row-actions">
              <button size="mini" class="btn-action btn-edit" @click="editQuestion(f.question_id)">编辑</button>
              <button size="mini" class="btn-action btn-del" @click="removeFavorite(f)">移除</button>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { favoriteApi, type Favorite } from '@/api/favorites.ts'
import { knowledgeApi } from '@/api/knowledge'
import { useUserStore } from '@/store/index.ts'

const userStore = useUserStore()

const favorites = ref<Favorite[]>([])
const loading = ref(false)
const treeLoading = ref(false)
const selectedKP = ref<number | null>(null)

// Tree
interface TreeNode {
  name: string
  expanded?: boolean
  question_count?: number
  semesters?: SemesterNode[]
}
interface SemesterNode { name: string; expanded?: boolean; question_count?: number; chapters: ChapterNode[] }
interface ChapterNode { name: string; expanded?: boolean; question_count?: number; knowledge_points: KPNode[] }
interface KPNode { id: number; name: string; question_count: number }

const tree = ref<TreeNode[]>([])

// Filter state
const searchQuery = ref('')
const currentType = ref('')
const typeOptions = [
  { label: '全部', value: '' },
  { label: '单选题', value: 'single_choice' },
  { label: '多选题', value: 'multiple_choice' },
  { label: '填空题', value: 'fill_blank' },
  { label: '简答题', value: 'short_answer' },
  { label: '论述题', value: 'essay' },
  { label: '判断题', value: 'true_false' },
  { label: '计算题', value: 'computation' },
  { label: '证明题', value: 'proof' },
]

function selectKP(id: number) { selectedKP.value = id; loadFavorites() }
function clearKPFilter() { selectedKP.value = null; loadFavorites() }

onMounted(async () => {
  loadKnowledgeTree()
  await loadFavorites()
})

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

async function loadFavorites() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (currentType.value) params.question_type = currentType.value
    if (searchQuery.value) params.search = searchQuery.value
    if (selectedKP.value) params.knowledge_point_id = selectedKP.value
    const res = await favoriteApi.list(params)
    favorites.value = res.data || []
  } catch (e) {
    console.error('Failed to load favorites:', e)
    uni.showToast({ title: '加载精选列表失败，请检查网络', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function setType(val: string) {
  currentType.value = val
  loadFavorites()
}

async function removeFavorite(f: Favorite) {
  uni.showModal({
    title: '确认移除', content: `确定要移除精选题目 ${f.question_no} 吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await favoriteApi.remove(f.question_id)
          favorites.value = favorites.value.filter((item) => item.id !== f.id)
          uni.showToast({ title: '已移除', icon: 'success' })
        } catch (e) {
          uni.showToast({ title: '移除失败', icon: 'none' })
        }
      }
    }
  })
}

// Navigation helpers
function navigateTo(url: string) {
  uni.navigateTo({ url })
}

function editQuestion(questionId: number) {
  navigateTo(`/pages/teacher/question-edit?id=${questionId}`)
}

function difficultyText(d: number | null): string {
  if (!d) return '-'
  const n = Math.round(Number(d))
  const map: Record<number, string> = { 1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4', 5: 'L5' }
  return map[n] || String(d)
}
</script>

<style scoped>
.favorites { display: flex; min-height: 100vh; background: #f5f7fa; }
.main { margin-left: 0; flex: 1; display: flex; gap: 16px; padding: 16px; overflow: hidden; }

/* Knowledge tree */
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

/* Right panel */
.panel { flex: 1; background: #fff; border-radius: 8px; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; min-width: 0; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.panel-title { font-size: 16px; font-weight: 500; color: #303133; }
.filter-hint { font-size: 12px; color: #909399; }
.clear-link { color: #409eff; cursor: pointer; text-decoration: underline; }

/* Search bar */
.search-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.search-input { flex: 1; border: 1px solid #dcdfe6; border-radius: 4px; padding: 6px 12px; font-size: 13px; }

/* Filter bar */
.filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-label { font-size: 13px; color: #909399; }
.filter-chip { padding: 4px 12px; border-radius: 12px; font-size: 12px; background: #f0f0f0; cursor: pointer; }
.filter-chip.active { background: #409eff; color: #fff; }

.empty { text-align: center; padding: 40px 0; color: #909399; }
.loading { text-align: center; padding: 40px 0; color: #409eff; }

/* Question table */
.question-table { flex: 1; overflow-y: auto; }
.table-header { display: flex; padding: 8px 12px; background: #f5f5f5; border-radius: 8px; font-size: 12px; font-weight: bold; color: #666; }
.table-row { display: flex; padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; align-items: center; }
.table-row:hover { background: #fafafa; }
.col { flex: 1; text-align: center; }
.col-no { flex: 0.8; }
.col-type { flex: 0.8; }
.col-diff { flex: 0.6; }
.col-stem { flex: 2; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stem-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
.col-kp { flex: 0.5; }
.col-action { flex: 1.2; }

/* Row actions */
.row-actions { display: flex; gap: 6px; align-items: center; justify-content: center; }
.btn-action { padding: 2px 10px; font-size: 11px; margin: 0; min-width: auto; line-height: 1.2; }
.btn-edit { background: #f0f5ff; color: #597ef7; border: 1px solid #adc6ff; }
.btn-del { background: #fff1f0; color: #f5222d; border: 1px solid #ffa39e; }

@media (max-width: 768px) {
  .main { margin-left: 60px; flex-direction: column; }
  .knowledge-tree { width: auto; max-height: 30vh; }
}
</style>
