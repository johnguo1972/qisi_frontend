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
        <view class="stem-content" v-html="renderedStem"></view>
        <!-- 题目图片 -->
        <view v-if="currentQuestion.images && currentQuestion.images.length > 0" class="stem-images">
          <image
            v-for="(img, idx) in currentQuestion.images"
            :key="idx"
            :src="questionImageUrl(img)"
            mode="widthFix"
            class="stem-image"
            :style="questionImageStyle(img)"
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
          <!-- #ifdef H5 -->
          <view class="option-content" v-html="renderOptionHtml(opt.content)"></view>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <text class="option-content">{{ opt.content }}</text>
          <!-- #endif -->
        </view>
      </view>

      <!-- 主观题：文本输入 + 拍照上传 -->
      <view v-else class="subjective-area">
        <view class="section-title">我的答案</view>
        <textarea v-model="textAnswer" :placeholder="textPlaceholder" class="text-input" />
        <text v-if="currentQuestion.question_type === 'fill_blank'" class="fill-hint">多个空位请用中文分号（；）分隔每个答案，例如：2；-3</text>

        <!-- 拍照上传 -->
        <!-- #ifdef MP-WEIXIN -->
        <PhotoUploadEnhanced
          :images="uploadedImages"
          :attempt-id="attemptId"
          :question-id="String(currentQuestion.id)"
          :level-id="levelId"
          @update:images="uploadedImages = $event"
          @attempt-created="attemptId = $event"
        />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
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
        <!-- #endif -->
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
        <button v-if="hasSubmitted" class="btn-related" @click="loadRelatedQuestions">同类题</button>
      </view>

      <!-- P1-06：逐题答题页的整份作业提交入口。整份提交由后端统一检查必答题。 -->
      <view v-if="missionId" class="whole-submit-section">
        <button
          class="btn-submit-mission"
          :disabled="missionSubmitting || missionSubmitted"
          @click="submitMission"
        >
          {{ missionSubmitting ? '提交整份作业中...' : (missionSubmitted ? '整份作业已提交' : '提交整份作业') }}
        </button>
        <text v-if="missingQuestionCount > 0" class="whole-submit-hint">
          还有 {{ missingQuestionCount }} 道题未提交，请先完成逐题提交
        </text>
      </view>

      <!-- 整份提交成功后展示本次作业的全部判分结果、答案和解析。 -->
      <view v-if="missionSubmitted && missionResults.length" class="mission-result-panel">
        <view class="mission-result-header">
          <text class="mission-result-title">整份作业结果</text>
          <text class="mission-result-count">共 {{ missionResults.length }} 题</text>
        </view>
        <view v-for="item in missionResults" :key="item.question_id" class="mission-result-item">
          <view class="mission-result-item-header">
            <text class="mission-result-no">第 {{ item.question_no || '—' }} 题</text>
            <text v-if="item.is_pending" class="mission-result-pending">待老师批阅</text>
            <text v-else :class="item.is_correct ? 'mission-result-correct' : 'mission-result-wrong'">
              {{ item.is_correct ? '回答正确' : '回答错误' }}
            </text>
          </view>
          <view v-if="item.answer" class="mission-result-section">
            <text class="mission-result-label">正确答案</text>
            <view class="mission-result-content" v-html="item.answer"></view>
          </view>
          <view v-if="item.analysis" class="mission-result-section">
            <text class="mission-result-label">解析</text>
            <view class="mission-result-content" v-html="item.analysis"></view>
          </view>
          <view v-if="item.solution" class="mission-result-section">
            <text class="mission-result-label">解答过程</text>
            <view class="mission-result-content" v-html="item.solution"></view>
          </view>
        </view>
      </view>

      <!-- 答案解析面板（提交后展开） -->
      <view v-if="showAnswer && !missionSubmitted" class="answer-panel">
        <view class="answer-panel-header">
          <text class="answer-panel-title">
            {{ isCorrect ? '解析' : '正确答案 & 解析' }}
          </text>
          <text class="answer-panel-close" @click="showAnswer = false">✕</text>
        </view>

        <!-- 正确答案 -->
        <view class="answer-section">
          <view class="answer-label">正确答案</view>
          <view class="answer-content" v-html="renderedAnswer"></view>
        </view>

        <!-- 解析 -->
        <view v-if="currentQuestion.analysis" class="answer-section">
          <view class="answer-label">详细解析</view>
          <view class="answer-content" v-html="renderedAnalysis"></view>
        </view>

        <!-- 解答 -->
        <view v-if="currentQuestion.solution" class="answer-section">
          <view class="answer-label">解答过程</view>
          <view class="answer-content" v-html="renderedSolution"></view>
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
          <text class="feedback-icon">{{ feedbackType === 'correct' ? '✅' : (feedbackType === 'pending' ? '⏳' : '❌') }}</text>
          <text class="feedback-title">{{ feedbackType === 'correct' ? '回答正确' : (feedbackType === 'pending' ? '已提交，待批阅' : '回答错误') }}</text>
        </view>
        <text class="feedback-text">{{ feedback }}</text>
      </view>
      <view v-else class="feedback-placeholder">
        <text>提交答案后显示反馈</text>
      </view>
    </view>
  </view>
  <view v-if="relatedVisible" class="related-modal" @click="relatedVisible = false">
    <view class="related-panel" @click.stop>
      <view class="answer-panel-header"><text class="answer-panel-title">可练习的同类题</text><text class="answer-panel-close" @click="relatedVisible = false">✕</text></view>
      <view v-for="item in relatedItems" :key="item.id" class="related-item"><text>{{ item.question_no || '题目' }}：{{ item.stem }}</text></view>
      <text v-if="!relatedItems.length" class="related-empty">暂无可练习的同类题</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { studentApi } from '@/api/student.ts'
import { chooseImage, uploadImage, checkCameraSupport, chooseAndUpload } from '@/utils/image-upload'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'
import { getQuestionTypeLabel } from '@/utils/question-type'
import PhotoUploadEnhanced from '@/components/PhotoUploadEnhanced.vue'

const levelId = ref<string>('')
const missionId = ref<string>('')
const questions = ref<any[]>([])
const currentIndex = ref(0)
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const feedback = ref('')
const feedbackType = ref('')
const suggestGuidance = ref(false)
const isCorrect = ref(false)
const hasSubmitted = ref(false)
const showAnswer = ref(false)
const modeAData = ref<any>(null)
const submitting = ref(false)
const missionSubmitting = ref(false)
const missionSubmitted = ref(false)
const missingQuestionCount = ref(0)
const missionResults = ref<any[]>([])
const renderedStem = ref('')
const renderedOptions = ref<Record<string, string>>({})
const renderedAnswer = ref('')
const renderedAnalysis = ref('')
const renderedSolution = ref('')
const relatedVisible = ref(false)
const relatedItems = ref<any[]>([])
const idempotencyKey = ref('')

// 每题状态缓存（切换题目时保存/恢复）
const answersMap = ref<Record<string, any>>({})

// 拍照上传相关
const uploadedImages = ref<Array<{ previewUrl: string; serverUrl: string }>>([])
const attemptId = ref<string>('')
const uploadingPhoto = ref(false)
const cameraSupported = ref(true)
// #ifdef H5
const camCheck = checkCameraSupport()
cameraSupported.value = camCheck.supported
// #endif

const currentQuestion = computed(() => questions.value[currentIndex.value] || {})

function draftStorageKey() {
  return missionId.value ? `student-mission-answers-${missionId.value}` : ''
}

function questionImageUrl(image: any): string {
  return getMediaUrl(image?.url || image?.file_path || '')
}

function questionImageStyle(image: any) {
  const savedWidth = Number(image?.display_width || 0)
  const width = savedWidth > 0 ? Math.max(80, Math.min(1200, Math.round(savedWidth))) : 420
  return { width: `${width}px`, maxWidth: '100%', height: 'auto' }
}

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
  return getQuestionTypeLabel(
    currentQuestion.value.question_type,
    currentQuestion.value.stem,
    currentQuestion.value.options,
  )
})

function isObjectiveQuestion(q: any): boolean {
  if (q.question_type === 'fill_blank') return false
  if (['single_choice', 'multiple_choice'].includes(q.question_type)) {
    // 容错：标记为多选题但没有选项，且题干含 ____，按填空题处理
    if (!q.options || q.options.length === 0) {
      if (q.stem && q.stem.includes('____')) return false
    }
    return true
  }
  return false
}

const isObjective = computed(() => isObjectiveQuestion(currentQuestion.value))

const textPlaceholder = computed(() => {
  if (currentQuestion.value.question_type === 'fill_blank') {
    return '请在此输入答案，多个空位请用中文分号（；）分隔'
  }
  return '请输入答案...'
})
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)
const hasPrev = computed(() => currentIndex.value > 0)
const canAddPhoto = computed(() => uploadedImages.value.length < 3 && !uploadingPhoto.value)

// 渲染后的答案、解析、解答（供答案解析面板使用）
// 在 renderCurrentQuestion 中异步渲染

async function renderCurrentQuestion() {
  const q = currentQuestion.value
  if (!q) return
  if (q.stem_html) {
    const hasLatex = /\$|\$\$|\\\(|\\\[/.test(q.stem_html)
    renderedStem.value = hasLatex ? await renderWithKatex(q.stem_html) : q.stem_html
  } else if (q.stem) {
    renderedStem.value = await renderWithKatex(q.stem)
  } else {
    renderedStem.value = '<span style="color:#999">暂无题干</span>'
  }
  renderedOptions.value = {}
  for (const opt of (q.options || [])) {
    if (opt.content) renderedOptions.value[opt.content] = await renderWithKatex(opt.content)
  }
  // 渲染答案、解析、解答中的 LaTeX 公式
  renderedAnswer.value = q.answer ? await renderWithKatex(q.answer) : ''
  renderedAnalysis.value = q.analysis ? await renderWithKatex(q.analysis) : ''
  renderedSolution.value = q.solution ? await renderWithKatex(q.solution) : ''
}

function renderOptionHtml(content: string): string {
  return renderedOptions.value[content] || content
}

onLoad((options: any) => {
  levelId.value = String(options?.levelId || '')
})

onMounted(async () => {
  if (!levelId.value) {
    uni.showToast({ title: '缺少关卡ID', icon: 'none' })
    return
  }

  try {
    const res = await studentApi.levelDetail(levelId.value)
    questions.value = res.data?.questions || []
    missionId.value = String(res.data?.mission_id || '')
    loadDraftAnswers()
    const missionStatus = String(res.data?.mission_progress_status || '')
    missionSubmitted.value = ['submitted', 'graded', 'passed'].includes(missionStatus)
    if (missionSubmitted.value) await loadMissionResults()
    await renderCurrentQuestion()
    restoreQuestionState(String(currentQuestion.value.id || ''))
  } catch (e) {
    console.error('加载题目失败:', e)
    uni.showToast({ title: '加载题目失败', icon: 'none' })
  }
})

// 保存当前题目的状态到缓存
function saveQuestionState() {
  const q = currentQuestion.value
  if (!q || !q.id) return
  answersMap.value[String(q.id)] = {
    selectedOptions: [...selectedOptions.value],
    textAnswer: textAnswer.value,
    uploadedImages: [...uploadedImages.value],
    attemptId: attemptId.value,
    hasSubmitted: hasSubmitted.value,
    showAnswer: showAnswer.value,
    feedback: feedback.value,
    feedbackType: feedbackType.value,
    isCorrect: isCorrect.value,
    modeAData: modeAData.value,
    suggestGuidance: suggestGuidance.value,
    idempotencyKey: idempotencyKey.value,
    questionType: q.question_type,
    levelId: currentQuestion.value.level_id || levelId.value,
  }
  const key = draftStorageKey()
  if (key) uni.setStorageSync(key, answersMap.value)
}

function loadDraftAnswers() {
  const key = draftStorageKey()
  if (!key) return
  const saved = uni.getStorageSync(key)
  if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
    answersMap.value = saved
  }
}

// 从缓存恢复指定题目的状态
function restoreQuestionState(questionId: string) {
  const saved = answersMap.value[String(questionId)]
  if (saved) {
    selectedOptions.value = saved.selectedOptions || []
    textAnswer.value = saved.textAnswer || ''
    uploadedImages.value = saved.uploadedImages || []
    attemptId.value = saved.attemptId || ''
    hasSubmitted.value = saved.hasSubmitted || false
    showAnswer.value = saved.showAnswer || false
    feedback.value = saved.feedback || ''
    feedbackType.value = saved.feedbackType || ''
    isCorrect.value = saved.isCorrect || false
    modeAData.value = saved.modeAData || null
    suggestGuidance.value = saved.suggestGuidance || false
    idempotencyKey.value = saved.idempotencyKey || ''
  } else {
    // 没做过：重置
    hasSubmitted.value = false
    showAnswer.value = false
    modeAData.value = null
    feedback.value = ''
    feedbackType.value = ''
    suggestGuidance.value = false
    selectedOptions.value = []
    textAnswer.value = ''
    uploadedImages.value = []
    attemptId.value = ''
    idempotencyKey.value = ''
  }
}

// 题目切换时保存当前题状态，恢复目标题状态
watch(currentIndex, async () => {
  await renderCurrentQuestion()
  restoreQuestionState(currentQuestion.value.id)
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
    // #ifdef MP-WEIXIN
    if (!attemptId.value) {
      const started: any = await studentApi.startAttempt({ question_id: currentQuestion.value.id, mission_id: missionId.value || undefined, level_id: levelId.value })
      if (started.code !== 0 || !started.data?.attempt_id) throw new Error(started.message || '无法创建作答记录')
      attemptId.value = started.data.attempt_id
    }
    const uploaded = await chooseAndUpload({ count: 1, sourceType: ['camera', 'album'], attemptId: attemptId.value })
    for (const url of uploaded) uploadedImages.value.push({ previewUrl: url, serverUrl: url })
    if (uploaded.length) uni.showToast({ title: '上传成功', icon: 'success' })
    return
    // #endif

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
  if (!idempotencyKey.value) {
    idempotencyKey.value = `${currentQuestion.value.id}-${Date.now()}-${Math.random().toString(36).slice(2)}`
  }
  const content = isObjective.value
    ? { selected_options: selectedOptions.value }
    : { text: textAnswer.value, images: uploadedImages.value.map(img => img.serverUrl) }

  try {
    let res: any
    // #ifdef MP-WEIXIN
    if (!attemptId.value) {
      const started: any = await studentApi.startAttempt({ question_id: currentQuestion.value.id, mission_id: missionId.value || undefined, level_id: levelId.value })
      if (started.code !== 0 || !started.data?.attempt_id) throw new Error(started.message || '无法创建作答记录')
      attemptId.value = started.data.attempt_id
    }
    res = await studentApi.submitDraftAttempt(attemptId.value, content)
    // #endif
    // #ifndef MP-WEIXIN
    res = await studentApi.submitAnswer({ question_id: currentQuestion.value.id, answer_content: content, mission_id: missionId.value || undefined, level_id: levelId.value, idempotency_key: idempotencyKey.value })
    // #endif
    isCorrect.value = res.data?.is_correct || false
    feedback.value = res.data?.feedback || ''
    feedbackType.value = res.data?.is_pending ? 'pending'
      : (res.data?.is_correct ? 'correct' : 'incorrect')
    suggestGuidance.value = res.data?.suggest_guidance || false
    hasSubmitted.value = true
    showAnswer.value = false

    if (res.data?.attempt_id) {
      attemptId.value = String(res.data.attempt_id)
    }

    // 加载 Mode A 答案
    try {
      const modeARes = await studentApi.getModeA(currentQuestion.value.id)
      modeAData.value = modeARes.data || null
    } catch (e) {
      console.warn('加载 AI 答案失败:', e)
    }
    // 提交成功后保存状态到缓存
    saveQuestionState()
  } catch (e) {
    console.error('提交失败:', e)
    uni.showToast({ title: '提交失败，请重试', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function answerContentForQuestion(question: any, state: any) {
  return isObjectiveQuestion(question)
    ? { selected_options: state?.selectedOptions || [] }
    : {
        text: state?.textAnswer || '',
        images: (state?.uploadedImages || []).map((image: any) => image.serverUrl),
      }
}

function buildMissionAnswers() {
  // 先保存当前题，避免用户填写后直接点击整份提交时遗漏当前输入。
  saveQuestionState()
  return Object.entries(answersMap.value)
    .map(([questionId, state]: [string, any]) => {
      const question = questions.value.find((item: any) => String(item.id) === questionId)
        || { question_type: state.questionType }
      const key = state.idempotencyKey || `mission-${missionId.value}-question-${questionId}`
      state.idempotencyKey = key
      return {
        question_id: questionId,
        level_id: state.levelId || levelId.value,
        answer_content: answerContentForQuestion(question, state),
        attempt_id: state.attemptId || undefined,
        idempotency_key: key,
        submitted: !!state.hasSubmitted,
      }
    })
    .filter(Boolean)
}

async function loadMissionResults() {
  if (!missionId.value) return
  try {
    const response: any = await studentApi.missionResults(missionId.value)
    if (Number(response?.code) === 0 && Array.isArray(response.data?.results)) {
      missionResults.value = response.data.results
      markMissionQuestionsSubmitted()
    }
  } catch (error) {
    console.warn('加载整份作业结果失败:', error)
  }
}

function markMissionQuestionsSubmitted() {
  for (const item of missionResults.value) {
    const questionId = String(item.question_id)
    answersMap.value[questionId] = {
      ...(answersMap.value[questionId] || {}),
      hasSubmitted: true,
    }
  }
  const currentState = answersMap.value[String(currentQuestion.value.id)]
  if (currentState) hasSubmitted.value = true
}

// ---------------------------------------------------------------------------
// P1-06：提交整份作业
// ---------------------------------------------------------------------------

async function submitMission() {
  if (!missionId.value || missionSubmitting.value || missionSubmitted.value) return

  missionSubmitting.value = true
  missingQuestionCount.value = 0
  try {
    const response: any = await studentApi.submitMission(missionId.value, {
      answers: buildMissionAnswers() as any,
    })
    if (Number(response?.code) === 0) {
      missionSubmitted.value = true
      // 整份结果已经包含全部题目的答案和解析，不再重复显示当前题的
      // 单题即时解析面板。
      showAnswer.value = false
      const key = draftStorageKey()
      if (key) uni.removeStorageSync(key)
      missionResults.value = Array.isArray(response.data?.results) ? response.data.results : []
      if (!missionResults.value.length) await loadMissionResults()
      markMissionQuestionsSubmitted()
      for (const item of missionResults.value) {
        const questionId = String(item.question_id)
        const state = answersMap.value[questionId] || {}
        answersMap.value[questionId] = { ...state, hasSubmitted: true }
      }
      const currentState = answersMap.value[String(currentQuestion.value.id)]
      if (currentState) {
        hasSubmitted.value = true
      }
      uni.$emit('student-mission-submitted', { missionId: missionId.value })
      uni.$emit('student-answer-completed', { levelId: levelId.value })
      uni.showToast({ title: '整份作业已提交', icon: 'success' })
      return
    }

    const missingIds = response?.data?.missing_question_ids
    missingQuestionCount.value = Array.isArray(missingIds) ? missingIds.length : 0
    uni.showToast({
      title: missingQuestionCount.value > 0
        ? `还有 ${missingQuestionCount.value} 道题未提交`
        : (response?.message || '整份作业提交失败'),
      icon: 'none',
    })
  } catch (error) {
    console.error('提交整份作业失败:', error)
    uni.showToast({ title: '提交整份作业失败，请重试', icon: 'none' })
  } finally {
    missionSubmitting.value = false
  }
}

// ---------------------------------------------------------------------------
// 查看答案
// ---------------------------------------------------------------------------

function showAnswerPanel() {
  showAnswer.value = true
}

async function loadRelatedQuestions() {
  try {
    const response: any = await studentApi.relatedQuestions(currentQuestion.value.id)
    relatedItems.value = response.data || []
    relatedVisible.value = true
  } catch (error) {
    uni.showToast({ title: '加载同类题失败', icon: 'none' })
  }
}

// ---------------------------------------------------------------------------
// 引导模式（B/C）
// ---------------------------------------------------------------------------

function startGuidance(mode: string) {
  uni.navigateTo({
    url: `/pages/student/guidance?questionId=${currentQuestion.value.id}&levelId=${levelId.value}&mode=${mode}`,
  })
}

async function prevQuestion() {
  if (hasPrev.value) {
    saveQuestionState()
    currentIndex.value--
  }
}

async function nextQuestion() {
  if (hasNext.value) {
    saveQuestionState()
    currentIndex.value++
  } else {
    saveQuestionState()
    // 返回关卡页前主动通知其刷新进度，同时通知首页更新任务完成度
    uni.$emit('student-answer-completed', { levelId: levelId.value })
    uni.$emit('student-layout-show')
    uni.navigateBack()
  }
}
</script>

<style scoped>
.answer-page {
  display: flex;
  height: 100vh;
  min-height: 0;
  background: #f0f2f5;
  overflow: hidden;
  box-sizing: border-box;
}

/* ====== 左侧题目区 ====== */
.question-panel {
  flex: 1;
  padding: 30rpx 40rpx;
  overflow-y: auto;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
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
.question-stem {
  font-size: 28rpx;
  color: #333;
  line-height: 1.8;
  margin-bottom: 20rpx;
  padding: 8rpx 0;
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
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
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
  margin-bottom: 0;
  flex-shrink: 0;
}
.option-card.selected .option-label {
  background: #409eff;
  color: #fff;
}
.option-content {
  flex: 1;
  min-width: 0;
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
  margin-bottom: 8rpx;
}

.fill-hint {
  display: block;
  font-size: 22rpx;
  color: #999;
  margin-bottom: 24rpx;
  line-height: 1.5;
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
.btn-related { background: #fff; color: #409eff; border: 1rpx solid #409eff; font-size: 22rpx; }
.btn-related::after { border: none; }
.related-modal { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.45); }
.related-panel { width: 80%; max-height: 70vh; overflow-y: auto; padding: 24rpx; border-radius: 12rpx; background: #fff; }
.related-item { padding: 18rpx 0; border-bottom: 1rpx solid #eee; color: #333; font-size: 24rpx; line-height: 1.5; }
.related-empty { display: block; padding: 30rpx; color: #999; text-align: center; font-size: 24rpx; }

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
  flex-shrink: 0;
  box-sizing: border-box;
  overflow-y: auto;
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
.feedback-card.pending {
  background: #eef6ff;
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
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }
  .question-panel {
    padding: 20rpx;
    overflow: visible;
    min-height: auto;
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

.whole-submit-section {
  width: 100%;
  padding: 0 20rpx 24rpx;
  box-sizing: border-box;
}
.btn-submit-mission {
  width: 100%;
  margin: 0;
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 26rpx;
  line-height: 1.4;
  padding: 16rpx 0;
}
.btn-submit-mission::after { border: none; }
.btn-submit-mission[disabled] {
  background: #a8d08d;
  color: #f5f5f5;
}
.whole-submit-hint {
  display: block;
  margin-top: 10rpx;
  color: #e6a23c;
  text-align: center;
  font-size: 22rpx;
}
.mission-result-panel {
  margin: 0 20rpx 24rpx;
  padding: 20rpx;
  background: #fff;
  border: 1rpx solid #e8e8e8;
  border-radius: 10rpx;
}
.mission-result-header,
.mission-result-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mission-result-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #303133;
}
.mission-result-count,
.mission-result-label {
  color: #909399;
  font-size: 22rpx;
}
.mission-result-item {
  padding: 18rpx 0;
  border-top: 1rpx solid #ebeef5;
}
.mission-result-item:first-of-type { margin-top: 16rpx; }
.mission-result-no { color: #303133; font-size: 26rpx; font-weight: bold; }
.mission-result-correct { color: #67c23a; font-size: 22rpx; }
.mission-result-wrong { color: #f56c6c; font-size: 22rpx; }
.mission-result-pending { color: #e6a23c; font-size: 22rpx; }
.mission-result-section { margin-top: 12rpx; }
.mission-result-label { display: block; margin-bottom: 6rpx; }
.mission-result-content { color: #606266; font-size: 24rpx; line-height: 1.6; }

/* #ifdef MP-WEIXIN */
.answer-page {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.answer-page .question-panel {
  width: 100%;
  padding: 20rpx;
  box-sizing: border-box;
}
.answer-page .question-header,
.answer-page .header-left,
.answer-page .header-right {
  min-width: 0;
}
.answer-page .question-header {
  align-items: flex-start;
  gap: 8rpx;
}
.answer-page .header-right {
  flex-shrink: 0;
  gap: 6rpx;
}
.answer-page .btn-guide-mode {
  min-width: 0;
  padding: 6rpx 8rpx;
  font-size: 20rpx;
  white-space: nowrap;
}
.answer-page .action-bar {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: stretch;
  gap: 12rpx;
  width: 100%;
  padding: 0 20rpx;
  box-sizing: border-box;
}
.answer-page .action-bar button {
  flex: 1 1 0 !important;
  min-width: 0;
  width: 0;
  margin: 0;
  padding: 14rpx 4rpx;
  font-size: 23rpx;
  line-height: 1.4;
  white-space: nowrap;
  box-sizing: border-box;
}
/* #endif */
</style>
