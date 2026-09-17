<template>
  <view class="page">
    <view class="header"><text class="title">错题练习</text><view class="header-actions"><button size="mini" @click="load">刷新</button><button size="mini" @click="historyVisible = true">导入历史</button><button size="mini" type="primary" :disabled="uploading" @click="chooseFile">{{ uploading ? '正在提交...' : '导入错题练习题' }}</button></view></view>
    <view class="layout"><view class="panel">
      <view class="panel-head"><text class="panel-title">习题列表（{{ total }} 题）</text><view class="pagination"><button size="mini" :disabled="page <= 1" @click="go(page - 1)">上一页</button><button size="mini" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button><text>{{ page }} / {{ totalPages }} 页　{{ pageSize }} / {{ total }}</text></view></view>
      <view class="filters"><text>题型</text><picker mode="selector" :range="typeLabels" :value="typeIndex" @change="onQuestionTypeChange"><view class="select">{{ typeLabels[typeIndex] }}</view></picker><text>难度</text><picker mode="selector" :range="difficultyLabels" :value="difficultyIndex" @change="onDifficultyChange"><view class="select">{{ difficultyLabels[difficultyIndex] }}</view></picker><text>标签</text><picker mode="selector" :range="tagLabels" :value="tagIndex" @change="onTagChange"><view class="select">{{ tagLabels[tagIndex] }}</view></picker><button size="mini" @click="loadTags">刷新标签</button><input v-model="keyword" class="keyword" placeholder="输入关键词进行查询" @confirm="applyFilters"/><button size="mini" type="primary" @click="applyFilters">查询</button><button size="mini" @click="resetFilters">重置</button></view>
      <view v-if="selectedIds.length && !loading" class="batch-bar"><text>已选 {{ selectedIds.length }} 题</text><button size="mini" type="warn" @click="removeQuestions(selectedIds)">从错题练习册移除</button><button size="mini" @click="selectedIds = []">取消选择</button></view>
      <scroll-view scroll-y class="question-scroll"><view v-if="loading" class="empty">加载中...</view><view v-else-if="!questions.length" class="empty">暂无题目</view><view v-for="(question, index) in questions" :key="question.id" class="question-item"><text v-if="question.source_document_question_no" data-test="wrong-drill-document-no" class="document-number">文档题号：{{ question.source_document_question_no }}</text><QuestionDetailCard :question="question" :index="(page - 1) * pageSize + index + 1" :show-answer="Boolean(showAnswerMap[question.id])" :selected="selectedIds.includes(question.id)" :compact="compactMode" @check="toggleSelect" @toggle-answer="toggleAnswer(question.id)" @ai-answer="mode => openAiAnswer(question, mode)" @edit="goEdit" @related="goEdit" @edit-tags="question => goEdit(question.id)" @add-favorite="addFavorite"><template #course-footer-actions><button size="mini" type="warn" :disabled="loading" @click.stop="removeQuestions([question.id])">从错题练习册移除</button></template></QuestionDetailCard></view></scroll-view>
    </view><RightActionPanel :all-shown="allAnswersShown" :compact-mode="compactMode" @refresh="load" @toggle-answer="toggleAllAnswers" @toggle-mode="compactMode = !compactMode" @basket="addSelectedToFavorites" @batch-ai="submitBatchAi" @ai-explore="submitAiExplore" @ai-mode-a="submitAiMode('A')" @ai-mode-b="submitAiMode('B')" @ai-mode-c="submitAiMode('C')"/></view>
    <view v-if="historyVisible" class="overlay" @click.self="historyVisible = false"><view class="history-dialog"><view class="history-head"><text>导入历史</text><button size="mini" @click="historyVisible = false">关闭</button></view><view v-if="!sources.length" class="empty">暂无导入记录</view><view v-for="item in sources" :key="item.source_set_id" class="history-row">{{ item.source_file_name }}　{{ item.import_task?.stage || item.status }}　成功 {{ item.import_task?.success_count || 0 }} 题</view></view></view>
    <AiAnswerModal :visible="answerVisible" :question="answerQuestion" :mode="answerMode" @close="answerVisible = false" @saved="load" @reprocessed="load"/>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { courseApi } from '@/api/courses'
import { classroomWrongbookApi } from '@/api/classroom-wrongbook'
import { aiProcessProbe, getTagList, questionApi } from '@/api/questions'
import { favoriteApi } from '@/api/favorites'
import QuestionDetailCard from '@/components/QuestionDetailCard.vue'
import RightActionPanel from '@/components/RightActionPanel.vue'
import AiAnswerModal from '@/components/AiAnswerModal.vue'
import { QUESTION_TYPE_OPTIONS } from '@/constants/question-types'

const courseId = ref(''), missionId = ref(''), classId = ref(''), sourceSetId = ref('')
const sources = ref<any[]>([]), questions = ref<any[]>([]), loading = ref(false), uploading = ref(false)
const total = ref(0), page = ref(1), pageSize = ref(20), selectedIds = ref<string[]>([])
const showAnswerMap = ref<Record<string, boolean>>({}), compactMode = ref(false), historyVisible = ref(false)
const keyword = ref(''), activeType = ref(''), activeDifficulty = ref(''), activeTag = ref(''), tags = ref<any[]>([])
const answerVisible = ref(false), answerQuestion = ref<any>(null), answerMode = ref<'ALL' | 'A' | 'B' | 'C'>('ALL')
const typeLabels = ['全部题型', ...QUESTION_TYPE_OPTIONS.map(item => item.label)]
const typeIndex = computed(() => Math.max(0, QUESTION_TYPE_OPTIONS.findIndex(item => item.value === activeType.value) + 1))
const difficultyLabels = ['全部难度', '★', '★★', '★★★', '★★★★', '★★★★★']
const difficultyIndex = computed(() => Number(activeDifficulty.value || 0))
const tagLabels = computed(() => ['全部标签', ...tags.value.map(item => item.name)])
const tagIndex = computed(() => Math.max(0, tags.value.findIndex(item => item.name === activeTag.value) + 1))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const allAnswersShown = computed(() => questions.value.length > 0 && questions.value.every(question => showAnswerMap.value[question.id]))

onLoad(async options => { courseId.value = String(options?.course_id || ''); await loadTags(); await load() })
async function load() {
  if (!courseId.value) return
  loading.value = true
  try {
    const contextResponse: any = await courseApi.wrongDrillContext(courseId.value as any), context = contextResponse?.data || contextResponse
    missionId.value = String(context?.mission_id || ''); classId.value = String(context?.class_ids?.[0] || '')
    if (!missionId.value || !classId.value) { questions.value = []; total.value = 0; return }
    const sourceResponse: any = await classroomWrongbookApi.wrongDrillSources(missionId.value, { class_id: classId.value })
    sources.value = sourceResponse?.data?.sources || []
    if (!sources.value.some(item => item.source_set_id === sourceSetId.value)) sourceSetId.value = sources.value[0]?.source_set_id || ''
    if (!sourceSetId.value) { questions.value = []; total.value = 0; return }
    const response: any = await classroomWrongbookApi.wrongDrillSourceDetail(missionId.value, sourceSetId.value, { class_id: classId.value, page: page.value, page_size: pageSize.value, question_type: activeType.value, difficulty: activeDifficulty.value, tag: activeTag.value, keyword: keyword.value })
    const data = response?.data || {}; questions.value = data.questions || []; total.value = Number(data.total || 0); page.value = Number(data.page_no || 1)
  } catch (error) { console.error('加载错题练习题失败', error); uni.showToast({ title: '加载错题练习题失败', icon: 'none' }) } finally { loading.value = false }
}
function go(target: number) { page.value = Math.max(1, Math.min(totalPages.value, target)); load() }
function applyFilters() { page.value = 1; load() }
function resetFilters() { activeType.value = ''; activeDifficulty.value = ''; activeTag.value = ''; keyword.value = ''; applyFilters() }
function onQuestionTypeChange(event: any) { activeType.value = QUESTION_TYPE_OPTIONS[Number(event.detail.value) - 1]?.value || ''; applyFilters() }
function onDifficultyChange(event: any) { activeDifficulty.value = String(event.detail.value || ''); applyFilters() }
function onTagChange(event: any) { activeTag.value = tags.value[Number(event.detail.value) - 1]?.name || ''; applyFilters() }
async function loadTags() { const response: any = await getTagList(); tags.value = Array.isArray(response?.data) ? response.data : [] }
function toggleSelect(id: string) { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter(item => item !== id) : [...selectedIds.value, id] }
function toggleAnswer(id: string) { showAnswerMap.value[id] = !showAnswerMap.value[id] }
function toggleAllAnswers() { const visible = !allAnswersShown.value; questions.value.forEach(question => { showAnswerMap.value[question.id] = visible }) }
function goEdit(id: string) { uni.navigateTo({ url: `/pages/teacher/question-edit?id=${id}` }) }
function openAiAnswer(question: any, mode: 'ALL' | 'A' | 'B' | 'C') { answerQuestion.value = question; answerMode.value = mode; answerVisible.value = true }
async function addFavorite(id: string) { try { await favoriteApi.add(id); uni.showToast({ title: '已加入精选', icon: 'success' }) } catch { uni.showToast({ title: '已在精选中', icon: 'none' }) } }
function requireSelection() { if (!selectedIds.value.length) { uni.showToast({ title: '请先选择题目', icon: 'none' }); return false }; return true }
async function addSelectedToFavorites() { if (requireSelection()) await Promise.all(selectedIds.value.map(addFavorite)) }
async function submitBatchAi() { if (requireSelection()) await questionApi.batchAi(selectedIds.value) }
async function submitAiExplore() { if (requireSelection()) await Promise.all(selectedIds.value.map(aiProcessProbe)) }
async function submitAiMode(mode: string) { if (requireSelection()) await Promise.all(selectedIds.value.map(id => questionApi.aiProcessMode(id, mode))) }
async function removeQuestions(ids: string[]) { if (!ids.length || !sourceSetId.value) return; try { await classroomWrongbookApi.removeWrongDrillQuestions(missionId.value, sourceSetId.value, { class_id: classId.value, question_ids: ids }); selectedIds.value = []; await load() } catch { uni.showToast({ title: '移除失败', icon: 'none' }) } }
function chooseFile() {
  const selected = (result: any) => uploadWrongDrill(result?.tempFiles?.[0]?.path || result?.tempFilePaths?.[0])
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({ count: 1, type: 'file', success: selected })
  // #endif
  // #ifndef MP-WEIXIN
  ;(uni as any).chooseFile({ count: 1, extension: ['docx'], success: selected })
  // #endif
}
async function uploadWrongDrill(filePath?: string) { if (!filePath || !missionId.value || !classId.value) return; uploading.value = true; try { const response: any = await classroomWrongbookApi.uploadWrongDrill(missionId.value, filePath, { class_id: classId.value }); sourceSetId.value = response?.data?.source_set_id || ''; uni.showToast({ title: '已提交导入', icon: 'success' }); await load() } catch (error) { console.error('导入错题练习题失败', error); uni.showToast({ title: '导入失败', icon: 'none' }) } finally { uploading.value = false } }
</script>

<style scoped>
.page { min-height: 100vh; padding: 30rpx; background: #f5f7fa; }.header,.header-actions,.panel-head,.filters,.batch-bar,.layout,.pagination,.history-head { display:flex; align-items:center; gap:12rpx; flex-wrap:wrap; }.header,.panel-head,.history-head { justify-content:space-between; }.title,.panel-title { font-size:36rpx; font-weight:600; }.layout { align-items:stretch; background:#fff; }.panel { flex:1; min-width:0; padding:20rpx; }.filters,.batch-bar { margin:16rpx 0; padding:16rpx; background:#f6f8fb; }.select,.keyword { padding:10rpx; border:1px solid #dcdfe6; background:#fff; }.question-scroll { height:calc(100vh - 310rpx); }.document-number { display:block; margin:12rpx 0; color:#606266; }.empty { padding:100rpx; color:#909399; text-align:center; }.overlay { position:fixed; inset:0; z-index:99; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,.4); }.history-dialog { width:700rpx; max-height:70vh; padding:30rpx; overflow:auto; background:#fff; border-radius:12rpx; }.history-row { padding:16rpx 0; border-bottom:1px solid #ebeef5; color:#606266; }
</style>
