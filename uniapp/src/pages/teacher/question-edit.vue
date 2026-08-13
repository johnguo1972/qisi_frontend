<template>
  <view class="edit-page">
    <view v-if="question" class="editor-shell">
      <view class="page-header">
        <view>
          <text class="page-title">编辑题目</text>
          <text class="page-subtitle">{{ form.question_no || '-' }} · {{ questionTypeLabel }}</text>
        </view>
        <view class="header-actions">
          <button size="mini" @click="handleBack">返回</button>
          <button size="mini" type="primary" :loading="saving" @click="handleSave">保存</button>
          <button size="mini" type="success" @click="handleConfirm">确认题目</button>
          <button size="mini" @click="handleAiProcess">AI处理</button>
        </view>
      </view>

      <view class="workspace">
        <scroll-view scroll-y class="editor-pane">
          <view class="section-card">
            <view class="section-heading"><text class="section-title">题目编辑</text><text class="section-hint">左侧编辑，右侧为最终题目效果预览</text></view>
            <view class="meta-grid">
              <view class="field"><text class="field-label">题型</text><picker mode="selector" :range="questionTypeRange" :value="questionTypeIndex" @change="onQuestionTypeChange"><view class="control picker-control">{{ questionTypeLabel }}</view></picker></view>
              <view class="field"><text class="field-label">题号</text><input v-model="form.question_no" class="control" /></view>
              <view class="field"><text class="field-label">难度</text><picker mode="selector" :range="difficultyRange" :value="difficultyIndex" @change="onDifficultyChange"><view class="control picker-control">{{ difficultyLabel }}</view></picker></view>
            </view>

            <view class="content-field stem-field"><text class="field-label">题干 <text class="question-uuid">UUID：{{ question.id }}</text></text><textarea v-model="form.stem" class="editor-textarea" rows="6" @input="scheduleRender" /></view>

            <view v-if="editableTables.length" class="content-field tables-field">
              <view class="table-editor-heading"><text class="field-label">表格</text><text class="table-editor-hint">可直接修改单元格；保存题目时同步保存</text></view>
              <view v-for="(table, tableIndex) in editableTables" :key="table.table_id || tableIndex" class="table-editor">
                <view class="table-editor-toolbar"><text class="table-editor-title">表格{{ editableTables.length > 1 ? ` ${tableIndex + 1}` : '' }}</text><view class="table-editor-actions"><button size="mini" @click="addTableRow(tableIndex)">+ 行</button><button size="mini" @click="addTableColumn(tableIndex)">+ 列</button><button size="mini" type="warn" @click="removeTable(tableIndex)">删除表格</button></view></view>
                <scroll-view scroll-x class="table-editor-scroll"><view class="table-editor-grid" :style="{ gridTemplateColumns: tableGridColumns(table) }"><view v-for="(cell, cellIndex) in flattenedEditableCells(table)" :key="cellIndex" class="table-editor-cell"><input v-model="table.cells[Math.floor(cellIndex / tableColumnCount(table))][cellIndex % tableColumnCount(table)]" class="table-cell-input" @input="scheduleRender" /><button size="mini" type="warn" class="table-cell-remove" @click="removeTableCell(tableIndex, cellIndex)">×</button></view></view></scroll-view>
              </view>
            </view>
            <view v-else class="content-field tables-field"><view class="table-editor-heading"><text class="field-label">表格</text><button size="mini" @click="addTable">+ 添加表格</button></view></view>

            <view v-if="isChoice" class="content-field options-field">
              <text class="field-label">选项</text>
              <view v-for="option in form.options" :key="option.label" class="option-editor"><text class="option-label">{{ option.label }}.</text><textarea v-model="option.content" class="editor-textarea option-textarea" rows="2" maxlength="100" @input="scheduleRender" /></view>
            </view>

            <view class="content-field"><text class="field-label">答案</text><textarea v-model="form.answer" class="editor-textarea answer-textarea" rows="2" @input="scheduleRender" /></view>
            <view class="content-field"><text class="field-label">解析</text><textarea v-model="form.analysis" class="editor-textarea analysis-textarea" rows="7" @input="scheduleRender" /></view>
            <view class="content-field"><text class="field-label">解答</text><textarea v-model="form.solution" class="editor-textarea analysis-textarea" rows="7" @input="scheduleRender" /></view>
          </view>

          <view class="section-card image-manager">
            <view class="section-heading"><view><text class="section-title">插图管理</text><text class="section-hint">插图默认显示在题干下方；说明文字显示在图片下方</text></view><button size="mini" type="primary" @click="importImage">导入图片</button></view>
            <view v-if="images.length" class="image-list">
              <view v-for="image in images" :key="image.id" class="image-item" :class="{ active: selectedImage?.id === image.id }">
                <image :src="getImageUrl(image.file_path)" mode="aspectFill" class="image-thumb" @click="selectImage(image)" />
                <view class="image-settings"><input v-model="image.description" class="image-name" placeholder="图片说明（显示在图片下方）" @blur="saveImage(image)" /><view class="image-actions"><button size="mini" :disabled="!image.can_restore_original" @click="restoreOriginalImage(image)">恢复原始图</button><button size="mini" type="warn" @click="deleteImage(image)">删除</button></view></view>
              </view>
            </view>
            <text v-else class="empty-hint">暂无插图，可导入图片</text>
            <view v-if="selectedImage" class="canvas-editor">
              <view class="canvas-title"><text>图片画布编辑</text><text>滚轮或按钮缩放；左键拖动框选；拖动蓝框或右下角方块可调整</text></view>
              <view class="canvas-tools"><button size="mini" @click="zoomOut">缩小</button><button size="mini" @click="zoomIn">放大</button><button size="mini" @click="rotateLeft">左旋 90°</button><button size="mini" @click="rotateRight">右旋 90°</button><button size="mini" @click="flipHorizontal">水平翻转</button><button size="mini" :disabled="!hasImageTransform" @click="saveImageTransform">保存变换</button></view>
              <view class="canvas-stage" @wheel.prevent="handleCanvasWheel" @mousewheel.prevent="handleCanvasWheel" @mousedown="startSelection" @mousemove="moveSelection" @mouseup="endSelection" @mouseleave="endSelection">
                <view ref="canvasSurface" class="canvas-surface" :style="canvasSurfaceStyle"><image :src="getImageUrl(selectedImage.file_path)" mode="widthFix" class="canvas-image" :style="canvasStyle" /></view>
                <view v-if="selection" class="selection-box" :style="selectionStyle" @mousedown.stop="startSelectionMove"><view class="selection-resize" @mousedown.stop="startSelectionResize"></view></view>
              </view>
              <view class="canvas-footer"><text>当前显示宽度：{{ selectedImageWidth }}px</text><view><button size="mini" @click="resetImageScale">重置</button><button size="mini" @click="saveImage(selectedImage)">保存大小</button><button size="mini" type="primary" :disabled="!selection || cropping || hasImageTransform" @click="cropSelectedImage">保存裁切</button></view></view>
            </view>
          </view>

          <view class="section-card">
            <view class="section-heading"><text class="section-title">{{ subjectLabel }}知识点</text><text class="section-hint">可模糊搜索、展开树并多选</text></view>
            <view class="kp-picker">
              <input v-model="knowledgeSearch" class="control" placeholder="搜索当前科目知识点" @focus="kpDropdownOpen = true" />
              <view v-if="kpDropdownOpen" class="kp-dropdown-panel">
                <scroll-view scroll-y class="knowledge-tree-scroll">
                  <view v-if="!filteredKnowledgeTree.length" class="empty-hint">暂无匹配的知识点</view>
                  <view v-for="grade in filteredKnowledgeTree" :key="grade.id" class="tree-group">
                    <view class="tree-row tree-grade" @click="toggleTree(grade.id)"><text class="tree-arrow">{{ expanded(grade.id) || searchingKnowledge ? '▾' : '▸' }}</text><text>{{ grade.name }}</text></view>
                    <view v-if="expanded(grade.id) || searchingKnowledge">
                      <view v-for="semester in grade.semesters" :key="semester.id">
                        <view class="tree-row tree-semester" @click="toggleTree(semester.id)"><text class="tree-arrow">{{ expanded(semester.id) || searchingKnowledge ? '▾' : '▸' }}</text><text>{{ semester.name }}</text></view>
                        <view v-if="expanded(semester.id) || searchingKnowledge">
                          <view v-for="chapter in semester.chapters" :key="chapter.id">
                            <view class="tree-row tree-chapter" @click="toggleTree(chapter.id)"><text class="tree-arrow">{{ expanded(chapter.id) || searchingKnowledge ? '▾' : '▸' }}</text><text>{{ chapter.name }}</text></view>
                            <view v-if="expanded(chapter.id) || searchingKnowledge">
                              <view v-for="kp in chapter.knowledge_points" :key="kp.id" class="tree-row tree-leaf" @click.stop="toggleKnowledgePoint(kp)"><view class="tree-checkbox" :class="{ checked: isKnowledgePointSelected(kp.id) }"><text v-if="isKnowledgePointSelected(kp.id)">✓</text></view><text>{{ kp.name }}</text></view>
                            </view>
                          </view>
                        </view>
                      </view>
                    </view>
                  </view>
                </scroll-view>
                <view class="kp-dropdown-actions"><button size="mini" @click="kpDropdownOpen = false">收起知识树</button></view>
              </view>
            </view>
            <view class="selected-kp-list"><view v-for="kp in selectedKps" :key="kp.id" class="kp-tag"><text>{{ kp.name }}</text><text class="tag-remove" @click="removeKnowledgePoint(kp.id)">×</text></view><text v-if="!selectedKps.length" class="empty-hint">尚未选择知识点</text></view>
          </view>

          <view class="section-card">
            <view class="section-heading"><text class="section-title">标签编辑</text><button size="mini" @click="loadQuestionTags">刷新标签</button></view>
            <view class="tag-add-row"><input v-model="newTag" class="control" placeholder="输入标签名称" @confirm="addTag" /><button size="mini" type="primary" @click="addTag">添加标签</button></view>
            <view class="tag-list"><view v-for="tag in questionTags" :key="tag.id" class="edit-tag"><text>{{ tag.name }}</text><text class="tag-remove" @click="removeTag(tag.id)">×</text></view><text v-if="!questionTags.length" class="empty-hint">暂无标签</text></view>
          </view>
          <view class="editor-bottom-space"></view>

        </scroll-view>

        <scroll-view scroll-y class="render-pane">
          <view class="render-toolbar"><text class="section-title">渲染预览</text><text class="render-hint">图片显示尺寸与左侧画布保存的尺寸一致</text></view>
            <view class="render-card">
            <view class="render-stem"><text class="render-question-prefix">{{ form.question_no || question.question_no || '-' }}（{{ questionTypeLabel }}）.</text><view class="render-stem-content"><view v-html="stemHtml"></view><view v-if="renderedTables.length" class="render-tables"><view v-for="(table, tableIndex) in renderedTables" :key="table.table_id || tableIndex" class="render-table"><text class="render-table-caption">表格{{ renderedTables.length > 1 ? ` ${tableIndex + 1}` : '' }}</text><view class="render-data-grid" :style="{ gridTemplateColumns: table.gridColumns }"><view v-for="(cell, cellIndex) in table.cells" :key="cellIndex" class="render-data-cell" v-html="cell || '&nbsp;'" /></view></view></view></view></view>
            <view class="render-question-meta">
              <view class="render-meta-group"><text class="render-meta-label">难度</text><text class="render-meta-chip">{{ difficultyLabel }}</text></view>
              <view v-if="selectedKps.length" class="render-meta-group"><text class="render-meta-label">知识点</text><text v-for="kp in selectedKps" :key="kp.id" class="render-meta-chip">{{ kp.name }}</text></view>
              <view v-if="questionTags.length" class="render-meta-group"><text class="render-meta-label">标签</text><text v-for="tag in questionTags" :key="tag.id" class="render-meta-chip tag-chip">{{ tag.name }}</text></view>
            </view>
            <view v-if="images.length" class="render-images"><view v-for="image in images" :key="image.id" class="render-image-wrap"><image :src="getImageUrl(image.file_path)" mode="widthFix" class="render-image" :style="renderImageStyle(image)" @click="previewImage(image)" /><text v-if="image.description" class="render-image-caption">{{ image.description }}</text></view></view>
            <view v-if="isChoice" class="render-options"><view v-for="option in renderedOptions" :key="option.label" class="render-option"><text class="render-option-label">{{ option.label }}.</text><view v-html="option.html"></view></view></view>
            <view v-if="answerHtml" class="render-answer"><text class="render-label">答案</text><view v-html="answerHtml"></view></view>
            <view v-if="analysisHtml" class="render-answer"><text class="render-label">解析</text><view v-html="analysisHtml"></view></view>
            <view v-if="solutionHtml" class="render-answer"><text class="render-label">解答</text><view v-html="solutionHtml"></view></view>
          </view>
        </scroll-view>
      </view>
    </view>
    <view v-else-if="loading" class="state">加载中...</view><view v-else class="state">题目不存在</view>
    <QuestionAIControls
      :visible="showAiControls"
      :question-id="selectedAiQuestionId"
      @close="closeAiControls"
      @completed="handleAiCompleted"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { addQuestionTag, confirmQuestion, deleteQuestionImage, getQuestionAssets, getQuestionDetail, getQuestionTags, removeQuestionTag, restoreQuestionImageOriginal, updateQuestion, updateQuestionImageLayout, uploadQuestionImage } from '@/api/questions'
import { knowledgeApi } from '@/api/knowledge'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'
import { chooseImage } from '@/utils/image-upload'
import QuestionAIControls from '@/components/QuestionAIControls.vue'

type ImageItem = { id: string | number; file_path: string; description?: string; display_width?: number; can_restore_original?: boolean }
type KpLeaf = { id: string | number; name: string }
type KpChapter = { id: string; name: string; knowledge_points: KpLeaf[] }
type KpSemester = { id: string; name: string; chapters: KpChapter[] }
type KpGrade = { id: string; name: string; semesters: KpSemester[] }

const IMAGE_DEFAULT_WIDTH = 420
const QUESTION_TYPE_LABELS: Record<string, string> = { single_choice: '单选题', multiple_choice: '多选题', fill_blank: '填空题', short_answer: '简答题', solution: '解答题', essay: '论述题', true_false: '判断题', computation: '计算题', proof: '证明题', experiment: '实验题' }
const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multiple_choice', label: '多选题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'short_answer', label: '简答题' },
  { value: 'solution', label: '解答题' },
]
const questionTypeRange = QUESTION_TYPE_OPTIONS.map((item) => item.label)
const difficultyRange = ['基础巩固', '较易', '中等', '较难', '困难']
const question = ref<any>(null)
const questionId = ref('')
const selectedAiQuestionId = ref<string | number | null>(null)
const showAiControls = ref(false)
const loading = ref(true)
const saving = ref(false)
const form = ref({ stem: '', answer: '', analysis: '', solution: '', difficulty: 1, question_type: 'short_answer', question_no: '', page_start: 1, page_end: 1, options: [{ label: 'A', content: '' }, { label: 'B', content: '' }, { label: 'C', content: '' }, { label: 'D', content: '' }] })
const images = ref<ImageItem[]>([])
const stemHtml = ref('')
const answerHtml = ref('')
const analysisHtml = ref('')
const solutionHtml = ref('')
const renderedOptions = ref<Array<{ label: string; html: string }>>([])
const renderedTables = ref<Array<{ table_id?: string; gridColumns: string; cells: string[] }>>([])
type EditableTable = { table_id?: string; cells: string[][] }
const editableTables = ref<EditableTable[]>([])
let renderTimer: ReturnType<typeof setTimeout> | null = null
let lastWheelAt = 0

const questionTypeLabel = computed(() => QUESTION_TYPE_LABELS[form.value.question_type] || form.value.question_type || '未知题型')
const questionTypeIndex = computed(() => Math.max(0, QUESTION_TYPE_OPTIONS.findIndex((item) => item.value === form.value.question_type)))
const difficultyIndex = computed(() => Math.max(0, Math.min(4, Number(form.value.difficulty || 1) - 1)))
const difficultyLabel = computed(() => form.value.difficulty ? difficultyRange[Math.max(0, Math.min(4, Number(form.value.difficulty) - 1))] : '未评定')
const isChoice = computed(() => ['single_choice', 'multiple_choice'].includes(form.value.question_type))
const subjectLabel = computed(() => ({ physics: '物理', math: '数学', chemistry: '化学' } as Record<string, string>)[String(question.value?.subject || '')] || '当前科目')

function onQuestionTypeChange(event: any) {
  const index = Number(event?.detail?.value ?? 0)
  form.value.question_type = QUESTION_TYPE_OPTIONS[index]?.value || QUESTION_TYPE_OPTIONS[0].value
  scheduleRender()
}

function onDifficultyChange(event: any) {
  form.value.difficulty = Math.max(1, Math.min(5, Number(event?.detail?.value ?? 0) + 1))
}

function handleAiProcess() {
  selectedAiQuestionId.value = question.value.id
  showAiControls.value = true
}

function closeAiControls() {
  showAiControls.value = false
  selectedAiQuestionId.value = null
}

async function handleAiCompleted({ action }: { action: string }) {
  const questionId = String(selectedAiQuestionId.value || '')
  closeAiControls()
  if (questionId) await loadQuestion(questionId)
  void action
}

const knowledgeSearch = ref('')
const kpDropdownOpen = ref(false)
const expandedNodes = ref<Record<string, boolean>>({})
const knowledgeTree = ref<KpGrade[]>([])
const selectedKps = ref<Array<KpLeaf & { module: string }>>([])
const searchingKnowledge = computed(() => Boolean(knowledgeSearch.value.trim()))
function treeContains(value: string, keyword: string) { return value.toLowerCase().includes(keyword) }
const filteredKnowledgeTree = computed(() => {
  const keyword = knowledgeSearch.value.trim().toLowerCase()
  if (!keyword) return knowledgeTree.value
  return knowledgeTree.value.map((grade) => ({ ...grade, semesters: grade.semesters.map((semester) => ({ ...semester, chapters: semester.chapters.map((chapter) => ({ ...chapter, knowledge_points: chapter.knowledge_points.filter((kp) => treeContains(kp.name, keyword)) })).filter((chapter) => chapter.knowledge_points.length || treeContains(chapter.name, keyword)) })).filter((semester) => semester.chapters.length || treeContains(semester.name, keyword)) })).filter((grade) => grade.semesters.length || treeContains(grade.name, keyword))
})
function expanded(id: string) { return Boolean(expandedNodes.value[id]) }
function toggleTree(id: string) { expandedNodes.value[id] = !expandedNodes.value[id] }
function isKnowledgePointSelected(id: string | number) { return selectedKps.value.some((kp) => String(kp.id) === String(id)) }
function toggleKnowledgePoint(kp: KpLeaf) { if (isKnowledgePointSelected(kp.id)) removeKnowledgePoint(kp.id); else selectedKps.value.push({ ...kp, module: kp.name }) }
function removeKnowledgePoint(id: string | number) { selectedKps.value = selectedKps.value.filter((kp) => String(kp.id) !== String(id)) }

const questionTags = ref<Array<{ id: string | number; name: string }>>([])
const newTag = ref('')

const selectedImage = ref<ImageItem | null>(null)
const canvasSurface = ref<HTMLElement | null>(null)
const sourceImage = ref<HTMLImageElement | null>(null)
const imageRotation = ref(0)
const imageFlipped = ref(false)
const canvasWidth = ref(1)
const canvasHeight = ref(1)
const selection = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const selectionStart = ref<{ x: number; y: number } | null>(null)
const selectionInitial = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const selectionMode = ref<'create' | 'move' | 'resize'>('create')
const selecting = ref(false)
const cropping = ref(false)
const selectedImageWidth = computed(() => selectedImage.value ? displayWidth(selectedImage.value) : IMAGE_DEFAULT_WIDTH)
const canvasStyle = computed(() => ({ width: `${canvasWidth.value}px`, height: `${canvasHeight.value}px` }))
const canvasSurfaceStyle = computed(() => ({ ...canvasStyle.value, transform: `translate(-50%, -50%) rotate(${imageRotation.value}deg) scaleX(${imageFlipped.value ? -1 : 1})` }))
const hasImageTransform = computed(() => imageRotation.value % 360 !== 0 || imageFlipped.value)
const selectionStyle = computed(() => selection.value ? { left: `calc(50% + ${selection.value.x - canvasWidth.value / 2}px)`, top: `calc(50% + ${selection.value.y - canvasHeight.value / 2}px)`, width: `${selection.value.w}px`, height: `${selection.value.h}px` } : {})

function displayWidth(image: ImageItem) {
  const value = Number(image.display_width || 0)
  return value ? Math.max(80, Math.min(1200, Math.round(value))) : IMAGE_DEFAULT_WIDTH
}
function normalizeImage(image: any): ImageItem {
  const storedWidth = Number(image.display_width || 0)
  const display_width = storedWidth > 0 && storedWidth <= 200 ? IMAGE_DEFAULT_WIDTH : Math.max(80, Math.min(1200, Math.round(storedWidth || IMAGE_DEFAULT_WIDTH)))
  return { id: image.id, file_path: image.file_path || image.url || '', description: image.description || '', display_width, can_restore_original: Boolean(image.can_restore_original) }
}
function getImageUrl(path: string) { return getMediaUrl(path) }
function renderImageStyle(image: ImageItem) { return { width: `${displayWidth(image)}px`, maxWidth: '100%' } }
function stripPlaceholders(html: string) { return html.replace(/\{\{image_\d+\}\}/g, '') }
async function renderText(value: string) { return stripPlaceholders(await renderWithKatex(value || '')) }
function normalizePreviewRows(table: any): string[][] {
  const rows = Array.isArray(table?.rows)
    ? table.rows.filter((row: any) => Array.isArray(row) && row.some((cell: any) => String(cell ?? '').trim()))
    : []
  const width = Math.max(1, ...rows.map((row) => row.length))
  return rows.map((row) => row.map((cell: any) => String(cell ?? '')).concat(Array(Math.max(0, width - row.length)).fill('')))
}
function cloneEditableTables(tables: any): EditableTable[] {
  if (!Array.isArray(tables)) return []
  return tables.map((table: any, index: number) => ({ table_id: table?.table_id || `table_${index + 1}`, cells: normalizePreviewRows(table) })).filter((table) => table.cells.length > 0)
}
function tableColumnCount(table: EditableTable): number { return Math.max(1, ...table.cells.map((row) => row.length)) }
function tableGridColumns(table: EditableTable): string { return `repeat(${tableColumnCount(table)}, minmax(110px, 1fr))` }
function flattenedEditableCells(table: EditableTable): string[] { const width = tableColumnCount(table); return table.cells.flatMap((row) => row.concat(Array(Math.max(0, width - row.length)).fill(''))) }
function addTable() { editableTables.value.push({ table_id: `table_${Date.now()}`, cells: [['']] }); scheduleRender() }
function addTableRow(index: number) { const table = editableTables.value[index]; if (!table) return; table.cells.push(Array(tableColumnCount(table)).fill('')); scheduleRender() }
function addTableColumn(index: number) { const table = editableTables.value[index]; if (!table) return; table.cells.forEach((row) => row.push('')); scheduleRender() }
function removeTable(index: number) { editableTables.value.splice(index, 1); scheduleRender() }
function removeTableCell(tableIndex: number, cellIndex: number) { const table = editableTables.value[tableIndex]; if (!table) return; const width = tableColumnCount(table); const rowIndex = Math.floor(cellIndex / width); const columnIndex = cellIndex % width; if (table.cells[rowIndex]) table.cells[rowIndex].splice(columnIndex, 1); if (table.cells[rowIndex]?.length === 0) table.cells.splice(rowIndex, 1); if (table.cells.length === 0) editableTables.value.splice(tableIndex, 1); scheduleRender() }
async function renderPreviewTable(table: any) {
  const rows = normalizePreviewRows({ rows: table?.rows || table?.cells || [] })
  const width = Math.max(1, ...rows.map((row) => row.length))
  const cells = await Promise.all(rows.flatMap((row) => row).map((cell) => renderText(cell)))
  return { table_id: table?.table_id, gridColumns: `repeat(${width}, minmax(72px, 1fr))`, cells }
}
async function renderPreview() {
  stemHtml.value = await renderText(form.value.stem)
  answerHtml.value = await renderText(form.value.answer)
  analysisHtml.value = await renderText(form.value.analysis)
  solutionHtml.value = await renderText(form.value.solution)
  renderedOptions.value = await Promise.all(form.value.options.map(async (option) => ({ label: option.label, html: await renderText(option.content) })))
  renderedTables.value = await Promise.all(editableTables.value.map(renderPreviewTable))
}
function scheduleRender() { if (renderTimer) clearTimeout(renderTimer); renderTimer = setTimeout(renderPreview, 150) }

async function loadQuestion(id: string) {
  loading.value = true
  try {
    const response: any = await getQuestionDetail(id); const data = response.data || response
    if (!data?.id) return
    question.value = data
    form.value = { stem: data.display_stem || data.stem || '', answer: data.answer || '', analysis: data.analysis || '', solution: data.solution || '', difficulty: Number(data.difficulty || 1), question_type: data.question_type || 'short_answer', question_no: data.question_no || '', page_start: data.page_start || 1, page_end: data.page_end || 1, options: data.options?.length ? data.options.map((option: any) => ({ label: option.option_label || option.label, content: option.content || '' })) : form.value.options }
    editableTables.value = cloneEditableTables(data.tables)
    const assets: any = await getQuestionAssets(id)
    images.value = (assets.data?.images || data.images || []).map(normalizeImage)
    if (images.value[0]) selectImage(images.value[0])
    await Promise.all([renderPreview(), loadKnowledgeTree(), loadQuestionTags()])
  } catch (error) { console.error(error); uni.showToast({ title: '题目加载失败', icon: 'none' }) } finally { loading.value = false }
}

function findLeaf(id: string | number) { for (const grade of knowledgeTree.value) for (const semester of grade.semesters) for (const chapter of semester.chapters) { const kp = chapter.knowledge_points.find((item) => String(item.id) === String(id)); if (kp) return kp } return null }
async function loadKnowledgeTree() {
  try {
    const response: any = await knowledgeApi.getTree({ subject: String(question.value?.subject || '') })
    knowledgeTree.value = (response.data?.grades || []).map((grade: any) => ({ id: `grade-${grade.name}`, name: grade.name, semesters: (grade.semesters || []).map((semester: any) => ({ id: `semester-${grade.name}-${semester.name}`, name: semester.name, chapters: (semester.chapters || []).map((chapter: any) => ({ id: `chapter-${grade.name}-${semester.name}-${chapter.name}`, name: chapter.name, knowledge_points: (chapter.knowledge_points || []).map((kp: any) => ({ id: kp.id, name: kp.name || '未命名知识点' })) })) })) }))
    const expanded: Record<string, boolean> = {}
    knowledgeTree.value.forEach((grade) => {
      expanded[grade.id] = true
      grade.semesters.forEach((semester) => {
        expanded[semester.id] = true
        semester.chapters.forEach((chapter) => { expanded[chapter.id] = true })
      })
    })
    expandedNodes.value = expanded
    const raw = Array.isArray(question.value?.knowledge_points) ? question.value.knowledge_points : []
    selectedKps.value = raw.map((item: any) => findLeaf(typeof item === 'object' ? (item.id || item.knowledge_point_id) : item)).filter(Boolean).map((kp: any) => ({ ...kp, module: kp.name }))
  } catch { knowledgeTree.value = []; selectedKps.value = [] }
}

async function loadQuestionTags() { if (!questionId.value) return; try { const response: any = await getQuestionTags(questionId.value); questionTags.value = response.data || [] } catch { questionTags.value = [] } }
async function addTag() { const name = newTag.value.trim(); if (!name) return; try { await addQuestionTag(questionId.value, { tag_name: name }); newTag.value = ''; await loadQuestionTags() } catch { uni.showToast({ title: '添加标签失败', icon: 'none' }) } }
async function removeTag(tagId: string | number) { try { await removeQuestionTag(questionId.value, String(tagId)); questionTags.value = questionTags.value.filter((tag) => String(tag.id) !== String(tagId)) } catch { uni.showToast({ title: '删除标签失败', icon: 'none' }) } }

async function handleSave() { if (saving.value || !question.value) return; saving.value = true; try { const response: any = await updateQuestion(question.value.id, { ...form.value, tables: editableTables.value.map((table) => ({ table_id: table.table_id, rows: table.cells })), knowledge_points: selectedKps.value.map((kp) => ({ id: kp.id, module: kp.module })), tags: questionTags.value.map((tag) => tag.name) }); const saved = response?.data || response; if (saved?.tables) { question.value = { ...question.value, ...saved }; editableTables.value = cloneEditableTables(saved.tables) } uni.showToast({ title: '保存成功', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '保存失败', icon: 'none' }) } finally { saving.value = false } }
async function handleConfirm() { await handleSave(); if (!question.value) return; try { await confirmQuestion(question.value.id); uni.showToast({ title: '已确认题目', icon: 'success' }) } catch { uni.showToast({ title: '确认失败', icon: 'none' }) } }
function handleBack() { uni.navigateBack({ delta: 1 }) }
function handleBackToList() { handleBack() }
function handlePrevQuestion() { uni.showToast({ title: '已是当前题目', icon: 'none' }) }
function handleNextQuestion() { uni.showToast({ title: '已是当前题目', icon: 'none' }) }

async function reloadImages() { const previousId = selectedImage.value?.id; const response: any = await getQuestionAssets(questionId.value); images.value = (response.data?.images || []).map(normalizeImage); const next = images.value.find((image) => String(image.id) === String(previousId)) || images.value[0]; if (next) selectImage(next); else clearImageEditor() }
async function importImage() { try { const selected = await chooseImage({ count: 1, sourceType: 'album' }); const item = selected[0]; if (!item) return; uni.showLoading({ title: '正在上传图片' }); const response: any = await uploadQuestionImage(questionId.value, item.file || item.path, 'question-image.png'); if (response.code !== 0) throw new Error(response.message || '图片上传失败'); await reloadImages(); const image = images.value.find((item) => String(item.id) === String(response.data?.image?.id)) || images.value.at(-1); if (image) selectImage(image); uni.showToast({ title: '图片已导入', icon: 'success' }) } catch (error: any) { if (error?.message) uni.showToast({ title: error.message, icon: 'none' }) } finally { uni.hideLoading() } }
async function saveImage(image: ImageItem) { try { image.display_width = displayWidth(image); const response: any = await updateQuestionImageLayout(questionId.value, image.id, { placement: 'stem', display_width: image.display_width, description: image.description || '' }); if (response.data) Object.assign(image, normalizeImage(response.data)); uni.showToast({ title: '图片设置已保存', icon: 'success', duration: 800 }) } catch { uni.showToast({ title: '图片设置保存失败', icon: 'none' }) } }
async function deleteImage(image: ImageItem) { const result = await new Promise<any>((resolve) => uni.showModal({ title: '删除图片', content: '确定删除这张插图吗？', success: resolve })); if (!result.confirm) return; try { await deleteQuestionImage(questionId.value, image.id); if (selectedImage.value?.id === image.id) clearImageEditor(); await reloadImages(); uni.showToast({ title: '图片已删除', icon: 'success' }) } catch { uni.showToast({ title: '删除失败', icon: 'none' }) } }
async function restoreOriginalImage(image: ImageItem) { const result = await new Promise<any>((resolve) => uni.showModal({ title: '恢复原始图', content: '将撤销该图片的所有裁切、旋转和翻转，恢复为原始图。是否继续？', success: resolve })); if (!result.confirm) return; try { const response: any = await restoreQuestionImageOriginal(questionId.value, image.id); if (response.data) Object.assign(image, normalizeImage(response.data)); if (selectedImage.value?.id === image.id) selectImage(image); await reloadImages(); uni.showToast({ title: '已恢复原始图', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '恢复原始图失败', icon: 'none' }) } }
function previewImage(image: ImageItem) { uni.previewImage({ urls: [getImageUrl(image.file_path)] }) }

function selectImage(image: ImageItem) { selectedImage.value = image; selection.value = null; imageRotation.value = 0; imageFlipped.value = false; nextTick(() => loadCanvasImage(image)) }
function clearImageEditor() { selectedImage.value = null; sourceImage.value = null; selection.value = null; selectionStart.value = null; imageRotation.value = 0; imageFlipped.value = false }
function loadCanvasImage(image: ImageItem) { canvasWidth.value = displayWidth(image); canvasHeight.value = 280; if (typeof Image === 'undefined') return; const source = new Image(); source.onload = () => { sourceImage.value = source; refreshCanvasSurface() }; source.onerror = () => uni.showToast({ title: '图片加载失败，无法编辑', icon: 'none' }); source.src = getImageUrl(image.file_path) }
function refreshCanvasSurface() { const source = sourceImage.value; if (!source || !selectedImage.value) return; const width = displayWidth(selectedImage.value); const scale = width / source.naturalWidth; canvasWidth.value = width; canvasHeight.value = Math.max(1, Math.round(source.naturalHeight * scale)) }
function changeImageScale(delta: number) { if (!selectedImage.value) return; selectedImage.value.display_width = Math.max(80, Math.min(1200, displayWidth(selectedImage.value) + delta)); selection.value = null; refreshCanvasSurface() }
function zoomIn() { changeImageScale(24) }
function zoomOut() { changeImageScale(-24) }
function handleCanvasWheel(event: any) { const now = Date.now(); if (now - lastWheelAt < 36) return; lastWheelAt = now; const deltaY = Number(event?.deltaY ?? event?.detail?.deltaY ?? event?.detail?.delta ?? 0); const wheelDelta = Number(event?.wheelDelta ?? event?.detail?.wheelDelta ?? 0); const direction = deltaY ? (deltaY < 0 ? 1 : -1) : (wheelDelta ? (wheelDelta > 0 ? 1 : -1) : 0); if (direction) changeImageScale(direction * 24) }
function resetImageScale() { if (!selectedImage.value) return; selectedImage.value.display_width = IMAGE_DEFAULT_WIDTH; selection.value = null; refreshCanvasSurface() }
function rotateLeft() { imageRotation.value = (imageRotation.value + 270) % 360; selection.value = null }
function rotateRight() { imageRotation.value = (imageRotation.value + 90) % 360; selection.value = null }
function flipHorizontal() { imageFlipped.value = !imageFlipped.value; selection.value = null }
async function saveImageTransform() {
  if (!selectedImage.value || !sourceImage.value || !hasImageTransform.value || cropping.value) return
  if (typeof document === 'undefined') { uni.showToast({ title: '当前环境不支持图片变换', icon: 'none' }); return }
  cropping.value = true
  try {
    const source = sourceImage.value
    const rotation = ((imageRotation.value % 360) + 360) % 360
    const output = document.createElement('canvas')
    const quarterTurn = rotation === 90 || rotation === 270
    output.width = quarterTurn ? source.naturalHeight : source.naturalWidth
    output.height = quarterTurn ? source.naturalWidth : source.naturalHeight
    const context = output.getContext('2d')
    if (!context) throw new Error('浏览器不支持图片变换')
    context.translate(output.width / 2, output.height / 2)
    context.rotate(rotation * Math.PI / 180)
    context.scale(imageFlipped.value ? -1 : 1, 1)
    context.drawImage(source, -source.naturalWidth / 2, -source.naturalHeight / 2)
    const blob = await new Promise<Blob>((resolve, reject) => output.toBlob((value) => value ? resolve(value) : reject(new Error('图片变换失败')), 'image/png'))
    const oldImage = selectedImage.value
    const uploaded: any = await uploadQuestionImage(questionId.value, new File([blob], 'transformed-image.png', { type: 'image/png' }), 'transformed-image.png', oldImage.id)
    if (uploaded.code !== 0) throw new Error(uploaded.message || '变换图片上传失败')
    const newId = uploaded.data?.image?.id
    if (!newId) throw new Error('变换图片保存失败')
    await updateQuestionImageLayout(questionId.value, newId, { placement: 'stem', display_width: displayWidth(oldImage), description: oldImage.description || '' })
    await deleteQuestionImage(questionId.value, oldImage.id)
    imageRotation.value = 0
    imageFlipped.value = false
    selection.value = null
    await reloadImages()
    const replacement = images.value.find((item) => String(item.id) === String(newId))
    if (replacement) selectImage(replacement)
    uni.showToast({ title: '图片变换已保存', icon: 'success' })
  } catch (error: any) { uni.showToast({ title: error?.message || '图片变换失败', icon: 'none' }) } finally { cropping.value = false }
}
function surfaceElement(): HTMLElement | null { const surface: any = canvasSurface.value; if (surface?.getBoundingClientRect) return surface as HTMLElement; if (surface?.$el?.getBoundingClientRect) return surface.$el as HTMLElement; if (typeof document !== 'undefined') return document.querySelector('.canvas-surface') as HTMLElement | null; return null }
function canvasPoint(event: any) { const surface = surfaceElement(); if (!surface) return { x: 0, y: 0 }; const rect = surface.getBoundingClientRect(); const clientX = Number(event?.clientX ?? event?.detail?.x ?? 0); const clientY = Number(event?.clientY ?? event?.detail?.y ?? 0); return { x: Math.max(0, Math.min(canvasWidth.value, clientX - rect.left)), y: Math.max(0, Math.min(canvasHeight.value, clientY - rect.top)) } }
function startSelection(event: any) { if ((event?.button !== undefined && event.button !== 0) || (event.target as HTMLElement)?.classList?.contains('selection-resize')) return; selecting.value = true; selectionMode.value = 'create'; selectionStart.value = canvasPoint(event); selection.value = null }
function startSelectionMove(event: any) { if (!selection.value) return; selecting.value = true; selectionMode.value = 'move'; selectionStart.value = canvasPoint(event); selectionInitial.value = { ...selection.value } }
function startSelectionResize(event: any) { if (!selection.value) return; selecting.value = true; selectionMode.value = 'resize'; selectionStart.value = canvasPoint(event); selectionInitial.value = { ...selection.value } }
function moveSelection(event: any) { if (!selecting.value || !selectionStart.value) return; const point = canvasPoint(event); const start = selectionStart.value; if (selectionMode.value === 'create') selection.value = { x: Math.min(start.x, point.x), y: Math.min(start.y, point.y), w: Math.abs(point.x - start.x), h: Math.abs(point.y - start.y) }; else if (selectionMode.value === 'move' && selectionInitial.value) { const initial = selectionInitial.value; selection.value = { ...initial, x: Math.max(0, Math.min(canvasWidth.value - initial.w, initial.x + point.x - start.x)), y: Math.max(0, Math.min(canvasHeight.value - initial.h, initial.y + point.y - start.y)) } } else if (selectionMode.value === 'resize' && selectionInitial.value) { const initial = selectionInitial.value; selection.value = { ...initial, w: Math.max(8, Math.min(canvasWidth.value - initial.x, initial.w + point.x - start.x)), h: Math.max(8, Math.min(canvasHeight.value - initial.y, initial.h + point.y - start.y)) } } }
function endSelection() { selecting.value = false }
async function cropSelectedImage() { if (!selectedImage.value || !sourceImage.value || !selection.value || selection.value.w < 8 || selection.value.h < 8 || cropping.value) return; if (typeof document === 'undefined') { uni.showToast({ title: '当前环境不支持画布裁切', icon: 'none' }); return }; cropping.value = true; try { const source = sourceImage.value; const scale = canvasWidth.value / source.naturalWidth; const rect = selection.value; const output = document.createElement('canvas'); output.width = Math.max(1, Math.round(rect.w / scale)); output.height = Math.max(1, Math.round(rect.h / scale)); const context = output.getContext('2d'); if (!context) throw new Error('浏览器不支持图片裁切'); context.drawImage(source, Math.round(rect.x / scale), Math.round(rect.y / scale), output.width, output.height, 0, 0, output.width, output.height); const blob = await new Promise<Blob>((resolve, reject) => output.toBlob((value) => value ? resolve(value) : reject(new Error('图片裁切失败')), 'image/png')); const oldImage = selectedImage.value; const uploaded: any = await uploadQuestionImage(questionId.value, new File([blob], 'cropped-image.png', { type: 'image/png' }), 'cropped-image.png', oldImage.id); if (uploaded.code !== 0) throw new Error(uploaded.message || '裁切图片上传失败'); const newId = uploaded.data?.image?.id; if (newId) await updateQuestionImageLayout(questionId.value, newId, { placement: 'stem', display_width: displayWidth(oldImage), description: oldImage.description || '' }); await deleteQuestionImage(questionId.value, oldImage.id); await reloadImages(); const replacement = images.value.find((item) => String(item.id) === String(newId)); if (replacement) selectImage(replacement); uni.showToast({ title: '裁切完成，可随时恢复原始图', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '裁切失败', icon: 'none' }) } finally { cropping.value = false } }

function onKeyDown(event: KeyboardEvent) { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); handleSave() } }
onLoad((options) => { questionId.value = String(options?.id || '') })
onMounted(async () => { if (questionId.value) await loadQuestion(questionId.value); if (typeof window !== 'undefined') window.addEventListener('keydown', onKeyDown) })
onUnmounted(() => { if (typeof window !== 'undefined') window.removeEventListener('keydown', onKeyDown); if (renderTimer) clearTimeout(renderTimer) })
</script>

<style scoped>
.edit-page { min-height: 100vh; background: #f3f5f8; color: #303133; }
.editor-shell { height: 100vh; display: flex; flex-direction: column; }
.page-header { display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; padding: 14px 22px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.page-title { display: block; font-size: 18px; font-weight: 600; }.page-subtitle { display: block; margin-top: 4px; color: #909399; font-size: 12px; }
.header-actions, .image-actions, .canvas-footer, .tag-add-row { display: flex; align-items: center; gap: 8px; }.header-actions button, .image-actions button, .canvas-footer button, .tag-add-row button { margin: 0; }
.workspace { display: flex; flex: 1; min-height: 0; gap: 12px; padding: 12px; }.editor-pane { width: 52%; min-width: 0; padding-bottom: 56px; box-sizing: border-box; }.render-pane { width: 48%; min-width: 0; padding: 0 4px 48px; box-sizing: border-box; }
.section-card, .render-card { margin-bottom: 12px; padding: 18px; border-radius: 8px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.04); }.section-heading, .render-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }.section-title { font-size: 15px; font-weight: 600; }.section-hint, .render-hint { color: #909399; font-size: 12px; }
.meta-grid { display: grid; grid-template-columns: 1.3fr 1fr .7fr; gap: 10px; margin-bottom: 14px; }.field, .content-field { margin-bottom: 14px; }.field-label { display: block; margin-bottom: 6px; color: #606266; font-size: 13px; font-weight: 600; }
.control, .editor-textarea, .image-name { box-sizing: border-box; width: 100%; border: 1px solid #dcdfe6; border-radius: 5px; background: #fff; color: #303133; font-size: 13px; }.control { height: 34px; padding: 0 9px; }.picker-control { display: flex; align-items: center; justify-content: center; min-width: 0; line-height: 1.2; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.editor-textarea { display: block; min-height: 108px; padding: 10px; line-height: 1.7; resize: vertical; }.stem-field .editor-textarea { min-height: 132px; }.question-uuid { margin-left: 8px; color: #909399; font-size: 11px; font-weight: 400; user-select: all; }.option-editor { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }.option-label { min-width: 16px; padding-top: 10px; color: #409eff; font-weight: 600; }.option-textarea { min-height: 58px; height: 68px; max-height: 130px; }.answer-textarea { min-height: 46px; height: 52px; }.analysis-textarea { min-height: 150px; }
.tables-field { overflow: hidden; }.table-editor-heading, .table-editor-toolbar, .table-editor-actions { display: flex; align-items: center; }.table-editor-heading, .table-editor-toolbar { justify-content: space-between; gap: 8px; }.table-editor-hint { color: #909399; font-size: 11px; }.table-editor { margin-top: 8px; padding: 8px; border: 1px solid #dcdfe6; border-radius: 5px; background: #fafafa; }.table-editor-title { color: #606266; font-size: 12px; font-weight: 600; }.table-editor-actions { gap: 5px; }.table-editor-actions button, .table-cell-remove { margin: 0; }.table-editor-scroll { margin-top: 8px; width: 100%; }.table-editor-grid { display: grid; width: max-content; min-width: 100%; border-top: 1px solid #dcdfe6; border-left: 1px solid #dcdfe6; }.table-editor-cell { position: relative; min-width: 110px; min-height: 36px; padding: 3px 25px 3px 3px; border-right: 1px solid #dcdfe6; border-bottom: 1px solid #dcdfe6; background: #fff; box-sizing: border-box; }.table-cell-input { width: 100%; height: 30px; padding: 0 5px; border: 1px solid #ebeef5; border-radius: 3px; box-sizing: border-box; color: #303133; font-size: 12px; }.table-cell-remove { position: absolute; top: 5px; right: 2px; width: 20px; height: 24px; padding: 0; color: #f56c6c; font-size: 15px; line-height: 20px; }
.kp-picker { position: relative; }.kp-dropdown-panel { position: relative; z-index: 3; margin-top: 6px; overflow: hidden; border: 1px solid #dcdfe6; border-radius: 6px; background: #fff; box-shadow: 0 3px 12px rgba(0,0,0,.1); }.knowledge-tree-scroll { height: 420px; padding: 6px 0; box-sizing: border-box; }.tree-row { display: flex; align-items: center; min-height: 30px; gap: 6px; padding-right: 8px; color: #303133; font-size: 12px; cursor: pointer; }.tree-row:hover { background: #f5f7fa; }.tree-arrow { width: 14px; text-align: center; color: #909399; }.tree-grade { padding-left: 8px; font-weight: 600; }.tree-semester { padding-left: 26px; }.tree-chapter { padding-left: 44px; }.tree-leaf { min-height: 32px; padding-left: 60px; cursor: pointer; }.tree-checkbox { display: flex; width: 16px; height: 16px; align-items: center; justify-content: center; flex: 0 0 16px; border: 1px solid #bfc7d3; border-radius: 3px; color: #fff; background: #fff; font-size: 12px; }.tree-checkbox.checked { border-color: #409eff; background: #409eff; }.kp-dropdown-actions { padding: 8px; border-top: 1px solid #ebeef5; text-align: right; }.selected-kp-list, .tag-list { display: flex; flex-wrap: wrap; gap: 6px; min-height: 34px; margin-top: 8px; padding: 8px; border-radius: 5px; background: #fafafa; }.kp-tag { padding: 4px 8px; border-radius: 12px; color: #409eff; background: #ecf5ff; font-size: 12px; }.tag-remove { margin-left: 5px; color: #f56c6c; cursor: pointer; }.tag-add-row .control { flex: 1; }.edit-tag { padding: 4px 9px; border-radius: 12px; color: #67c23a; background: #f0f9eb; font-size: 12px; }
.image-list { display: flex; flex-direction: column; gap: 10px; }.image-item { display: flex; gap: 10px; padding: 10px; border: 1px solid #ebeef5; border-radius: 6px; }.image-item.active { border-color: #409eff; box-shadow: 0 0 0 2px rgba(64,158,255,.12); }.image-thumb { width: 104px; height: 82px; flex: 0 0 104px; border-radius: 4px; background: #f5f7fa; cursor: pointer; }.image-settings { display: flex; flex: 1; min-width: 0; flex-direction: column; justify-content: space-between; }.image-name { height: 32px; padding: 0 8px; }.image-actions { justify-content: flex-end; margin-top: 8px; }
.empty-hint { color: #a0a5ad; font-size: 12px; }
.editor-bottom-space { height: 64px; }
.canvas-editor { margin-top: 14px; padding: 12px; border: 1px solid #bfdcff; border-radius: 8px; background: #f8fbff; }.canvas-title { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #606266; font-size: 12px; }.canvas-title text:first-child { color: #303133; font-weight: 600; }.canvas-tools { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; margin: -2px 0 10px; }.canvas-tools button { margin: 0; }.canvas-stage { position: relative; height: 320px; overflow: hidden; overscroll-behavior: contain; touch-action: none; user-select: none; background: #e9eef5; cursor: crosshair; }.canvas-surface { position: absolute; z-index: 1; left: 50%; top: 50%; display: block; max-width: none; transform: translate(-50%, -50%); }.canvas-image { display: block; max-width: none; object-fit: fill; pointer-events: none; }.selection-box { position: absolute; z-index: 2; border: 2px solid #409eff; background: rgba(64,158,255,.16); cursor: move; }.selection-resize { position: absolute; right: -6px; bottom: -6px; width: 10px; height: 10px; border: 1px solid #fff; border-radius: 2px; background: #409eff; cursor: nwse-resize; }.canvas-footer { justify-content: space-between; margin-top: 10px; color: #606266; font-size: 12px; }
.render-toolbar { padding: 4px 4px 10px; }.render-card { min-height: calc(100vh - 110px); font-size: 14px; line-height: 1.8; }.render-stem { display: flex; align-items: flex-start; gap: 4px; }.render-question-prefix { flex: 0 0 auto; color: #303133; font-weight: 700; }.render-stem-content { min-width: 0; flex: 1; }.render-stem-content :deep(p:first-child) { margin-top: 0; }.render-tables { margin-top: 12px; overflow-x: auto; }.render-table { min-width: 100%; margin-bottom: 12px; }.render-table-caption { display: block; margin-bottom: 4px; color: #909399; font-size: 12px; }.render-data-grid { display: grid; width: max-content; min-width: 100%; border-top: 1px solid #dcdfe6; border-left: 1px solid #dcdfe6; }.render-data-cell { min-width: 72px; min-height: 28px; padding: 5px 7px; box-sizing: border-box; white-space: pre-wrap; overflow-wrap: anywhere; border-right: 1px solid #dcdfe6; border-bottom: 1px solid #dcdfe6; color: #606266; background: #fff; }.render-question-meta { display: flex; flex-wrap: wrap; gap: 7px 14px; margin: 10px 0 14px; padding: 8px 10px; border-radius: 5px; background: #f7f9fc; }.render-meta-group { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; }.render-meta-label { color: #909399; font-size: 12px; }.render-meta-chip { padding: 1px 7px; border-radius: 10px; color: #409eff; background: #ecf5ff; font-size: 12px; line-height: 20px; }.tag-chip { color: #67c23a; background: #f0f9eb; }.render-options { margin-top: 14px; }.render-option { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 9px; }.render-option-label { min-width: 16px; color: #409eff; font-weight: 600; }.render-images { margin: 14px 0; }.render-image-wrap { display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 12px; overflow: hidden; }.render-image { display: block; border-radius: 4px; cursor: pointer; }.render-image-caption { margin-top: 4px; color: #606266; font-size: 12px; }.render-answer { margin-top: 16px; padding: 12px; border-left: 3px solid #409eff; border-radius: 4px; background: #f8fafc; }.render-label { display: block; margin-bottom: 5px; color: #409eff; font-weight: 600; }.state { padding: 100px 0; text-align: center; color: #909399; }
@media (max-width: 900px) { .editor-shell { height: auto; min-height: 100vh; }.workspace { flex-direction: column; }.editor-pane, .render-pane { width: 100%; }.render-card { min-height: 300px; }.meta-grid { grid-template-columns: 1fr; }.canvas-title, .canvas-footer { align-items: flex-start; flex-direction: column; } }
</style>
