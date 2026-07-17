<template>
  <view class="import-page">
    <TeacherSidebar activeItem="course-practice" />

    <view class="main">
      <!-- Header -->
      <view class="page-header">
        <text class="page-title">从课程资料导入习题</text>
        <view class="header-actions">
          <text class="doc-name">{{ materialName }}</text>
          <button size="mini" @click="goBack">返回</button>
        </view>
      </view>

      <view class="content">
        <!-- Left: Document viewer -->
        <view class="doc-panel">
          <view class="doc-viewer">
            <view v-if="pages.length === 0" class="doc-empty">
              <text>文档加载中...</text>
            </view>
            <view v-else class="doc-page" @mousedown="onSelectionStart" @mousemove="onSelectionMove" @mouseup="onSelectionEnd">
              <image
                :src="pages[currentPage]?.url"
                mode="widthFix"
                class="page-image"
                @load="onImageLoad"
              />
              <!-- Box selection overlay -->
              <view
                v-if="hasSelection"
                class="selection-box"
                :style="{
                  left: Math.min(selectionStart.x, selectionEnd.x) + 'px',
                  top: Math.min(selectionStart.y, selectionEnd.y) + 'px',
                  width: Math.abs(selectionEnd.x - selectionStart.x) + 'px',
                  height: Math.abs(selectionEnd.y - selectionStart.y) + 'px',
                }"
              ></view>
            </view>
          </view>

          <!-- Page navigation -->
          <view class="page-nav" v-if="pages.length > 1">
            <button size="mini" :disabled="currentPage <= 0" @click="currentPage--">上一页</button>
            <text>{{ currentPage + 1 }} / {{ pages.length }}</text>
            <button size="mini" :disabled="currentPage >= pages.length - 1" @click="currentPage++">下一页</button>
          </view>

          <!-- Selection tools -->
          <view class="selection-tools">
            <button
              size="mini"
              :type="isSelecting ? 'warn' : 'primary'"
              @click="toggleSelection"
            >
              {{ isSelecting ? '取消框选' : '框选新增试题' }}
            </button>
            <button
              size="mini"
              type="success"
              :disabled="!isSelecting || !hasSelection"
              @click="doAiRecognize"
            >
              AI 识别
            </button>
          </view>
        </view>

        <!-- Right: Edit form -->
        <view class="edit-panel">
          <view class="form-header">
            <text class="form-title">题目编辑</text>
          </view>

          <scroll-view class="form-content" scroll-y>
            <!-- Question type -->
            <view class="form-group">
              <text class="form-label">题型</text>
              <picker :range="questionTypes" range-key="label" @change="onQuestionTypeChange">
                <view class="picker-value">
                  <text>{{ currentQuestion.typeLabel }}</text>
                </view>
              </picker>
            </view>

            <!-- Stem -->
            <view class="form-group">
              <text class="form-label">题干</text>
              <textarea
                class="form-textarea"
                v-model="currentQuestion.stem"
                placeholder="请输入题干（支持 LaTeX 公式）"
                :auto-height="true"
              />
            </view>

            <!-- Options (for choice questions) -->
            <view class="form-group" v-if="isChoiceQuestion">
              <text class="form-label">选项</text>
              <view class="option-row" v-for="opt in ['A', 'B', 'C', 'D']" :key="opt">
                <text class="option-label">{{ opt }}.</text>
                <input
                  class="option-input"
                  v-model="currentQuestion.options[opt]"
                  :placeholder="`选项${opt}`"
                />
              </view>
            </view>

            <!-- Answer -->
            <view class="form-group">
              <text class="form-label">答案</text>
              <input
                class="form-input"
                v-model="currentQuestion.answer"
                placeholder="正确答案"
              />
            </view>

            <!-- Analysis -->
            <view class="form-group">
              <text class="form-label">解析</text>
              <textarea
                class="form-textarea"
                v-model="currentQuestion.analysis"
                placeholder="请输入解析"
                :auto-height="true"
              />
            </view>

            <!-- Difficulty -->
            <view class="form-group">
              <text class="form-label">难度</text>
              <picker :range="difficultyLevels" range-key="label" @change="onDifficultyChange">
                <view class="picker-value">
                  <text>{{ currentQuestion.difficultyLabel }}</text>
                </view>
              </picker>
            </view>

            <!-- Knowledge points -->
            <view class="form-group">
              <text class="form-label">知识点</text>
              <input
                class="form-input"
                v-model="currentQuestion.knowledgePoints"
                placeholder="多个知识点用逗号分隔"
              />
            </view>

            <!-- Target node -->
            <view class="form-group">
              <text class="form-label">所属目录节点</text>
              <picker :range="nodeOptions" range-key="label" @change="onNodeChange">
                <view class="picker-value">
                  <text :class="targetNode ? 'picker-text' : 'picker-placeholder'">
                    {{ targetNodeLabel || '请选择目录节点' }}
                  </text>
                </view>
              </picker>
            </view>
          </scroll-view>

          <!-- Form actions -->
          <view class="form-footer">
            <button size="default" @click="resetForm">重置</button>
            <button size="default" type="primary" @click="saveQuestion" :disabled="!targetNode">
              保存到课程
            </button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import { materialApi, importApi, treeApi } from '@/api/courses'

// Page state
const courseId = ref(0)
const materialId = ref(0)
const materialName = ref('')
const pages = ref<Array<{ url: string; page: number }>>([])
const currentPage = ref(0)

// Selection state
const isSelecting = ref(false)
const selectionStart = ref({ x: 0, y: 0 })
const selectionEnd = ref({ x: 0, y: 0 })
const hasSelection = computed(() => {
  return Math.abs(selectionEnd.value.x - selectionStart.value.x) > 10 &&
         Math.abs(selectionEnd.value.y - selectionStart.value.y) > 10
})

// Question form
const currentQuestion = ref({
  type: 'single_choice',
  typeLabel: '单选题',
  stem: '',
  options: { A: '', B: '', C: '', D: '' },
  answer: '',
  analysis: '',
  difficulty: 3,
  difficultyLabel: '中等',
  knowledgePoints: '',
})

// Options
const questionTypes = [
  { label: '单选题', value: 'single_choice' },
  { label: '多选题', value: 'multiple_choice' },
  { label: '填空题', value: 'fill_blank' },
  { label: '解答题', value: 'solution' },
]

const difficultyLevels = [
  { label: '简单', value: 1 },
  { label: '较易', value: 2 },
  { label: '中等', value: 3 },
  { label: '较难', value: 4 },
  { label: '困难', value: 5 },
]

const isChoiceQuestion = computed(() =>
  currentQuestion.value.type === 'single_choice' || currentQuestion.value.type === 'multiple_choice'
)

// Tree nodes for selection
const treeNodes = ref<any[]>([])
const targetNode = ref<number | null>(null)
const targetNodeLabel = ref('')

const nodeOptions = computed(() => {
  const result: Array<{ label: string; value: number }> = []
  function walk(nodes: any[], prefix = '') {
    for (const n of nodes) {
      result.push({ label: prefix + n.name, value: n.id })
      if (n.children) walk(n.children, prefix + '  ')
    }
  }
  walk(treeNodes.value)
  return result
})

// Initialization
onMounted(async () => {
  const pages_list = getCurrentPages()
  const currentPage_obj = pages_list[pages_list.length - 1] as any
  const options = currentPage_obj.options || {}
  console.log('[ImportPage] options:', options)
  courseId.value = Number(options.course_id || options.id)
  materialId.value = Number(options.material_id)
  console.log('[ImportPage] courseId:', courseId.value, 'materialId:', materialId.value)

  if (!courseId.value || !materialId.value) {
    uni.showToast({ title: '参数错误', icon: 'none' })
    return
  }

  await loadMaterialPages()
  await loadTreeNodes()
})

async function loadMaterialPages() {
  try {
    console.log('[ImportPage] Loading pages for courseId:', courseId.value, 'materialId:', materialId.value)
    const res: any = await materialApi.pages(courseId.value, materialId.value)
    console.log('[ImportPage] API response:', res)
    if (res.data) {
      pages.value = res.data.pages || []
      materialName.value = res.data.material_name || ''
      console.log('[ImportPage] pages:', pages.value.length, 'materialName:', materialName.value)
    }
  } catch (e: any) {
    console.error('[ImportPage] loadMaterialPages error:', e)
    uni.showToast({ title: e?.message || '加载失败', icon: 'none' })
  }
}

async function loadTreeNodes() {
  try {
    const res: any = await treeApi.list(courseId.value)
    treeNodes.value = res.data || []
  } catch (e) {
    console.error('加载目录树失败:', e)
  }
}

// Selection handlers
function toggleSelection() {
  isSelecting.value = !isSelecting.value
  if (!isSelecting.value) {
    selectionStart.value = { x: 0, y: 0 }
    selectionEnd.value = { x: 0, y: 0 }
  }
}

function onImageLoad(e: any) {
  // Image loaded, ready for selection
}

function getMousePosition(e: MouseEvent) {
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function onSelectionStart(e: MouseEvent) {
  if (!isSelecting.value) return
  const pos = getMousePosition(e)
  selectionStart.value = pos
  selectionEnd.value = pos
}

function onSelectionMove(e: MouseEvent) {
  if (!isSelecting.value || !hasSelection.value && selectionStart.value.x === 0) return
  if (selectionStart.value.x === 0 && selectionStart.value.y === 0) return
  const pos = getMousePosition(e)
  selectionEnd.value = pos
}

function onSelectionEnd(e: MouseEvent) {
  if (!isSelecting.value) return
  const pos = getMousePosition(e)
  selectionEnd.value = pos
}

// AI recognition
async function doAiRecognize() {
  if (!hasSelection.value) {
    uni.showToast({ title: '请先框选题目区域', icon: 'none' })
    return
  }

  uni.showLoading({ title: 'AI 识别中...' })

  try {
    // Get the image URL for current page
    const imageUrl = pages.value[currentPage.value]?.url

    const res: any = await materialApi.aiRecognize(courseId.value, materialId.value, {
      image_url: imageUrl,
      page: currentPage.value + 1,
    })

    if (res.success && res.data) {
      // Fill form with AI results
      const data = res.data
      currentQuestion.value = {
        type: data.question_type || 'single_choice',
        typeLabel: questionTypes.find(t => t.value === data.question_type)?.label || '单选题',
        stem: data.stem || '',
        options: data.options || { A: '', B: '', C: '', D: '' },
        answer: data.answer || '',
        analysis: data.analysis || '',
        difficulty: data.difficulty || 3,
        difficultyLabel: difficultyLevels.find(d => d.value === data.difficulty)?.label || '中等',
        knowledgePoints: Array.isArray(data.knowledge_points) ? data.knowledge_points.join('，') : '',
      }
      uni.showToast({ title: '识别成功', icon: 'success' })
    } else {
      uni.showToast({ title: res.message || '识别失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('AI 识别失败:', e)
    uni.showToast({ title: e?.message || '识别失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

// Form handlers
function onQuestionTypeChange(e: any) {
  const idx = e.detail.value
  const opt = questionTypes[idx]
  currentQuestion.value.type = opt.value
  currentQuestion.value.typeLabel = opt.label
}

function onDifficultyChange(e: any) {
  const idx = e.detail.value
  const opt = difficultyLevels[idx]
  currentQuestion.value.difficulty = opt.value
  currentQuestion.value.difficultyLabel = opt.label
}

function onNodeChange(e: any) {
  const idx = e.detail.value
  const opt = nodeOptions.value[idx]
  targetNode.value = opt.value
  targetNodeLabel.value = opt.label
}

function resetForm() {
  currentQuestion.value = {
    type: 'single_choice',
    typeLabel: '单选题',
    stem: '',
    options: { A: '', B: '', C: '', D: '' },
    answer: '',
    analysis: '',
    difficulty: 3,
    difficultyLabel: '中等',
    knowledgePoints: '',
  }
}

async function saveQuestion() {
  if (!targetNode.value) {
    uni.showToast({ title: '请选择所属目录节点', icon: 'none' })
    return
  }

  if (!currentQuestion.value.stem) {
    uni.showToast({ title: '题干不能为空', icon: 'none' })
    return
  }

  uni.showLoading({ title: '保存中...' })

  try {
    const res: any = await importApi.saveQuestion(courseId.value, {
      question: {
        question_type: currentQuestion.value.type,
        stem: currentQuestion.value.stem,
        options: currentQuestion.value.options,
        answer: currentQuestion.value.answer,
        analysis: currentQuestion.value.analysis,
        difficulty: currentQuestion.value.difficulty,
        knowledge_points: currentQuestion.value.knowledgePoints.split('，').filter(Boolean),
      },
      tree_node_id: targetNode.value,
    })

    if (res.success) {
      uni.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => {
        uni.navigateBack()
      }, 1000)
    } else {
      uni.showToast({ title: res.message || '保存失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('保存失败:', e)
    uni.showToast({ title: e?.message || '保存失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.import-page {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.main {
  margin-left: 240px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.doc-name {
  font-size: 13px;
  color: #606266;
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.doc-panel {
  width: 50%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #ebeef5;
  background: #fff;
}

.doc-viewer {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.doc-empty {
  text-align: center;
  color: #909399;
  padding: 40px;
}

.doc-page {
  position: relative;
  max-width: 100%;
}

.page-image {
  max-width: 100%;
  height: auto;
}

.selection-box {
  position: absolute;
  border: 2px dashed #409eff;
  background: rgba(64, 158, 255, 0.1);
  pointer-events: none;
}

.page-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 12px;
  border-top: 1px solid #ebeef5;
}

.selection-tools {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid #ebeef5;
}

.edit-panel {
  width: 50%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.form-header {
  padding: 16px 24px;
  border-bottom: 1px solid #ebeef5;
}

.form-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.form-content {
  flex: 1;
  padding: 16px 24px;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
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

.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
  min-height: 80px;
}

.option-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.option-label {
  font-size: 13px;
  color: #606266;
  width: 20px;
}

.option-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
}

.picker-value {
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
}

.picker-text {
  font-size: 13px;
  color: #303133;
}

.picker-placeholder {
  font-size: 13px;
  color: #c0c4cc;
}

.form-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid #ebeef5;
}
</style>
