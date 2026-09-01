<template>
  <view class="variants-page">
    <!-- H5/App 使用页面内导航；小程序使用微信原生导航栏。 -->
    <!-- #ifndef MP-WEIXIN -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <text class="back-icon">&#8592;</text>
        <text class="back-text">返回</text>
      </view>
      <text class="nav-title">同类题练习</text>
      <view class="nav-right">
        <button
          class="btn-export"
          @click="exportPDF"
          :disabled="!variants.length"
        >
          导出PDF
        </button>
      </view>
    </view>
    <!-- #endif -->

    <!-- 加载中 -->
    <view v-if="loading" class="loading">
      <text class="loading-text">加载中...</text>
    </view>

    <!-- 空状态 -->
    <view v-else-if="!variants.length" class="empty">
      <text class="empty-icon">📭</text>
      <text class="empty-text">暂无同类题</text>
      <text class="empty-hint">系统会根据错题知识点推荐相似题目</text>
    </view>

    <!-- 直接作答区域：保留原来的 variant-practice 路由和入口函数，仅隐藏旧按钮。 -->
    <view v-else class="practice-shell">
      <view class="question-pane">
        <view class="variant-list">
          <view v-for="item in variants" :key="item.id" class="variant-card" :class="{ submitted: hasResult(item.id) }">
            <view class="card-header">
              <view class="card-tags">
                <view class="tag type-tag">{{ typeLabel(item.question_type, item.stem) }}</view>
                <view class="tag diff-tag" :class="diffClass(item.difficulty)">
                  {{ diffLabel(item.difficulty) }}
                </view>
              </view>
              <text class="card-no">{{ item.question_no || '#' + item.id }}</text>
            </view>

            <view class="card-body">
              <view class="stem-text" v-html="renderedStem(item)"></view>
              <image
                v-for="(image, imageIndex) in (item.images || [])"
                :key="image.id || imageIndex"
                :src="questionImageUrl(image)"
                class="stem-image"
                :style="questionImageStyle(image)"
                mode="widthFix"
              />

              <view v-if="isObjective(item)" class="inline-options">
                <view
                  v-for="option in choiceOptions(item)"
                  :key="option.label"
                  class="inline-option"
                  :class="{ selected: selectedOptions(item.id).includes(option.label) }"
                  @click="toggleOption(item, option.label)"
                >
                  <text class="inline-option-label">{{ option.label }}</text>
                  <view class="inline-option-content" v-html="renderedOption(item, option)"></view>
                </view>
              </view>
              <textarea
                v-else
                v-model="answers[item.id].text"
                class="inline-answer-input"
                :disabled="hasResult(item.id)"
                :placeholder="subjectivePlaceholder(item)"
              />
            </view>

            <view class="card-footer">
              <view class="knowledge-tags" v-if="item.knowledge_points?.length">
                <text v-for="kp in item.knowledge_points" :key="kp" class="kp-tag">{{ kp }}</text>
              </view>
              <!-- 保留旧入口代码，默认隐藏；需要恢复单题练习时只需移除 v-if。 -->
              <button v-if="false" class="btn-practice" @click="startPractice(item.id)">开始练习</button>
            </view>
            <view v-if="hasResult(item.id)" class="submitted-tip">本题已提交</view>
          </view>

          <view class="submit-area">
            <button class="submit-all-btn" :disabled="submitting || submitted" @click="submitAll">
              {{ submitting ? '提交中...' : (submitted ? '已完成提交' : '提交答案') }}
            </button>
            <text v-if="submitError" class="submit-error">{{ submitError }}</text>
          </view>

          <view class="bottom-actions">
            <button class="btn-back-full" @click="goBack">返回错题本</button>
          </view>
        </view>
      </view>

      <scroll-view v-if="hasResults" scroll-y class="result-pane">
        <view class="result-panel-title">答题结果与解析</view>
        <view v-for="item in variants" :key="item.id" class="result-card">
          <view class="result-card-header">
            <text>第{{ resultIndex(item.id) }}题</text>
            <text class="result-type" :class="resultClass(item.id)">{{ resultLabel(item.id) }}</text>
          </view>
          <view class="result-row">
            <text class="result-label">学生答案</text>
            <text class="result-value">{{ studentAnswerText(item) }}</text>
          </view>
          <view v-if="results[item.id]" class="result-row">
            <text class="result-label">正确答案</text>
            <view class="result-rich" v-html="renderedCorrectAnswer(item.id) || '暂无参考答案'"></view>
          </view>
          <view v-if="results[item.id]" class="result-row">
            <text class="result-label">解析</text>
            <view class="result-rich" v-html="renderedAnalysis(item.id) || '暂无解析'"></view>
          </view>
        </view>
      </scroll-view>
      <view v-else class="result-pane result-placeholder">
        <text>完成全部题目并提交后显示答案和解析</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { wrongbookApi } from '@/api/student.ts'
import { getMediaUrl } from '@/utils/media-url'
import { renderWithKatex } from '@/utils/katex-renderer'
import { resolveQuestionType } from '@/utils/question-type'

interface VariantOption {
  label: string
  content: string
}

interface VariantItem {
  id: string
  question_no?: string
  question_type: string
  difficulty: number
  stem?: string
  stem_html?: string
  answer?: string
  options?: VariantOption[]
  images?: Array<{ url?: string; file_path?: string; display_width?: number }>
  knowledge_points?: string[]
}

interface AnswerValue {
  selected_options: string[]
  text: string
}

interface VariantResult {
  is_correct: boolean
  is_pending: boolean
  score?: number
  feedback?: string
  correct_answer?: string
  analysis?: string
  student_answer: string
}

const wrongId = ref<string>('')
const variants = ref<VariantItem[]>([])
const loading = ref(true)
const answers = ref<Record<string, AnswerValue>>({})
const results = ref<Record<string, VariantResult>>({})
const renderedOptionsMap = ref<Record<string, Record<string, string>>>({})
const renderedCorrectAnswerMap = ref<Record<string, string>>({})
const renderedAnalysisMap = ref<Record<string, string>>({})
const submitting = ref(false)
const submitted = ref(false)
const submitError = ref('')
const hasResults = computed(() => Object.keys(results.value).length > 0)

function questionImageUrl(image: any): string {
  return getMediaUrl(image?.url || image?.file_path || '')
}

function questionImageStyle(image: any) {
  const savedWidth = Number(image?.display_width || 0)
  const width = savedWidth > 0 ? Math.max(80, Math.min(1200, Math.round(savedWidth))) : 420
  return { width: `${width}px`, maxWidth: '100%', height: 'auto' }
}

onLoad((options: any) => {
  wrongId.value = String(options?.id || '')
})

onMounted(async () => {
  if (!wrongId.value) {
    uni.showToast({ title: '缺少错题ID', icon: 'none' })
    loading.value = false
    return
  }

  await loadVariants()
})

async function loadVariants() {
  loading.value = true
  try {
    const res = await wrongbookApi.variants(wrongId.value)
    variants.value = normalizeVariants(res.data || [])
    initializeAnswers()
    await renderVariantStems()
  } catch (e: any) {
    console.error('获取同类题失败:', e)
    uni.showToast({ title: '加载失败，请重试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const renderedStemMap = ref<Record<string, string>>({})

const INLINE_OPTION_PATTERN = /(?:^|\n)\s*(?:\$?\s*\\(?:mathrm|text)\s*\{\s*([A-D])\s*\}\s*\$?|([A-D]))\s*[.．、)]\s*([^\n]+)/gi

function extractInlineOptions(stem: string): VariantOption[] {
  const options: VariantOption[] = []
  const pattern = new RegExp(INLINE_OPTION_PATTERN.source, 'gi')
  let match: RegExpExecArray | null
  while ((match = pattern.exec(String(stem || ''))) !== null) {
    options.push({
      label: (match[1] || match[2]).toUpperCase(),
      content: match[3].trim(),
    })
  }
  return options
}

function removeInlineOptions(stem: string): string {
  return String(stem || '')
    .replace(new RegExp(INLINE_OPTION_PATTERN.source, 'gi'), '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function normalizeVariants(data: any[]): VariantItem[] {
  return (Array.isArray(data) ? data : []).map((raw: any) => {
    const explicitOptions = Array.isArray(raw?.options) ? raw.options : []
    const options = explicitOptions.length
      ? explicitOptions.map((option: any) => ({
        label: String(option?.label || option?.option_label || '').toUpperCase(),
        content: String(option?.content || ''),
      })).filter((option: VariantOption) => option.label)
      : extractInlineOptions(raw?.stem || '')
    return { ...raw, id: String(raw.id), options }
  })
}

function initializeAnswers() {
  const initial: Record<string, AnswerValue> = {}
  for (const item of variants.value) {
    initial[item.id] = { selected_options: [], text: '' }
  }
  answers.value = initial
  results.value = {}
  renderedCorrectAnswerMap.value = {}
  renderedAnalysisMap.value = {}
  submitted.value = false
  submitError.value = ''
}

async function renderVariantStems() {
  const rendered: Record<string, string> = {}
  const renderedOptions: Record<string, Record<string, string>> = {}
  for (const item of variants.value) {
    const rawStem = item.stem || item.stem_html || ''
    const stem = extractInlineOptions(rawStem).length ? removeInlineOptions(rawStem) : (item.stem_html || rawStem)
    rendered[item.id] = await renderWithKatex(stem)
    renderedOptions[item.id] = {}
    for (const option of choiceOptions(item)) {
      renderedOptions[item.id][option.label] = await renderWithKatex(option.content || '')
    }
  }
  renderedStemMap.value = rendered
  renderedOptionsMap.value = renderedOptions
}

function renderedStem(item: VariantItem): string {
  return renderedStemMap.value[item.id] || item.stem_html || item.stem || ''
}

function renderedOption(item: VariantItem, option: VariantOption): string {
  return renderedOptionsMap.value[item.id]?.[option.label] || option.content || ''
}

function effectiveQuestionType(item: VariantItem): string {
  return resolveQuestionType(item.question_type, item.stem || '', choiceOptions(item), item.answer || '')
}

function choiceOptions(item: VariantItem): VariantOption[] {
  if (item.options?.length) return item.options
  if (effectiveQuestionTypeWithoutOptions(item) === 'true_false') {
    return [
      { label: '正确', content: '正确' },
      { label: '错误', content: '错误' },
    ]
  }
  return []
}

function effectiveQuestionTypeWithoutOptions(item: VariantItem): string {
  return resolveQuestionType(item.question_type, item.stem || '', [], item.answer || '')
}

function isObjective(item: VariantItem): boolean {
  return ['single_choice', 'multiple_choice', 'true_false'].includes(effectiveQuestionType(item))
}

function selectedOptions(questionId: string): string[] {
  return answers.value[questionId]?.selected_options || []
}

function toggleOption(item: VariantItem, label: string) {
  if (hasResult(item.id) || submitting.value) return
  const answer = answers.value[item.id]
  if (!answer) return
  const type = effectiveQuestionType(item)
  if (type === 'single_choice' || type === 'true_false') {
    answer.selected_options = answer.selected_options.includes(label) ? [] : [label]
    return
  }
  const index = answer.selected_options.indexOf(label)
  if (index >= 0) answer.selected_options.splice(index, 1)
  else answer.selected_options.push(label)
}

function subjectivePlaceholder(item: VariantItem): string {
  const type = effectiveQuestionType(item)
  return type === 'fill_blank' ? '请输入填空答案' : '请输入解答'
}

function answerContent(item: VariantItem): Record<string, any> {
  const answer = answers.value[item.id] || { selected_options: [], text: '' }
  return isObjective(item)
    ? { selected_options: [...answer.selected_options] }
    : { text: answer.text.trim() }
}

function hasAnswer(item: VariantItem): boolean {
  const answer = answers.value[item.id]
  if (!answer) return false
  return isObjective(item)
    ? answer.selected_options.length > 0
    : Boolean(answer.text.trim())
}

function hasResult(questionId: string): boolean {
  return Boolean(results.value[questionId])
}

function formatAnswer(answer: Record<string, any>): string {
  if (Array.isArray(answer?.selected_options)) {
    return answer.selected_options.join('、') || '未作答'
  }
  return String(answer?.text || '').trim() || '未作答'
}

function studentAnswerText(item: VariantItem): string {
  return results.value[item.id]?.student_answer || formatAnswer(answerContent(item))
}

function resultLabel(questionId: string): string {
  const result = results.value[questionId]
  if (!result) return '未提交'
  if (result.is_pending) return '待批阅'
  return result.is_correct ? '正确' : '错误'
}

function resultClass(questionId: string): string {
  const result = results.value[questionId]
  if (!result) return 'result-unsubmitted'
  if (result.is_pending) return 'result-pending'
  return result.is_correct ? 'result-correct' : 'result-incorrect'
}

function resultIndex(questionId: string): number {
  return variants.value.findIndex(item => item.id === questionId) + 1
}

function renderedCorrectAnswer(questionId: string): string {
  return renderedCorrectAnswerMap.value[questionId] || ''
}

function renderedAnalysis(questionId: string): string {
  return renderedAnalysisMap.value[questionId] || ''
}

async function renderResult(questionId: string, result: VariantResult) {
  renderedCorrectAnswerMap.value[questionId] = result.correct_answer
    ? await renderWithKatex(String(result.correct_answer))
    : ''
  renderedAnalysisMap.value[questionId] = result.analysis
    ? await renderWithKatex(String(result.analysis))
    : ''
}

async function submitAll() {
  if (submitting.value || submitted.value) return
  const missing = variants.value.filter(item => !hasAnswer(item) && !hasResult(item.id))
  if (missing.length) {
    uni.showToast({
      title: '请完成第' + missing.map(item => resultIndex(item.id)).join('、') + '题',
      icon: 'none',
    })
    return
  }

  submitting.value = true
  submitError.value = ''
  let failedCount = 0
  for (const item of variants.value) {
    if (hasResult(item.id)) continue
    try {
      const response: any = await wrongbookApi.variantSubmit(wrongId.value, {
        question_id: item.id,
        answer_content: answerContent(item),
      })
      if (response?.code !== undefined && response.code !== 0) {
        throw new Error(response.message || '提交失败')
      }
      const payload = response?.data || {}
      const result: VariantResult = {
        is_correct: Boolean(payload.is_correct),
        is_pending: Boolean(payload.is_pending),
        score: payload.score,
        feedback: payload.feedback,
        correct_answer: payload.correct_answer,
        analysis: payload.analysis,
        student_answer: formatAnswer(answerContent(item)),
      }
      results.value[item.id] = result
      await renderResult(item.id, result)
    } catch (error) {
      failedCount += 1
      console.error('提交同类题失败:', item.id, error)
    }
  }
  submitted.value = variants.value.every(item => hasResult(item.id))
  if (failedCount) {
    submitError.value = failedCount === variants.value.length
      ? '提交失败，请稍后重试'
      : '部分题目提交失败，请检查后重试'
  } else {
    uni.showToast({ title: '提交成功', icon: 'success' })
  }
  submitting.value = false
}

function startPractice(questionId?: string) {
  // 进入独立“同类题练习”页，传错题 id
  const startId = questionId ? `&questionId=${encodeURIComponent(String(questionId))}` : ''
  uni.navigateTo({ url: `/pages/student/variant-practice?itemId=${wrongId.value}${startId}` })
}

function exportPDF() {
  if (!variants.value.length) {
    uni.showToast({ title: '暂无可导出的题目', icon: 'none' })
    return
  }
  const ids = variants.value.map(v => v.id).join(',')
  uni.navigateTo({
    url: `/pages/student/export?type=variants&source_wrong_item_id=${wrongId.value}&ids=${ids}&title=同类题练习`,
  })
}

function goBack() {
  uni.navigateBack()
}

function typeLabel(type: string, stem = ''): string {
  const map: Record<string, string> = {
    single_choice: '单选',
    multiple_choice: '多选',
    fill_blank: '填空',
    short_answer: '简答',
    essay: '论述',
    true_false: '判断',
    computation: '计算',
    proof: '证明',
  }
  const normalized = String(type || '').trim().toLowerCase()
  const aliases: Record<string, string> = {
    calculation: '\u8ba1\u7b97\u9898',
    solution: '\u89e3\u7b54\u9898',
    experiment: '\u5b9e\u9a8c\u9898',
    reading_comprehension: '\u9605\u8bfb\u7406\u89e3',
    unknown: '\u672a\u8bc6\u522b',
  }
  if (normalized === 'unknown' || !normalized) {
    // 历史题库中部分题目题型为 unknown，根据题干内容给出可读的中文类型。
    if (/\u9009\u586b|\\underline|_{2,}/i.test(stem)) return '\u586b\u7a7a\u9898'
    if (/\\mathrm\{[A-D]\}|(?:^|\n)\s*[A-D][.、]/i.test(stem)) return '\u5355\u9009\u9898'
  }
  return map[normalized] || aliases[normalized] || (normalized ? '\u672a\u8bc6\u522b' : '\u9898\u76ee')
}

function diffClass(difficulty: number): string {
  const level = Number(difficulty)
  if (!Number.isFinite(level)) return 'diff-medium'
  if (level <= 2) return 'diff-easy'
  if (level <= 4) return 'diff-medium'
  return 'diff-hard'
}

function diffLabel(difficulty: number): string {
  const level = Number(difficulty)
  if (!Number.isFinite(level)) return '\u4e2d\u7b49'
  if (level <= 2) return '\u7b80\u5355'
  if (level <= 4) return '\u4e2d\u7b49'
  return '\u56f0\u96be'
}

function truncate(str: string, len: number): string {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}
</script>

<style scoped>
.variants-page {
  min-height: 100vh;
  background: #f0f2f5;
}

/* 导航栏 */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 40rpx;
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
  cursor: pointer;
}
.back-icon {
  font-size: 32rpx;
  color: #409eff;
}
.back-text {
  font-size: 26rpx;
  color: #409eff;
}
.nav-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
}
.btn-export {
  font-size: 24rpx;
  padding: 8rpx 24rpx;
  background: linear-gradient(135deg, #409eff, #3a8ee6);
  color: #fff;
  border: none;
  border-radius: 8rpx;
  line-height: 1.4;
  margin: 0;
  height: auto;
  min-width: 0;
}
.btn-export[disabled] {
  background: #ccc;
}
.btn-export:active {
  opacity: 0.85;
}

/* 加载中 */
.loading {
  display: flex;
  justify-content: center;
  padding: 200rpx 0;
}
.loading-text {
  font-size: 28rpx;
  color: #999;
}

/* 空状态 */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 0;
}
.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}
.empty-text {
  font-size: 28rpx;
  color: #666;
  margin-bottom: 12rpx;
}
.empty-hint {
  font-size: 24rpx;
  color: #999;
}

/* 题目列表 */
.variant-list {
  padding: 30rpx 40rpx;
}

.variant-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.2s;
}
.variant-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.card-tags {
  display: flex;
  gap: 12rpx;
}
.tag {
  font-size: 20rpx;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
}
.type-tag {
  background: #e3f2fd;
  color: #2196f3;
}
.diff-tag {
  background: #e8f5e9;
  color: #4caf50;
}
.diff-easy {
  background: #e8f5e9;
  color: #4caf50;
}
.diff-medium {
  background: #fff3e0;
  color: #ff9800;
}
.diff-hard {
  background: #ffebee;
  color: #f44336;
}
.card-no {
  font-size: 24rpx;
  color: #999;
}

.card-body {
  margin-bottom: 16rpx;
}
.stem-text {
  font-size: 26rpx;
  color: #333;
  line-height: 1.6;
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
}
.stem-text :deep(.katex) {
  font-size: 1em;
}
.stem-text :deep(.katex-display) {
  margin: 8rpx 0;
  overflow-x: auto;
}
.stem-image {
  width: 100%;
  max-height: 400rpx;
  margin-top: 16rpx;
  border-radius: 8rpx;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.knowledge-tags {
  display: flex;
  gap: 8rpx;
  flex-wrap: wrap;
  flex: 1;
  margin-right: 16rpx;
}
.kp-tag {
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  background: #f5f5f5;
  color: #666;
  border-radius: 4rpx;
}
.btn-practice {
  font-size: 24rpx;
  padding: 10rpx 32rpx;
  background: linear-gradient(135deg, #409eff, #3a8ee6);
  color: #fff;
  border: none;
  border-radius: 8rpx;
  line-height: 1.4;
  margin: 0;
  height: auto;
  min-width: 0;
}
.btn-practice:active {
  opacity: 0.85;
}

/* 底部操作 */
.bottom-actions {
  margin-top: 30rpx;
  padding-bottom: 40rpx;
}
.btn-back-full {
  width: 100%;
  font-size: 28rpx;
  padding: 20rpx 0;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  border-radius: 8rpx;
}
.btn-back-full:active {
  background: #ecf5ff;
}

.practice-shell {
  display: flex;
  height: calc(100vh - 86rpx);
  min-height: 700rpx;
  overflow: hidden;
}
.question-pane {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
.result-pane {
  width: 430px;
  flex: 0 0 430px;
  padding: 30rpx 24rpx;
  box-sizing: border-box;
  overflow-y: auto;
  background: #fff;
  border-left: 1rpx solid #e8e8e8;
}
.result-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b8bec8;
  font-size: 26rpx;
  text-align: center;
}
.inline-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
  margin-top: 22rpx;
}
.inline-option {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  padding: 18rpx;
  border: 2rpx solid #dcdfe6;
  border-radius: 10rpx;
  background: #fff;
}
.inline-option.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.inline-option-label {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38rpx;
  height: 38rpx;
  flex: 0 0 38rpx;
  border-radius: 50%;
  background: #f0f2f5;
  color: #606266;
  font-size: 22rpx;
  font-weight: 600;
}
.inline-option.selected .inline-option-label {
  background: #409eff;
  color: #fff;
}
.inline-option-content {
  min-width: 0;
  color: #303133;
  font-size: 25rpx;
  line-height: 1.5;
}
.inline-answer-input {
  width: 100%;
  min-height: 180rpx;
  margin-top: 22rpx;
  padding: 18rpx;
  box-sizing: border-box;
  border: 1rpx solid #dcdfe6;
  border-radius: 10rpx;
  background: #fff;
  color: #303133;
  font-size: 26rpx;
}
.inline-answer-input:disabled {
  background: #f5f7fa;
}
.variant-card.submitted {
  border: 2rpx solid #c6e2c6;
}
.submitted-tip {
  margin-top: 12rpx;
  color: #67c23a;
  font-size: 22rpx;
}
.submit-area {
  padding: 10rpx 0 20rpx;
}
.submit-all-btn {
  width: 100%;
  padding: 20rpx 0;
  border-radius: 8rpx;
  background: linear-gradient(135deg, #409eff, #3a8ee6);
  color: #fff;
  font-size: 28rpx;
}
.submit-all-btn[disabled] {
  background: #a0cfff;
}
.submit-error {
  display: block;
  margin-top: 12rpx;
  color: #f56c6c;
  font-size: 23rpx;
  text-align: center;
}
.result-panel-title {
  margin-bottom: 18rpx;
  color: #303133;
  font-size: 30rpx;
  font-weight: 600;
}
.result-card {
  margin-bottom: 18rpx;
  padding: 20rpx;
  border: 1rpx solid #ebeef5;
  border-radius: 10rpx;
  background: #fafcff;
}
.result-card-header {
  display: flex;
  justify-content: space-between;
  padding-bottom: 14rpx;
  border-bottom: 1rpx solid #ebeef5;
  color: #303133;
  font-size: 26rpx;
  font-weight: 600;
}
.result-type { font-weight: 600; }.result-correct { color: #67c23a; }.result-incorrect { color: #f56c6c; }.result-pending { color: #e6a23c; }.result-unsubmitted { color: #909399; }
.result-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 16rpx 0 0;
}
.result-label {
  flex: 0 0 120rpx;
  color: #909399;
  font-size: 24rpx;
}
.result-value, .result-rich {
  flex: 1;
  min-width: 0;
  color: #303133;
  font-size: 24rpx;
  line-height: 1.6;
  word-break: break-word;
}
.result-rich :deep(.katex-display) {
  overflow-x: auto;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .practice-shell {
    display: block;
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }
  .question-pane {
    overflow: visible;
  }
  .result-pane {
    width: auto;
    min-height: 360rpx;
    border-top: 1rpx solid #e8e8e8;
    border-left: 0;
  }
  .inline-options {
    grid-template-columns: 1fr;
  }
  .nav-bar {
    padding: 20rpx 24rpx;
  }
  .variant-list {
    padding: 24rpx;
  }
  .card-footer {
    flex-direction: column;
    gap: 16rpx;
    align-items: flex-start;
  }
  .btn-practice {
    width: 100%;
    text-align: center;
  }
  .knowledge-tags {
    margin-right: 0;
  }
}
</style>
