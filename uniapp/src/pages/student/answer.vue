<template>
  <view class="answer-page">
    <!-- 左侧题目区 -->
    <view class="question-panel">
      <!-- 顶部导航：题号 + 引导按钮 -->
      <view class="question-header">
        <view class="header-left">
          <text class="q-no">第 {{ currentIndex + 1 }}/{{ questions.length }} 题</text>
          <text class="q-type">{{ questionTypeLabel }}</text>
        </view>
        <view class="header-right">
          <button class="btn-guide-mode" @click="startGuidance('B')">
            <text>固定选项问题引导</text>
          </button>
          <button class="btn-guide-mode" @click="startGuidance('C')">
            <text>非固定选项问题引导</text>
          </button>
        </view>
      </view>

      <!-- 题干展示 -->
      <view class="stem-section" v-if="currentQuestion.stem_html || currentQuestion.stem">
        <view class="stem-content" v-html="stemRendered"></view>
        <!-- 题目图片 -->
        <view v-if="currentQuestion.images && currentQuestion.images.length > 0" class="stem-images">
          <image
            v-for="(img, idx) in currentQuestion.images"
            :key="idx"
            :src="img.url || img.file_path"
            mode="widthFix"
            class="stem-image"
          />
        </view>
      </view>
      <view v-else class="stem-placeholder">
        <text>暂无题干内容</text>
      </view>

      <!-- 客观题：选项 -->
      <view v-if="isObjective" class="options-section">
        <view class="section-title">选项</view>
        <view v-for="opt in currentQuestion.options" :key="opt.label"
              class="option-card" :class="{ selected: selectedOptions.includes(opt.label) }"
              @click="selectOption(opt.label)">
          <view class="option-label">{{ opt.label }}</view>
          <text class="option-content">{{ opt.content }}</text>
        </view>
      </view>

      <!-- 主观题：文本输入 + 拍照上传 -->
      <view v-else class="subjective-area">
        <view class="section-title">我的答案</view>
        <textarea v-model="textAnswer" placeholder="请输入答案..." class="text-input" />

        <!-- 拍照上传 -->
        <view class="photo-section">
          <view class="photo-header">
            <text class="photo-label">上传解题照片</text>
            <!-- #ifdef H5 -->
            <text v-if="!cameraSupported" class="photo-hint">请使用手机访问以使用拍照功能</text>
            <!-- #endif -->
          </view>

          <!-- 拍照按钮 + 缩略图 -->
          <view class="photo-grid">
            <view v-for="(img, idx) in uploadedImages" :key="idx" class="thumb-item">
              <image :src="img.previewUrl" mode="aspectFill" class="thumb-image" @click="previewImage(idx)" />
              <view class="thumb-delete" @click="removeImage(idx)">
                <text class="delete-icon">×</text>
              </view>
            </view>
            <view v-if="canAddPhoto" @click="handleTakePhoto" class="camera-btn">
              <text class="camera-icon">&#128247;</text>
            </view>
          </view>
        </view>
      </view>

      <!-- 操作按钮区：上一题 + 提交/查看答案 + 下一题 -->
      <view class="action-bar">
        <button class="btn-prev" @click="prevQuestion" :disabled="!hasPrev">
          ‹ 上一题
        </button>
        <button v-if="!hasSubmitted" class="btn-submit" @click="submitAnswer" :disabled="submitting">
          {{ submitting ? '提交中...' : '提交答案' }}
        </button>
        <button v-else-if="!showAnswer" class="btn-show-answer" @click="showAnswerPanel">
          {{ isCorrect ? '查看解析' : '查看答案' }}
        </button>
        <button class="btn-next" @click="nextQuestion">
          {{ hasNext ? '下一题 ›' : '完成' }}
        </button>
      </view>

      <!-- 答案解析面板（提交后展开） -->
      <view v-if="showAnswer" class="answer-panel">
        <view class="answer-panel-header">
          <text class="answer-panel-title">
            {{ isCorrect ? '解析' : '正确答案 & 解析' }}
          </text>
          <text class="answer-panel-close" @click="showAnswer = false">✕</text>
        </view>

        <!-- 正确答案 -->
        <view class="answer-section">
          <view class="answer-label">正确答案</view>
          <view class="answer-content" v-html="answerRendered"></view>
        </view>

        <!-- 解析 -->
        <view v-if="currentQuestion.analysis" class="answer-section">
          <view class="answer-label">详细解析</view>
          <view class="answer-content" v-html="analysisRendered"></view>
        </view>

        <!-- 解答 -->
        <view v-if="currentQuestion.solution" class="answer-section">
          <view class="answer-label">解答过程</view>
          <view class="answer-content" v-html="solutionRendered"></view>
        </view>

        <!-- AI 答案 A 模式（结构化步骤） -->
        <view v-if="modeAData && modeAData.steps && modeAData.steps.length > 0" class="answer-section">
          <view class="answer-label">AI 逐步讲解</view>
          <view class="ai-steps">
            <view v-for="(step, idx) in modeAData.steps" :key="idx" class="ai-step">
              <text class="ai-step-label">步骤{{ step.step_number }}：</text>
              <text class="ai-step-content">{{ step.content }}</text>
            </view>
          </view>
          <view v-if="modeAData.summary" class="ai-summary">
            <text class="ai-summary-label">总结：</text>
            <text class="ai-summary-content">{{ modeAData.summary }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 右侧反馈区 -->
    <view class="feedback-panel">
      <view v-if="feedback" class="feedback-card" :class="feedbackType">
        <view class="feedback-header">
          <text class="feedback-icon">{{ feedbackType === 'correct' ? '✅' : '' }}</text>
          <text class="feedback-title">{{ feedbackType === 'correct' ? '回答正确' : '回答错误' }}</text>
        </view>
        <text class="feedback-text">{{ feedback }}</text>
      </view>
      <view v-else class="feedback-placeholder">
        <text>提交答案后显示反馈</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { studentApi } from '@/api/student.ts'
import { chooseImage, uploadImage, checkCameraSupport } from '@/utils/image-upload'
import { renderWithKatex } from '@/utils/katex-renderer'

// 将题目图片列表转换为渲染所需的格式
function toImageMap(images: any[]): Map<number, { file_path: string }> {
  const map = new Map<number, { file_path: string }>()
  if (!images) return map
  images.forEach((img: any, idx: number) => {
    const id = img.id || (idx + 1)
    const path = img.url || img.file_path || ''
    if (path) map.set(id, { file_path: path })
  })
  return map
}

// 渲染题干（KaTeX + 图片占位符 {{image_N}}）
async function renderStem(q: any): Promise<string> {
  const images = q.images || []
  const imageMap = toImageMap(images)
  const source = q.stem_html || q.stem || ''
  const rendered = await renderWithKatex(source)
  // 替换 {{image_N}} 占位符
  return rendered.replace(/\{\{image_(\d+)\}\}/g, (match, idStr: string) => {
    const id = Number(idStr)
    const img = imageMap.get(id)
    if (!img) return match
    const src = img.file_path.startsWith('http') ? img.file_path : `/media/${img.file_path}`
    return `<img src="${src}" alt="插图${id}" style="max-width:100%;border-radius:4px;margin:8px 0;" />`
  })
}

async function renderAnswer(q: any): Promise<string> {
  const source = q.answer || ''
  return renderWithKatex(source)
}

async function renderAnalysis(q: any): Promise<string> {
  const source = q.analysis || ''
  return renderWithKatex(source)
}

async function renderSolution(q: any): Promise<string> {
  const source = q.solution || ''
  return renderWithKatex(source)
}

const levelId = ref(0)
const questions = ref<any[]>([])
const currentIndex = ref(0)
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const feedback = ref('')
const feedbackType = ref('')
const suggestGuidance = ref(false)
const submitting = ref(false)
const hasSubmitted = ref(false)
const showAnswer = ref(false)
const modeAData = ref<any>(null)
const isCorrect = ref(false)

// 拍照上传相关
const uploadedImages = ref<Array<{ previewUrl: string; serverUrl: string }>>([])
const uploadingPhoto = ref(false)
const cameraSupported = ref(true)
// #ifdef H5
const camCheck = checkCameraSupport()
cameraSupported.value = camCheck.supported
// #endif

const currentQuestion = computed(() => questions.value[currentIndex.value] || {})

const questionTypeLabel = computed(() => {
  const typeMap: Record<string, string> = {
    single_choice: '单选题',
    multiple_choice: '多选题',
    fill_blank: '填空题',
    solution: '解答题',
    short_answer: '简答题',
    essay: '论述题',
    true_false: '判断题',
    computation: '计算题',
    proof: '证明题',
  }
  return typeMap[currentQuestion.value.question_type] || currentQuestion.value.question_type || '题目'
})

const isObjective = computed(() =>
  ['single_choice', 'multiple_choice'].includes(currentQuestion.value.question_type)
)
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)
const hasPrev = computed(() => currentIndex.value > 0)
const canAddPhoto = computed(() => uploadedImages.value.length < 3 && !uploadingPhoto.value)

// 题干渲染（KaTeX + 图片占位符）
const stemRendered = ref('')
const answerRendered = ref('')
const analysisRendered = ref('')
const solutionRendered = ref('')

async function renderQuestionContent() {
  const q = currentQuestion.value
  if (!q) return

  stemRendered.value = await renderStem(q)
  answerRendered.value = await renderAnswer(q)
  analysisRendered.value = await renderAnalysis(q)
  solutionRendered.value = await renderSolution(q)
}

onMounted(async () => {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  levelId.value = parseInt(page.options.levelId || '0')

  if (!levelId.value) {
    uni.showToast({ title: '缺少关卡ID', icon: 'none' })
    return
  }

  try {
    const res = await studentApi.levelDetail(levelId.value)
    questions.value = res.data?.questions || []
    await renderQuestionContent()
  } catch (e) {
    console.error('加载题目失败:', e)
    uni.showToast({ title: '加载题目失败', icon: 'none' })
  }
})

// 题目切换时重新渲染内容
watch(currentIndex, async () => {
  // 重置状态
  hasSubmitted.value = false
  showAnswer.value = false
  modeAData.value = null
  feedback.value = ''
  feedbackType.value = ''
  selectedOptions.value = []
  textAnswer.value = ''
  uploadedImages.value = []

  await renderQuestionContent()
})

// ---------------------------------------------------------------------------
// 选项选择（单选/多选）
// ---------------------------------------------------------------------------

function selectOption(label: string) {
  if (isObjective.value && currentQuestion.value.question_type === 'single_choice') {
    // 单选题：只能选一个
    selectedOptions.value = [label]
  } else {
    // 多选题：可多选
    const idx = selectedOptions.value.indexOf(label)
    if (idx >= 0) selectedOptions.value.splice(idx, 1)
    else selectedOptions.value.push(label)
  }
}

// ---------------------------------------------------------------------------
// 拍照上传
// ---------------------------------------------------------------------------

async function handleTakePhoto() {
  // #ifdef H5
  if (!cameraSupported.value) {
    uni.showToast({ title: '请使用手机访问以使用拍照功能', icon: 'none' })
    return
  }
  // #endif

  try {
    const results = await chooseImage({ count: 1, sourceType: ['camera', 'album'] })
    if (!results || results.length === 0) return

    uploadingPhoto.value = true
    uni.showLoading({ title: '上传中...' })

    const img = results[0]
    const baseUrl = (process.env.VUE_APP_BASE_URL as string) || ''
    const uploadUrl = `${baseUrl}/api/v1/questions/upload-image/`

    const uploadResult = await uploadImage({
      filePath: img.path,
      uploadUrl,
      fieldName: 'image',
      file: img.file,
    } as any)

    if (uploadResult.statusCode === 200 && uploadResult.data?.success) {
      const serverUrl = uploadResult.data.url || uploadResult.data.image_url || img.path
      uploadedImages.value.push({ previewUrl: img.path, serverUrl })
      uni.showToast({ title: '上传成功', icon: 'success' })
    } else {
      uni.showToast({ title: '上传失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('拍照上传失败:', e)
    uni.showToast({ title: '上传失败: ' + (e.message || ''), icon: 'none' })
  } finally {
    uploadingPhoto.value = false
    uni.hideLoading()
  }
}

function removeImage(idx: number) {
  uni.showModal({
    title: '确认删除',
    content: '确定要删除这张图片吗？',
    success: (res) => {
      if (res.confirm) {
        uploadedImages.value.splice(idx, 1)
      }
    },
  })
}

function previewImage(idx: number) {
  const urls = uploadedImages.value.map((img) => img.previewUrl)
  uni.previewImage({ current: urls[idx], urls })
}

// ---------------------------------------------------------------------------
// 提交答案
// ---------------------------------------------------------------------------

async function submitAnswer() {
  submitting.value = true
  const content = isObjective.value
    ? { selected_options: selectedOptions.value }
    : { text: textAnswer.value, images: uploadedImages.value.map(img => img.serverUrl) }

  try {
    const res = await studentApi.submitAnswer({
      question_id: currentQuestion.value.id,
      answer_content: content,
      level_id: levelId.value,
    })
    isCorrect.value = res.data?.is_correct || false
    feedback.value = res.data?.feedback || ''
    feedbackType.value = isCorrect.value ? 'correct' : 'incorrect'
    suggestGuidance.value = res.data?.suggest_guidance || false
    hasSubmitted.value = true
    showAnswer.value = false

    // 加载 Mode A 答案
    try {
      const modeARes = await studentApi.getModeA(currentQuestion.value.id)
      modeAData.value = modeARes.data || null
    } catch (e) {
      console.warn('加载 AI 答案失败:', e)
    }
  } catch (e) {
    console.error('提交失败:', e)
    uni.showToast({ title: '提交失败，请重试', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------------------
// 查看答案
// ---------------------------------------------------------------------------

function showAnswerPanel() {
  showAnswer.value = true
}

// ---------------------------------------------------------------------------
// 引导模式（B/C）
// ---------------------------------------------------------------------------

function startGuidance(mode: string) {
  uni.navigateTo({
    url: `/pages/student/guidance?questionId=${currentQuestion.value.id}&levelId=${levelId.value}&mode=${mode}`,
  })
}

// ---------------------------------------------------------------------------
// 上一题
// ---------------------------------------------------------------------------

function prevQuestion() {
  if (hasPrev.value) {
    currentIndex.value--
  }
}

// ---------------------------------------------------------------------------
// 下一题
// ---------------------------------------------------------------------------

function nextQuestion() {
  if (hasNext.value) {
    currentIndex.value++
  } else {
    uni.navigateBack()
  }
}
</script>

<style scoped>
.answer-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}

/* ====== 左侧题目区 ====== */
.question-panel {
  flex: 1;
  padding: 30rpx 40rpx;
  overflow-y: auto;
}

.question-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.header-right {
  display: flex;
  gap: 12rpx;
}
.btn-guide-mode {
  padding: 6rpx 16rpx;
  background: #fff;
  color: #ff9800;
  border: 1rpx solid #ff9800;
  border-radius: 6rpx;
  font-size: 22rpx;
  height: auto;
  line-height: 1.4;
}
.btn-guide-mode:active {
  background: #fff3e0;
}
.q-no {
  font-size: 24rpx;
  color: #999;
}
.q-type {
  font-size: 24rpx;
  font-weight: bold;
  color: #409eff;
  background: #ecf5ff;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
}

/* 题干区域 */
.stem-section {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}
.stem-content {
  font-size: 28rpx;
  color: #333;
  line-height: 1.8;
  white-space: pre-wrap;
}
.stem-content :deep(img) {
  max-width: 100%;
  border-radius: 8rpx;
  margin: 8rpx 0;
}
.stem-images {
  margin-top: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.stem-image {
  width: 100%;
  border-radius: 8rpx;
}
.stem-placeholder {
  text-align: center;
  padding: 40rpx;
  color: #ccc;
  font-size: 26rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 24rpx;
}

/* 章节标题 */
.section-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 12rpx;
  display: block;
}

/* 选项 */
.options-section {
  margin-bottom: 24rpx;
}
.options-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
}
.option-card {
  border: 2rpx solid #ddd;
  border-radius: 12rpx;
  padding: 20rpx;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.2s, background 0.2s;
}
.option-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.option-label {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: #eee;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  font-weight: bold;
  margin-bottom: 12rpx;
}
.option-card.selected .option-label {
  background: #409eff;
  color: #fff;
}
.option-content {
  font-size: 26rpx;
  color: #333;
  line-height: 1.5;
}

/* 主观题区域 */
.subjective-area {
  margin-bottom: 24rpx;
}
.text-input {
  width: 100%;
  min-height: 300rpx;
  border: 1rpx solid #ddd;
  border-radius: 12rpx;
  padding: 20rpx;
  box-sizing: border-box;
  background: #fff;
  font-size: 26rpx;
  margin-bottom: 24rpx;
}

/* 拍照上传 */
.photo-section {
  margin-top: 16rpx;
}
.photo-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.photo-label {
  font-size: 24rpx;
  color: #666;
  font-weight: 500;
}
.photo-hint {
  font-size: 20rpx;
  color: #999;
}
.photo-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  align-items: center;
}
.thumb-item {
  position: relative;
  width: 160rpx;
  height: 160rpx;
  border-radius: 12rpx;
  overflow: hidden;
  border: 1rpx solid #eee;
}
.thumb-image {
  width: 100%;
  height: 100%;
}
.thumb-delete {
  position: absolute;
  top: 0;
  right: 0;
  width: 40rpx;
  height: 40rpx;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 0 0 0 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.delete-icon {
  color: #fff;
  font-size: 24rpx;
  line-height: 1;
}
.camera-btn {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4rpx 12rpx rgba(64, 158, 255, 0.3);
  transition: transform 0.15s;
}
.camera-btn:active {
  transform: scale(0.95);
}
.camera-icon {
  font-size: 48rpx;
  line-height: 1;
}

/* 操作按钮 */
.action-bar {
  display: flex;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.btn-prev, .btn-next {
  flex: 1;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  font-size: 26rpx;
  padding: 20rpx 0;
  border-radius: 8rpx;
}
.btn-prev[disabled], .btn-next[disabled] {
  opacity: 0.5;
}
.btn-submit {
  flex: 2;
  background: #409eff;
  color: #fff;
  font-size: 28rpx;
  padding: 20rpx 0;
  border-radius: 8rpx;
}
.btn-submit[disabled] {
  background: #ccc;
}
.btn-show-answer {
  flex: 2;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  font-size: 26rpx;
  padding: 20rpx 0;
  border-radius: 8rpx;
}

/* 答案解析面板 */
.answer-panel {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
  border: 1rpx solid #e8f5e9;
}
.answer-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.answer-panel-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #4caf50;
}
.answer-panel-close {
  font-size: 32rpx;
  color: #999;
  cursor: pointer;
}
.answer-section {
  margin-bottom: 20rpx;
}
.answer-section:last-child {
  margin-bottom: 0;
}
.answer-label {
  font-size: 24rpx;
  font-weight: bold;
  color: #666;
  margin-bottom: 8rpx;
  display: block;
}
.answer-content {
  font-size: 26rpx;
  color: #333;
  line-height: 1.8;
  white-space: pre-wrap;
}
.answer-content :deep(img) {
  max-width: 100%;
  border-radius: 8rpx;
  margin: 8rpx 0;
}

/* AI 逐步讲解 */
.ai-steps {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.ai-step {
  background: #f8f9fa;
  border-radius: 8rpx;
  padding: 12rpx 16rpx;
}
.ai-step-label {
  font-size: 24rpx;
  font-weight: bold;
  color: #409eff;
}
.ai-step-content {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
}
.ai-summary {
  margin-top: 12rpx;
  background: #fffbe6;
  border-radius: 8rpx;
  padding: 12rpx 16rpx;
}
.ai-summary-label {
  font-size: 24rpx;
  font-weight: bold;
  color: #fa8c16;
}
.ai-summary-content {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
}

/* ====== 右侧反馈区 ====== */
.feedback-panel {
  width: 340px;
  padding: 30rpx 24rpx;
  background: #fff;
  border-left: 1rpx solid #e8e8e8;
  display: flex;
  align-items: center;
}
.feedback-card {
  padding: 30rpx;
  border-radius: 12rpx;
  width: 100%;
}
.feedback-card.correct {
  background: #e8f5e9;
}
.feedback-card.incorrect {
  background: #fff3e0;
}
.feedback-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 16rpx;
}
.feedback-icon {
  font-size: 32rpx;
}
.feedback-title {
  font-size: 28rpx;
  font-weight: bold;
}
.feedback-text {
  font-size: 24rpx;
  color: #333;
  display: block;
  margin-bottom: 20rpx;
  line-height: 1.6;
}
.feedback-actions {
  display: flex;
  gap: 12rpx;
}
.btn-guidance {
  flex: 1;
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
}
.feedback-placeholder {
  text-align: center;
  color: #ccc;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .answer-page {
    flex-direction: column;
  }
  .question-panel {
    padding: 20rpx;
  }
  .feedback-panel {
    width: 100%;
    min-height: 200px;
    border-left: none;
    border-top: 1rpx solid #e8e8e8;
    padding: 20rpx;
  }
  .options-grid {
    grid-template-columns: 1fr;
  }
  .action-bar {
    flex-direction: column;
  }
}
</style>
