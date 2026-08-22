<template>
  <view class="answer-page">
    <view class="question-panel">
      <view class="question-header">
        <text class="q-no">同类题 {{ currentIndex + 1 }}/{{ questions.length }}</text>
        <text class="q-type">{{ getQuestionTypeLabel(currentQuestion.question_type, currentQuestion.stem, choiceOptions, currentQuestion.answer) }}</text>
      </view>

      <view class="stem" v-html="renderedStem"></view>
      <image v-for="(img, i) in (currentQuestion.images || [])" :key="img.id || i"
             :src="questionImageUrl(img)" class="stem-img" mode="widthFix"
             :style="questionImageStyle(img)" />

      <view v-if="isObjective" class="options-grid">
        <view v-for="opt in choiceOptions" :key="opt.label"
              class="option-card" :class="{ selected: selectedOptions.includes(opt.label) }"
              @click="toggleOption(opt.label)">
          <view class="option-label">{{ opt.label }}</view>
          <view class="option-content" v-html="renderedOptions[opt.label] || opt.content"></view>
        </view>
      </view>
      <view v-else class="subjective-area">
        <textarea v-model="textAnswer" placeholder="请输入答案" class="text-input" />
      </view>

      <button class="submit-btn" @click="submit" :disabled="submitting">
        {{ submitting ? '提交中...' : '提交' }}
      </button>
    </view>

    <view class="feedback-panel">
      <view v-if="feedback" class="feedback-card" :class="feedbackType">
        <text class="feedback-title">
          {{ feedbackType === 'correct' ? '✓ 正确' : (feedbackType === 'pending' ? '⏱ 待批阅' : '✗ 不正确') }}
        </text>
        <text class="feedback-text">{{ feedback }}</text>
        <button v-if="!answerVisible" class="btn-answer" @click="showAnswer">查看答案与解析</button>
        <view v-if="answerVisible" class="answer-card">
          <text class="answer-label">参考答案</text>
          <view v-if="renderedCorrectAnswer" class="answer-content" v-html="renderedCorrectAnswer"></view>
          <text v-else class="answer-empty">暂无参考答案</text>
          <text class="answer-label">解析</text>
          <view v-if="renderedAnalysis" class="answer-content" v-html="renderedAnalysis"></view>
          <text v-else class="answer-empty">暂无解析</text>
        </view>
        <button v-if="!submitting" class="btn-next" @click="next">{{ hasNext ? '下一题' : '完成' }}</button>
      </view>
      <view v-else class="feedback-placeholder"><text>提交后显示结果</text></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { wrongbookApi } from '@/api/student.ts'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'
import { getQuestionTypeLabel, resolveQuestionType } from '@/utils/question-type'

interface Opt { label: string; content: string }
interface Q {
  id: string
  question_type: string
  stem?: string
  answer?: string
  options?: Opt[]
  images?: Array<{ id?: string; url?: string; file_path?: string; display_width?: number }>
}

const itemId = ref<string>('')
const startQuestionId = ref<string>('')
const questions = ref<Q[]>([])
const currentIndex = ref(0)
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const feedback = ref('')
const feedbackType = ref('')
const submitting = ref(false)
const answerVisible = ref(false)
const submittedCorrectAnswer = ref('')
const submittedAnalysis = ref('')
const renderedStem = ref('')
const renderedOptions = ref<Record<string, string>>({})
const renderedCorrectAnswer = ref('')
const renderedAnalysis = ref('')

const currentQuestion = computed(() => questions.value[currentIndex.value] || ({} as Q))

// Legacy variants can store A-D options in the stem. Parse them only for this
// page so the existing /variants/ response and its behavior remain unchanged.
const INLINE_OPTION_PATTERN = /(?:^|\n)\s*(?:\$?\s*\\(?:mathrm|text)\s*\{\s*([A-D])\s*\}\s*\$?|([A-D]))\s*[.．、)]\s*([^\n]+)/gi

function extractInlineOptions(stem: string): Opt[] {
  const options: Opt[] = []
  const pattern = new RegExp(INLINE_OPTION_PATTERN.source, 'gi')
  let match: RegExpExecArray | null
  while ((match = pattern.exec(String(stem || ''))) !== null) {
    options.push({ label: (match[1] || match[2]).toUpperCase(), content: match[3].trim() })
  }
  return options
}

function removeInlineOptions(stem: string): string {
  return String(stem || '')
    .replace(new RegExp(INLINE_OPTION_PATTERN.source, 'gi'), '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function normalizeQuestions(data: any[]): Q[] {
  return (Array.isArray(data) ? data : []).map((raw: any) => {
    const explicitOptions = Array.isArray(raw?.options) ? raw.options : []
    const options = explicitOptions.length
      ? explicitOptions.map((option: any) => ({
        label: String(option?.label || option?.option_label || '').toUpperCase(),
        content: String(option?.content || ''),
      }))
      : extractInlineOptions(raw?.stem || '')
    return { ...raw, options }
  })
}

function questionImageUrl(image: any): string {
  return getMediaUrl(image?.url || image?.file_path || '')
}

function questionImageStyle(image: any) {
  const savedWidth = Number(image?.display_width || 0)
  const width = savedWidth > 0 ? Math.max(80, Math.min(1200, Math.round(savedWidth))) : 420
  return { width: `${width}px`, maxWidth: '100%', height: 'auto' }
}

const effectiveQuestionType = computed(() => resolveQuestionType(
  currentQuestion.value.question_type,
  currentQuestion.value.stem,
  currentQuestion.value.options,
  currentQuestion.value.answer,
))

const choiceOptions = computed<Opt[]>(() => {
  if (currentQuestion.value.options?.length) return currentQuestion.value.options
  if (effectiveQuestionType.value === 'true_false') {
    return [{ label: '正确', content: '正确' }, { label: '错误', content: '错误' }]
  }
  return []
})

const isObjective = computed(() =>
  ['single_choice', 'multiple_choice', 'true_false'].includes(effectiveQuestionType.value))
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)

onLoad((options: any) => {
  itemId.value = String(options?.itemId || '')
  startQuestionId.value = String(options?.questionId || '')
})

onMounted(async () => {
  if (!itemId.value) { uni.showToast({ title: '缺少错题ID', icon: 'none' }); return }
  try {
    const res = await wrongbookApi.variants(itemId.value)
    questions.value = normalizeQuestions(res.data || [])
    const startIndex = questions.value.findIndex((question) => String(question.id) === startQuestionId.value)
    if (startIndex >= 0) currentIndex.value = startIndex
    await renderCurrentQuestion()
    if (!questions.value.length) uni.showToast({ title: '暂无同类题', icon: 'none' })
  } catch { uni.showToast({ title: '加载失败', icon: 'none' }) }
})

async function renderCurrentQuestion() {
  const q = currentQuestion.value
  if (!q) return
  const stem = extractInlineOptions(q.stem || '').length ? removeInlineOptions(q.stem || '') : (q.stem || '')
  renderedStem.value = await renderWithKatex(stem)
  renderedOptions.value = {}
  for (const opt of choiceOptions.value) {
    renderedOptions.value[opt.label] = await renderWithKatex(opt.content || '')
  }
}

function toggleOption(label: string) {
  if (effectiveQuestionType.value === 'single_choice' || effectiveQuestionType.value === 'true_false') {
    selectedOptions.value = selectedOptions.value.includes(label) ? [] : [label]
    return
  }
  const i = selectedOptions.value.indexOf(label)
  if (i >= 0) selectedOptions.value.splice(i, 1)
  else selectedOptions.value.push(label)
}

async function submit() {
  if (!currentQuestion.value.id) return
  if (isObjective.value && !selectedOptions.value.length) {
    uni.showToast({ title: '请选择答案', icon: 'none' })
    return
  }
  if (!isObjective.value && !textAnswer.value.trim()) {
    uni.showToast({ title: '请输入答案', icon: 'none' })
    return
  }

  submitting.value = true
  const answer_content = isObjective.value ? { selected_options: selectedOptions.value } : { text: textAnswer.value }
  try {
    const res = await wrongbookApi.variantSubmit(itemId.value, {
      question_id: currentQuestion.value.id, answer_content,
    })
    feedback.value = res.data?.feedback || '已提交'
    feedbackType.value = res.data?.is_pending ? 'pending' : (res.data?.is_correct ? 'correct' : 'incorrect')
    submittedCorrectAnswer.value = String(res.data?.correct_answer || '')
    submittedAnalysis.value = String(res.data?.analysis || '')
    answerVisible.value = false
    renderedCorrectAnswer.value = ''
    renderedAnalysis.value = ''
  } catch { uni.showToast({ title: '提交失败，请稍后重试', icon: 'none' }) }
  finally { submitting.value = false }
}

async function showAnswer() {
  answerVisible.value = true
  renderedCorrectAnswer.value = submittedCorrectAnswer.value ? await renderWithKatex(submittedCorrectAnswer.value) : ''
  renderedAnalysis.value = submittedAnalysis.value ? await renderWithKatex(submittedAnalysis.value) : ''
}

function next() {
  feedback.value = ''
  feedbackType.value = ''
  selectedOptions.value = []
  textAnswer.value = ''
  answerVisible.value = false
  submittedCorrectAnswer.value = ''
  submittedAnalysis.value = ''
  renderedCorrectAnswer.value = ''
  renderedAnalysis.value = ''
  if (hasNext.value) currentIndex.value++
  else uni.navigateBack()
}

watch(currentIndex, async () => {
  await renderCurrentQuestion()
})
</script>

<style scoped>
.answer-page { display:flex; height:100vh; min-height:0; overflow:hidden; background:#f0f2f5; }
.question-panel { flex:1; min-width:0; min-height:0; overflow-y:auto; box-sizing:border-box; padding:30rpx 40rpx; }
.question-header { display:flex; justify-content:space-between; margin-bottom:20rpx; }
.q-no { font-size:24rpx; color:#999; }
.q-type { font-size:28rpx; font-weight:bold; color:#333; }
.stem { font-size:28rpx; color:#333; line-height:1.6; margin-bottom:16rpx; }
.stem-img { width:100%; border-radius:8rpx; margin-bottom:16rpx; }
.options-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:16rpx; margin-bottom:30rpx; }
.option-card { display:flex; align-items:flex-start; gap:12rpx; border:2rpx solid #ddd; border-radius:12rpx; padding:24rpx; background:#fff; }
.option-card.selected { border-color:#409eff; background:#ecf5ff; }
.option-label { width:40rpx; height:40rpx; border-radius:50%; background:#eee; display:flex; align-items:center; justify-content:center; font-size:22rpx; font-weight:bold; flex-shrink:0; }
.option-card.selected .option-label { background:#409eff; color:#fff; }
.option-content { flex:1; min-width:0; font-size:26rpx; color:#333; }
.subjective-area { margin-bottom:30rpx; }
.text-input { width:100%; min-height:300rpx; border:1rpx solid #ddd; border-radius:12rpx; padding:20rpx; box-sizing:border-box; background:#fff; font-size:26rpx; }
.submit-btn { background:#409eff; color:#fff; font-size:28rpx; padding:20rpx 0; border-radius:8rpx; }
.submit-btn[disabled] { background:#ccc; }
.feedback-panel { width:340px; padding:30rpx 24rpx; background:#fff; border-left:1rpx solid #e8e8e8; display:flex; align-items:center; flex-shrink:0; box-sizing:border-box; overflow-y:auto; }
.feedback-card { padding:30rpx; border-radius:12rpx; width:100%; }
.feedback-card.correct { background:#e8f5e9; border:1rpx solid #67c23a; }
.feedback-card.correct .feedback-title { color:#188038; }
.feedback-card.incorrect { background:#ffebee; border:1rpx solid #f56c6c; }
.feedback-card.incorrect .feedback-title { color:#d93025; }
.feedback-card.pending { background:#eef6ff; }
.feedback-title { font-size:28rpx; font-weight:bold; display:block; margin-bottom:12rpx; }
.feedback-text { font-size:24rpx; color:#333; display:block; margin-bottom:20rpx; line-height:1.6; }
.btn-answer { background:#fff; color:#409eff; border:1rpx solid #409eff; font-size:24rpx; margin-bottom:16rpx; }
.answer-card { padding:20rpx; margin-bottom:20rpx; border-radius:8rpx; background:#fff; }
.answer-label { display:block; color:#666; font-size:24rpx; font-weight:bold; margin:10rpx 0; }
.answer-content { color:#333; font-size:24rpx; line-height:1.6; word-break:break-word; }
.answer-empty { display:block; color:#999; font-size:24rpx; margin-bottom:10rpx; }
.btn-next { background:#4caf50; color:#fff; font-size:24rpx; }
.feedback-placeholder { text-align:center; color:#ccc; font-size:26rpx; }
@media (max-width:768px) { .answer-page { flex-direction:column; height:auto; min-height:100vh; overflow:visible; } .question-panel { overflow:visible; min-height:auto; } .feedback-panel { width:100%; border-left:none; border-top:1rpx solid #e8e8e8; } .options-grid { grid-template-columns:1fr; } }
.katex { font-size:1.05em; }
.katex-display { margin:6px 0; overflow-x:auto; }
</style>
