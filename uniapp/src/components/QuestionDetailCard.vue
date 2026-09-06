<template>
  <view class="q-card" :class="{ compact, selected }" :id="'q-' + question.id">
    <!-- 题头 -->
    <view class="card-header">
      <text class="q-num" :style="{ background: diffColor }">{{ index }}</text>
      <text class="q-title" :class="'diff-l' + question.difficulty">第 {{ question.question_no }} 题</text>
      <text class="q-uuid" @click.stop="copyUuid">UUID: {{ question.id }}</text>
      <text class="q-type-tag">{{ questionTypeLabel }}</text>
      <button size="mini" class="qr-button" @click.stop="previewImg(qrUrl)">二维码</button>
      <text class="q-creator">{{ question.creator_name || question.paper_title || '' }} {{ formatDate(question.created_at) }}</text>
    </view>

    <!-- 题干 -->
    <view class="q-body" :class="{ 'compact-body': compact }">
      <text v-if="compact" class="compact-stem">{{ compactStem }}</text>
      <view v-else class="stem-content" v-html="stemHtml"></view>
    </view>

    <view v-if="compact" class="compact-actions">
      <view class="check-box footer-check" :class="{ checked: selected }" @click.stop="toggleCheck">
        <text v-if="selected" class="check-mark">&#10003;</text>
      </view>
      <button size="mini" @click="$emit('edit', question.id)">编辑</button>
      <button size="mini" @click="$emit('related', question.id)">关联题</button>
      <button size="mini" @click="$emit('edit-tags', question)">标签编辑</button>
      <button size="mini" @click="$emit('add-favorite', question.id)">加入精选</button>
      <slot name="course-footer-actions" />
    </view>

    <!-- 题目配图 -->
    <view v-if="!compact && diagramImages.length > 0" class="q-images">
      <view class="image-row">
        <view v-for="(img, idx) in diagramImages" :key="idx" class="img-cell">
          <image :src="img.url" mode="widthFix" class="q-img" :style="imageStyle(img)" @click="previewImg(img.url)" />
          <text v-if="img.caption" class="img-label">{{ img.caption }}</text>
        </view>
      </view>
    </view>

    <!-- 选择题选项 -->
    <view v-if="!compact && isChoiceType" class="q-options">
      <view v-for="opt in options" :key="opt.label" class="opt-row">
        <text class="opt-label" :style="{ color: optColor }">{{ opt.label }}.</text>
        <view class="opt-content" v-html="opt.html"></view>
      </view>
    </view>

    <!-- 子问题 -->
    <view v-if="!compact && subquestions.length > 0" class="q-subquestions">
      <view v-for="(sub, idx) in subquestions" :key="idx" class="sub-row">
        <text class="sub-label">({{ sub.label || (idx + 1) }})</text>
        <view class="sub-content" v-html="sub.html"></view>
      </view>
    </view>

    <!-- 知识点标签 -->
    <view v-if="!compact" class="q-tags">
      <view class="tag-group">
        <text class="tag-title">● 知识点</text>
        <view v-for="kp in question.knowledge_points_display || []" :key="kp.id" class="tag kp-tag">{{ kp.name }}</view>
      </view>
      <view class="tag-group">
        <text class="tag-title">● 标签</text>
        <view v-for="tag in question.tags || []" :key="tag" class="tag label-tag">{{ tag }}</view>
      </view>
      <view class="tag-group">
        <text class="tag-title">● 难度</text>
        <text class="tag label-tag difficulty-tag">{{ difficultyStars }}</text>
      </view>
      <view v-if="question.source_collection" class="tag-group">
        <text class="tag-title">● 来源</text>
        <text class="source-link">{{ question.source_collection }}</text>
      </view>
    </view>

    <!-- 底部操作栏 -->
    <view v-if="!compact" class="q-footer">
      <view class="q-footer-right">
        <view class="check-box footer-check" :class="{ checked: selected }" @click.stop="toggleCheck">
          <text v-if="selected" class="check-mark">&#10003;</text>
        </view>
        <button size="mini" @click="$emit('toggle-answer')">答案</button>
        <button size="mini" class="btn-ai-answer" @click="$emit('ai-answer', 'ALL')">AI答案</button>
        <button size="mini" class="btn-ai-answer mode-a" @click="$emit('ai-answer', 'A')">A模式答案</button>
        <button size="mini" class="btn-ai-answer mode-b" @click="$emit('ai-answer', 'B')">B模式答案</button>
        <button size="mini" class="btn-ai-answer mode-c" @click="$emit('ai-answer', 'C')">C模式答案</button>
        <button size="mini" @click="$emit('edit', question.id)">编辑</button>
        <button size="mini" @click="$emit('related', question.id)">关联题</button>
        <button size="mini" @click="$emit('edit-tags', question)">标签编辑</button>
        <button size="mini" @click="$emit('add-favorite', question.id)">加入精选</button>
        <slot name="course-footer-actions" />
      </view>
    </view>

    <!-- 答案区 (可折叠) -->
    <view v-if="showAnswer" class="q-answer">
      <view v-if="question.answer" class="answer-item">
        <text class="answer-label">【答案】</text>
        <view v-html="answerHtml"></view>
      </view>
      <view v-if="question.analysis" class="answer-item">
        <text class="answer-label">【解析】</text>
        <view v-html="analysisHtml"></view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'
import { getQuestionTypeLabel } from '@/utils/question-type'

const props = defineProps<{
  question: any
  index: number
  showAnswer: boolean
  selected?: boolean
  compact?: boolean
}>()

const stemHtml = ref('')
const answerHtml = ref('')
const analysisHtml = ref('')
const optionHtmls = ref<Record<string, string>>({})
const subquestionHtmls = ref<string[]>([])
const emit = defineEmits(['edit', 'related', 'toggle-answer', 'add-favorite', 'edit-tags', 'check', 'ai-answer'])
function toggleCheck() { emit('check', props.question.id) }

const options = computed(() => {
  return (props.question.options || []).map((opt: any) => ({
    ...opt,
    html: optionHtmls.value[opt.label] || opt.content || '',
  }))
})

const subquestions = computed(() => {
  return (props.question.subquestions || []).map((sub: any, idx: number) => ({
    ...sub,
    label: sub.label || String(idx + 1),
    html: subquestionHtmls.value[idx] || sub.stem || '',
  }))
})

const isChoiceType = computed(() =>
  ['single_choice', 'multiple_choice'].includes(props.question.question_type)
)

const questionTypeLabel = computed(() => getQuestionTypeLabel(
  props.question.question_type,
  props.question.stem,
  props.question.options,
))

const difficultyStars = computed(() => {
  const level = Math.max(0, Math.min(5, Math.round(Number(props.question.difficulty || 0))))
  return level ? '★'.repeat(level) + '☆'.repeat(5 - level) : '-'
})

const compactStem = computed(() => {
  const stem = String(props.question.stem || '').replace(/\s+/g, ' ').trim()
  return stem.length > 25 ? `${stem.slice(0, 25)}...` : stem
})

const qrUrl = computed(() => {
  // #ifdef APP-PLUS
  return `https://qisi.chengxuelu.com/api/v1/questions/${props.question.id}/qr/`
  // #endif
  // #ifndef APP-PLUS
  return `/api/v1/questions/${props.question.id}/qr/`
  // #endif
})

const diffColor = computed(() => {
  const colors: Record<number, string> = { 1: '#67c23a', 2: '#409eff', 3: '#e6a23c', 4: '#f56c6c', 5: '#9924ff' }
  return colors[props.question.difficulty] || '#909399'
})

const optColor = computed(() => '#409eff')

const questionImages = computed(() => {
  const images = props.question.images || []
  return images.map((img: any) => ({
    url: getMediaUrl(img.file_path || img.url),
    caption: img.description || '',
    type: img.image_type || 'other',
    displayWidth: Number(img.display_width || 0),
  }))
})

// 题目配图（非公式类型）
const diagramImages = computed(() => {
  return questionImages.value.filter(img => img.type === 'diagram')
})

function imageStyle(image: { displayWidth?: number }) {
  const width = image.displayWidth && image.displayWidth > 200 ? Math.min(1200, image.displayWidth) : 420
  return { width: `${width}px`, maxWidth: '100%' }
}

function getImageUrl(path: string): string {
  if (!path) return ''
  if (path.startsWith('http')) return path
  // #ifdef APP-PLUS
  return 'https://qisi.chengxuelu.com/media/' + path.replace(/\\/g, '/')
  // #endif
  // #ifndef APP-PLUS
  // H5端使用相对路径，由开发服务器代理
  return '/media/' + path.replace(/\\/g, '/')
  // #endif
}

// 快速判断文本是否包含 LaTeX 公式标记
function hasMathMarkers(text: string): boolean {
  if (!text) return false
  return text.includes('$') || text.includes('\\[') || text.includes('\\(')
}

// 轻量渲染：纯文本直接转HTML，跳过KaTeX
function quickRender(text: string): string {
  if (!text) return '<span style="color:#999">(无内容)</span>'
  if (!hasMathMarkers(text)) {
    // 纯文本，直接转义换行符
    return text.replace(/\n/g, '<br/>')
  }
  return '' // 需要KaTeX渲染，返回空由调用方处理
}

function previewImg(url: string) {
  uni.previewImage({ urls: [url] })
}

function copyUuid() {
  uni.setClipboardData({
    data: String(props.question.id),
    success: () => uni.showToast({ title: 'UUID已复制', icon: 'none' }),
  })
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  return dateStr.slice(0, 10)
}

async function renderContent() {
  const q = props.question

  // 题干：直接渲染，不追加公式文本
  const stemSource = q.stem_html || q.stem || ''
  stemHtml.value = quickRender(stemSource)
  if (!stemHtml.value) stemHtml.value = await renderWithKatex(stemSource)

  // 答案和解析
  answerHtml.value = quickRender(q.answer || '')
  if (!answerHtml.value) answerHtml.value = await renderWithKatex(q.answer || '')

  analysisHtml.value = quickRender(q.analysis || '')
  if (!analysisHtml.value) analysisHtml.value = await renderWithKatex(q.analysis || '')

  // 渲染选项
  const newOptHtmls: Record<string, string> = {}
  for (const opt of q.options || []) {
    const optionSource = opt.content_html || opt.content || ''
    const html = quickRender(optionSource)
    newOptHtmls[opt.label] = html || await renderWithKatex(optionSource)
  }
  optionHtmls.value = newOptHtmls

  // 渲染子问题
  const newSubHtmls: string[] = []
  for (const sub of q.subquestions || []) {
    const html = quickRender(sub.stem || '')
    newSubHtmls.push(html || await renderWithKatex(sub.stem || ''))
  }
  subquestionHtmls.value = newSubHtmls
}

watch(() => props.question, renderContent, { immediate: true, deep: true })
onMounted(renderContent)
</script>

<style scoped>
.q-card {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border: 1px solid transparent;
}
.q-card.selected { border-color: #409eff; box-shadow: 0 0 0 2px rgba(64, 158, 255, .15); }
.q-card.compact { padding: 14px 20px; }
.q-uuid { font-size: 11px; color: #409eff; word-break: break-all; cursor: pointer; }
.q-qr { width: 42px; height: 42px; margin-left: 8px; }
.qr-button { margin: 0; padding: 0 8px; color: #409eff; border: 1px solid #b3d8ff; background: #ecf5ff; }
.footer-check { margin-right: 2px; order: 99; }
.compact-body { margin-bottom: 8px; }
.compact-body .stem-content { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.compact-stem { font-size: 14px; line-height: 1.6; color: #303133; }
.compact-actions { display: flex; justify-content: flex-end; gap: 6px; }
.btn-ai-answer { color: #c2410c; background: #fff7ed; border: 1px solid #fdba74; }
.btn-ai-answer.mode-a, .btn-ai-answer.mode-b, .btn-ai-answer.mode-c { color: #1d4ed8; background: #eff6ff; border-color: #93c5fd; }

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
  flex-wrap: wrap;
  min-width: 0;
}

.q-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #fff;
  font-size: 14px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.q-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.q-type-tag {
  font-size: 11px;
  color: #409eff;
  background: #ecf5ff;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
  flex-shrink: 0;
}

.q-creator {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.q-body {
  margin-bottom: 16px;
}

.stem-content {
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

.q-images {
  margin-bottom: 16px;
}

.image-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.img-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.q-img {
  border-radius: 4px;
  cursor: pointer;
}

.img-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.q-options {
  margin-bottom: 16px;
}

.opt-row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 26px;
  margin-bottom: 4px;
  overflow: hidden;
}

.opt-label {
  font-weight: bold;
  font-size: 14px;
  min-width: 20px;
}

.opt-content {
  flex: 1;
  font-size: 14px;
  min-width: 0;
  overflow: hidden;
  color: #303133;
  line-height: 26px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/*
 * Do not use :deep(*) here. uni-app compiles it to a universal selector
 * (`.opt-content.data-v-xxxx *`), which WXSS rejects. The container styles
 * above already provide the required compact option layout on all targets.
 */

.q-subquestions {
  margin-bottom: 16px;
}

.sub-row {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin-bottom: 8px;
}

.sub-label {
  font-weight: bold;
  color: #409eff;
  font-size: 14px;
  flex-shrink: 0;
}

.sub-content {
  flex: 1;
  font-size: 14px;
  line-height: 1.6;
}

.q-tags {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
}

.tag-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-title {
  font-size: 12px;
  color: #909399;
}

.tag {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 11px;
}

.kp-tag {
  background: #ecf5ff;
  color: #409eff;
}

.label-tag {
  background: #f0f9eb;
  color: #67c23a;
}

.source-link {
  font-size: 12px;
  color: #409eff;
  cursor: pointer;
}

.q-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}
.q-footer-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.check-box {
  width: 22px; height: 22px;
  border: 2px solid #dcdfe6;
  border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
  background: #fff;
}
.check-box.checked {
  background: #67c23a;
  border-color: #67c23a;
}
.check-mark {
  color: #fff;
  font-size: 14px;
  font-weight: bold;
}

.q-answer {
  margin-top: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.answer-item {
  margin-bottom: 12px;
}

.answer-item:last-child {
  margin-bottom: 0;
}

.answer-label {
  font-weight: bold;
  color: #409eff;
  font-size: 13px;
  margin-right: 8px;
}

.diff-l1 { color: #67c23a; }
.diff-l2 { color: #409eff; }
.diff-l3 { color: #e6a23c; }
.diff-l4 { color: #f56c6c; }
.diff-l5 { color: #9924ff; }
</style>
