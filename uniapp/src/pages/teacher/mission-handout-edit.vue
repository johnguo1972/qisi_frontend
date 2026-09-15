<template>
  <view class="page">
    <view class="header">
      <text class="back" @click="goBack">‹</text>
      <text class="title">编辑课堂练习作业</text>
      <text class="status">{{ missionStatusText }}</text>
    </view>
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else class="content">
      <view class="form-card">
        <view class="form-title">作业信息</view>
        <view class="form-item"><text class="label">题目来源</text><view class="readonly-value">讲义（课堂练习）<text>固定来源</text></view></view>
        <view class="form-item"><text class="label">作业名称 *</text><input v-model="form.name" class="input" placeholder="请输入作业名称" /></view>
        <view class="form-item"><text class="label">关卡类型</text><picker :range="levelTypeOptions" range-key="label" :value="levelTypeIndex" @change="onLevelTypeChange"><view class="picker-value">{{ selectedLevelTypeLabel }}<text>⌄</text></view></picker></view>
        <view class="form-item">
          <text class="label">已选择节点 *</text>
          <view class="picker-value" @click="nodePickerVisible = !nodePickerVisible"><text :class="selectedNodeIds.length ? 'value-text' : 'placeholder'">{{ selectedNodeNames }}</text><text>⌄</text></view>
          <view v-if="nodePickerVisible" class="dropdown">
            <view v-for="node in availableNodes" :key="node.id" class="option" @click="toggleNode(node.id)"><text>{{ node.name }}</text><text class="option-count">{{ node.question_count || 0 }}题 {{ selectedNodeIds.includes(node.id) ? '✓' : '' }}</text></view>
            <view v-if="!availableNodes.length" class="empty">当前课程暂无目录节点</view>
            <view class="dropdown-footer"><button size="mini" type="primary" @click="nodePickerVisible = false">完成</button></view>
          </view>
        </view>
        <view class="form-item"><text class="label">作业题目数 *</text><view class="picker-value" @click="openQuestionPicker"><text>{{ selectedQuestionIds.length }} / {{ questionOptions.length }} 题</text><text>📋</text></view></view>
        <view class="form-item"><text class="label">通过条件（正确率）</text><input v-model="form.correctRate" class="input" type="number" placeholder="0.6" /></view>
        <view class="form-item">
          <text class="label">分配班级 *</text>
          <view class="picker-value" @click="classPickerVisible = !classPickerVisible"><text :class="form.classIds.length ? 'value-text' : 'placeholder'">{{ selectedClassNames }}</text><text>⌄</text></view>
          <view v-if="classPickerVisible" class="dropdown">
            <view v-for="item in classList" :key="item.id" class="option" @click="toggleClass(item.id)"><text>{{ item.class_name }}</text><text>{{ form.classIds.includes(String(item.id)) ? '✓' : '' }}</text></view>
            <view v-if="!classList.length" class="empty">暂无可分配班级</view>
            <view class="dropdown-footer"><button size="mini" type="primary" @click="classPickerVisible = false">完成</button></view>
          </view>
        </view>
        <view class="form-item"><text class="label">开始日期</text><view class="readonly-value">{{ dateOnly(form.startAt) }}<text>当前作业开始时间</text></view></view>
        <view class="form-item"><text class="label">截止日期 *</text><picker mode="date" :value="form.endDate || today" :start="today" @change="onEndDateChange"><view class="picker-value"><text :class="form.endDate ? 'value-text' : 'placeholder'">{{ form.endDate || '请选择截止日期' }}</text><text>📅</text></view></picker></view>
        <view class="form-item"><text class="label">作业说明</text><textarea v-model="form.goalText" class="textarea" maxlength="255" placeholder="请输入作业说明（可选）" /></view>
        <button type="primary" class="save-button" :loading="saving" @click="save">保存修改</button>
      </view>
    </view>

    <view v-if="questionPickerVisible" class="overlay" @click.self="closeQuestionPicker">
      <view class="question-modal" @click.stop>
        <view class="modal-header"><text class="modal-title">选择作业题目</text><text class="modal-close" @click="closeQuestionPicker">×</text></view>
        <view class="toolbar"><text>已选 {{ selectedQuestionIds.length }} / {{ questionOptions.length }} 题</text><view><button size="mini" @click="selectVisible(true)">全选</button><button size="mini" @click="selectVisible(false)">取消全选</button></view></view>
        <view class="question-body">
          <scroll-view scroll-y class="node-list">
            <view v-for="node in questionNodes" :key="node.id" class="node-row" :class="{ active: questionNodeId === node.id }" @click="selectQuestionNode(node.id)"><text>{{ node.name }}</text><text>{{ nodeQuestionIds[node.id]?.length || 0 }}</text></view>
            <view v-if="!questionNodes.length" class="empty">暂无可用节点</view>
          </scroll-view>
          <scroll-view scroll-y class="questions">
            <view v-if="questionsLoading" class="empty">题目加载中...</view>
            <view v-else-if="!visibleQuestions.length" class="empty">当前节点暂无题目</view>
            <view v-for="(question, index) in visibleQuestions" :key="question.id" class="question-row" :draggable="selectedQuestionIds.includes(question.id)" @dragstart="startDrag(question.id)" @dragover.prevent @drop="dropDrag(question.id)" @dragend="endDrag">
              <text v-if="selectedQuestionIds.includes(question.id)" class="drag-handle">☷</text>
              <view class="question-main" @click="toggleQuestion(question.id)"><text class="check">{{ selectedQuestionIds.includes(question.id) ? '☑' : '□' }}</text><text class="order">{{ questionOrder(question.id) || '-' }}</text><text class="stem">{{ question.stem_preview || question.stem || `题目 ${index + 1}` }}</text></view>
              <view v-if="selectedQuestionIds.includes(question.id)" class="move-buttons"><button size="mini" :disabled="questionOrder(question.id) <= 1" @click.stop="moveQuestion(question.id, -1)">↑</button><button size="mini" :disabled="questionOrder(question.id) >= selectedQuestionIds.length" @click.stop="moveQuestion(question.id, 1)">↓</button></view>
            </view>
          </scroll-view>
        </view>
        <view class="modal-footer"><button type="primary" @click="closeQuestionPicker">完成</button></view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'
import { courseQuestionApi, treeApi } from '@/api/courses'
import { missionHandoutEditApi } from '@/api/missions'

interface NodeItem { id: string; name: string; parent_id?: string | null; sort_order?: number; question_count?: number }
interface QuestionItem { id: string; stem?: string; stem_preview?: string; tree_node_ids?: string[] }

const missionId = ref('')
const courseId = ref('')
const loading = ref(true)
const saving = ref(false)
const missionStatus = ref('')
const form = ref({ name: '', goalText: '', levelType: 'practice', correctRate: '0.6', classIds: [] as string[], startAt: '', endDate: '' })
const levelTypeOptions = [{ label: '练习', value: 'practice' }, { label: '复习', value: 'review' }, { label: '补做', value: 'retry' }, { label: '变式', value: 'variant' }, { label: '测试', value: 'check' }]
const availableNodes = ref<NodeItem[]>([])
const selectedNodeIds = ref<string[]>([])
const classList = ref<any[]>([])
const nodePickerVisible = ref(false)
const classPickerVisible = ref(false)
const questionPickerVisible = ref(false)
const questionsLoading = ref(false)
const questionOptions = ref<QuestionItem[]>([])
const selectedQuestionIds = ref<string[]>([])
const questionNodeId = ref('')
const nodeQuestionIds = ref<Record<string, string[]>>({})
const questionSelectionInitialized = ref(false)
const draggingQuestionId = ref('')
const routeOptions = ref<Record<string, any>>({})

const today = computed(() => localDateString())
const levelTypeIndex = computed(() => Math.max(0, levelTypeOptions.findIndex(item => item.value === form.value.levelType)))
const selectedLevelTypeLabel = computed(() => levelTypeOptions[levelTypeIndex.value]?.label || '练习')
const selectedNodeNames = computed(() => selectedNodeIds.value.length ? availableNodes.value.filter(node => selectedNodeIds.value.includes(node.id)).map(node => node.name).join('、') : '全部节点（至少选择一个）')
const selectedClassNames = computed(() => form.value.classIds.length ? classList.value.filter(item => form.value.classIds.includes(String(item.id))).map(item => item.class_name).join('、') : '请选择班级（可多选）')
const missionStatusText = computed(() => ({ draft: '草稿', published: '已发布', running: '进行中', closed: '已关闭' }[missionStatus.value] || missionStatus.value))
const questionNodes = computed(() => availableNodes.value.filter(node => selectedNodeIds.value.includes(node.id)))
const visibleQuestionIds = computed(() => questionNodeId.value ? new Set(nodeQuestionIds.value[questionNodeId.value] || []) : new Set(questionOptions.value.map(question => question.id)))
const visibleQuestions = computed(() => {
  const visible = visibleQuestionIds.value
  const map = new Map(questionOptions.value.map(question => [question.id, question]))
  const selected = selectedQuestionIds.value.map(id => map.get(id)).filter(item => item && visible.has(item.id)) as QuestionItem[]
  const selectedSet = new Set(selectedQuestionIds.value)
  return [...selected, ...questionOptions.value.filter(question => visible.has(question.id) && !selectedSet.has(question.id))]
})

function localDateString(date = new Date()) { const pad = (value: number) => String(value).padStart(2, '0'); return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` }
function dateOnly(value: string) { return value ? String(value).slice(0, 10) : '-' }
function flattenNodes(nodes: any[], result: NodeItem[] = []) { for (const node of nodes || []) { result.push({ id: String(node.id), name: node.name, parent_id: node.parent_id ? String(node.parent_id) : null, sort_order: node.sort_order, question_count: Number(node.question_count || 0) }); flattenNodes(node.children || [], result) } return result }
function unwrap(response: any) { return response?.data?.data ?? response?.data ?? response }

onLoad((options: any) => { routeOptions.value = options || {} })
onMounted(async () => {
  const pages = getCurrentPages(); const page = pages[pages.length - 1] as any
  const options = Object.keys(routeOptions.value).length ? routeOptions.value : (page?.options || page?.$page?.options || {})
  missionId.value = String(options.id || '')
  if (!missionId.value) { uni.showToast({ title: '缺少作业参数', icon: 'none' }); loading.value = false; return }
  try {
    const data = unwrap(await missionHandoutEditApi.detail(missionId.value))
    courseId.value = String(data.course_id || '')
    missionStatus.value = String(data.status || '')
    form.value = { name: data.mission_name || '', goalText: data.goal_text || '', levelType: data.level_type || 'practice', correctRate: String(data.pass_rule?.correct_rate ?? 0.6), classIds: (data.class_ids || []).map((value: any) => String(value)), startAt: data.start_at || '', endDate: dateOnly(data.end_at) }
    selectedNodeIds.value = (data.node_ids || []).map((value: any) => String(value))
    selectedQuestionIds.value = (data.question_ids || []).map((value: any) => String(value))
    questionOptions.value = (data.questions || []).map(normalizeQuestion)
    questionSelectionInitialized.value = questionOptions.value.length > 0
    await Promise.all([loadNodes(), loadClasses()])
    // Load the complete question scope up front so the form count and the
    // picker both represent the selected classroom-practice nodes.
    await loadScopedQuestions()
  } catch (error: any) { uni.showToast({ title: error?.message || '作业加载失败', icon: 'none' }) } finally { loading.value = false }
})
async function loadNodes() { if (!courseId.value) return; const data = unwrap(await treeApi.list(courseId.value)); availableNodes.value = flattenNodes(Array.isArray(data) ? data : []) }
async function loadClasses() { const response: any = await classApi.simpleList(); classList.value = response?.data?.data || response?.data || [] }
function normalizeQuestion(item: any): QuestionItem { return { ...item, id: String(item?.id || item?.question_id || ''), tree_node_ids: (item?.tree_node_ids || []).map((value: any) => String(value)) } }
function toggleNode(id: string) { const index = selectedNodeIds.value.indexOf(String(id)); if (index >= 0) selectedNodeIds.value.splice(index, 1); else selectedNodeIds.value.push(String(id)); if (questionPickerVisible.value) void loadScopedQuestions() }
function toggleClass(id: string) { const value = String(id); const index = form.value.classIds.indexOf(value); if (index >= 0) form.value.classIds.splice(index, 1); else form.value.classIds.push(value) }
function onLevelTypeChange(event: any) { form.value.levelType = levelTypeOptions[Number(event.detail.value)]?.value || 'practice' }
function onEndDateChange(event: any) { form.value.endDate = String(event?.detail?.value || '') }

async function loadScopedQuestions() {
  if (!courseId.value) return
  questionsLoading.value = true
  const nodeIds = selectedNodeIds.value.length ? selectedNodeIds.value : availableNodes.value.map(node => node.id)
  const unique = new Map<string, QuestionItem>(); const counts: Record<string, string[]> = {}
  try {
    for (const nodeId of nodeIds) {
      counts[nodeId] = []; let page = 1; let total = 0
      do {
        const response: any = await courseQuestionApi.list(courseId.value, { page, page_size: 100, tree_node_id: nodeId } as any)
        const data = unwrap(response) || {}; const items = Array.isArray(data.items) ? data.items : []
        for (const raw of items) { const question = normalizeQuestion(raw); if (!question.id) continue; unique.set(question.id, question); if (!counts[nodeId].includes(question.id)) counts[nodeId].push(question.id) }
        total = Number(data.total || items.length); if (!items.length || page * 100 >= total) break; page += 1
      } while (page <= 100)
    }
    questionOptions.value = [...unique.values()]; nodeQuestionIds.value = counts
    if (!questionSelectionInitialized.value) { selectedQuestionIds.value = questionOptions.value.map(question => question.id); questionSelectionInitialized.value = true }
    else { const available = new Set(questionOptions.value.map(question => question.id)); selectedQuestionIds.value = selectedQuestionIds.value.filter(id => available.has(id)) }
    if (!questionNodeId.value || !nodeIds.includes(questionNodeId.value)) questionNodeId.value = ''
  } catch (error: any) { uni.showToast({ title: error?.message || '题目加载失败', icon: 'none' }) } finally { questionsLoading.value = false }
}
async function openQuestionPicker() { questionPickerVisible.value = true; if (!questionOptions.value.length || !Object.keys(nodeQuestionIds.value).length) await loadScopedQuestions() }
function closeQuestionPicker() { questionPickerVisible.value = false }
function selectQuestionNode(id: string) { questionNodeId.value = String(id) }
function questionOrder(id: string) { const index = selectedQuestionIds.value.indexOf(String(id)); return index >= 0 ? index + 1 : 0 }
function toggleQuestion(id: string) { const value = String(id); const index = selectedQuestionIds.value.indexOf(value); if (index >= 0) selectedQuestionIds.value.splice(index, 1); else selectedQuestionIds.value.push(value) }
function selectVisible(select: boolean) { const visible = [...visibleQuestionIds.value]; const visibleSet = new Set(visible); selectedQuestionIds.value = select ? [...selectedQuestionIds.value.filter(id => !visibleSet.has(id)), ...visible] : selectedQuestionIds.value.filter(id => !visibleSet.has(id)) }
function moveQuestion(id: string, offset: number) { const current = selectedQuestionIds.value.indexOf(String(id)); const target = current + offset; if (current < 0 || target < 0 || target >= selectedQuestionIds.value.length) return; const next = [...selectedQuestionIds.value]; const [moved] = next.splice(current, 1); next.splice(target, 0, moved); selectedQuestionIds.value = next }
function startDrag(id: string) { draggingQuestionId.value = selectedQuestionIds.value.includes(id) ? id : '' }
function dropDrag(id: string) { const source = draggingQuestionId.value; if (source && source !== id) { const from = selectedQuestionIds.value.indexOf(source); const to = selectedQuestionIds.value.indexOf(id); if (from >= 0 && to >= 0) { const next = [...selectedQuestionIds.value]; next.splice(from, 1); next.splice(to, 0, source); selectedQuestionIds.value = next } } endDrag() }
function endDrag() { draggingQuestionId.value = '' }

async function save() {
  if (!form.value.name.trim()) return uni.showToast({ title: '请输入作业名称', icon: 'none' })
  if (!selectedNodeIds.value.length) return uni.showToast({ title: '请至少选择一个节点', icon: 'none' })
  if (!form.value.classIds.length) return uni.showToast({ title: '请至少选择一个班级', icon: 'none' })
  if (!form.value.endDate) return uni.showToast({ title: '请选择截止日期', icon: 'none' })
  if (!selectedQuestionIds.value.length) return uni.showToast({ title: '请至少选择一道题目', icon: 'none' })
  const correctRate = Number(form.value.correctRate)
  if (!Number.isFinite(correctRate) || correctRate < 0 || correctRate > 1) return uni.showToast({ title: '正确率必须在 0 到 1 之间', icon: 'none' })
  saving.value = true
  try {
    await missionHandoutEditApi.update(missionId.value, { mission_name: form.value.name.trim(), goal_text: form.value.goalText, level_type: form.value.levelType, pass_rule: { correct_rate: correctRate }, source_type: 'handout', source_context: 'course_practice', node_ids: selectedNodeIds.value as any, question_ids: selectedQuestionIds.value as any, class_ids: form.value.classIds as any, start_at: form.value.startAt, end_at: `${form.value.endDate}T23:59:59+08:00` })
    uni.$emit('mission-list-refresh'); uni.showToast({ title: '保存成功', icon: 'success' }); setTimeout(goBack, 600)
  } catch (error: any) { uni.showToast({ title: error?.message || '保存失败', icon: 'none' }) } finally { saving.value = false }
}
function goBack() { const pages = getCurrentPages(); if (pages.length > 1) uni.navigateBack({ delta: 1 }); else uni.reLaunch({ url: '/pages/teacher/layout' }) }
</script>

<style scoped>
.page { min-height: 100vh; background: #f5f7fa; color: #303133; }.header { height: 88rpx; display: flex; align-items: center; justify-content: center; background: #fff; border-bottom: 1rpx solid #ebeef5; position: relative; }.back { position: absolute; left: 28rpx; font-size: 56rpx; line-height: 1; color: #606266; }.title { font-size: 34rpx; font-weight: 600; }.status { position: absolute; right: 28rpx; color: #67c23a; font-size: 24rpx; }.loading { text-align: center; padding: 100rpx; color: #909399; }.content { padding: 28rpx; }.form-card { max-width: 1180rpx; margin: 0 auto; background: #fff; padding: 32rpx 40rpx 42rpx; border-radius: 12rpx; }.form-title { font-size: 32rpx; font-weight: 600; margin-bottom: 26rpx; }.form-item { margin-bottom: 24rpx; position: relative; }.label { display: block; font-size: 25rpx; color: #606266; margin-bottom: 10rpx; }.input, .readonly-value, .picker-value, .textarea { box-sizing: border-box; width: 100%; border: 1rpx solid #dcdfe6; border-radius: 8rpx; background: #fff; font-size: 27rpx; padding: 18rpx 22rpx; }.input { height: 74rpx; }.readonly-value, .picker-value { min-height: 74rpx; display: flex; align-items: center; justify-content: space-between; }.readonly-value { background: #f5f7fa; }.readonly-value text { color: #909399; font-size: 23rpx; }.value-text { color: #303133; }.placeholder { color: #c0c4cc; }.textarea { min-height: 150rpx; }.dropdown { position: absolute; z-index: 20; top: 136rpx; left: 0; width: 100%; max-height: 480rpx; overflow-y: auto; background: #fff; border: 1rpx solid #dcdfe6; border-radius: 8rpx; box-shadow: 0 8rpx 24rpx rgba(0,0,0,.12); }.option { padding: 20rpx 24rpx; border-bottom: 1rpx solid #f0f0f0; display: flex; justify-content: space-between; }.option-count { color: #909399; font-size: 23rpx; }.dropdown-footer { padding: 14rpx; text-align: right; }.empty { color: #909399; text-align: center; padding: 40rpx 20rpx; font-size: 25rpx; }.save-button { margin-top: 34rpx; width: 100%; }.overlay { position: fixed; inset: 0; z-index: 100; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; padding: 24rpx; }.question-modal { width: min(1100rpx, 96vw); height: min(900rpx, 88vh); background: #fff; border-radius: 12rpx; display: flex; flex-direction: column; overflow: hidden; }.modal-header { padding: 26rpx 32rpx; display: flex; justify-content: space-between; border-bottom: 1rpx solid #ebeef5; }.modal-title { font-size: 31rpx; font-weight: 600; }.modal-close { font-size: 42rpx; color: #909399; }.toolbar { padding: 18rpx 28rpx; display: flex; justify-content: space-between; align-items: center; color: #606266; font-size: 24rpx; }.toolbar button { margin-left: 12rpx; }.question-body { flex: 1; min-height: 0; display: flex; padding: 0 24rpx; gap: 18rpx; }.node-list { width: 280rpx; background: #f5f7fa; border-radius: 8rpx; }.node-row { padding: 20rpx 16rpx; display: flex; justify-content: space-between; border-bottom: 1rpx solid #ebeef5; font-size: 24rpx; }.node-row.active { color: #409eff; background: #ecf5ff; }.node-row text:last-child { color: #909399; }.questions { flex: 1; min-width: 0; border: 1rpx solid #ebeef5; border-radius: 8rpx; }.question-row { display: flex; align-items: center; min-height: 76rpx; border-bottom: 1rpx solid #ebeef5; padding: 0 14rpx; }.drag-handle { width: 36rpx; color: #909399; }.question-main { flex: 1; display: flex; align-items: center; min-width: 0; }.check { color: #409eff; width: 44rpx; }.order { width: 48rpx; color: #909399; }.stem { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 24rpx; }.move-buttons { display: flex; gap: 8rpx; }.move-buttons button { margin: 0; }.modal-footer { padding: 20rpx; text-align: center; border-top: 1rpx solid #ebeef5; }.modal-footer button { min-width: 180rpx; }
@media (max-width: 700px) { .content { padding: 16rpx; }.form-card { padding: 24rpx; }.question-body { gap: 10rpx; }.node-list { width: 230rpx; }.question-modal { height: 86vh; } }
</style>
