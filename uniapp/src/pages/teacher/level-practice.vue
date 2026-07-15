<template>
  <view class="practice-page">

    <view class="main">
      <!-- 顶部导航 -->
      <view class="top-bar">
        <view class="top-left">
          <text class="level-title">{{ levelName }}</text>
          <text class="level-type">{{ levelTypeText(levelType) }}</text>
        </view>
        <view class="top-right">
          <text class="question-counter">{{ currentIndex + 1 }} / {{ questions.length }}</text>
        </view>
      </view>

      <!-- 题目导航条 -->
      <view class="question-nav-bar">
        <view v-for="(q, idx) in questions" :key="q.id"
              :class="['nav-dot', { active: idx === currentIndex, answered: answeredIds.includes(q.id) }]"
              @click="goToQuestion(idx)">
          <text>{{ idx + 1 }}</text>
        </view>
      </view>

      <!-- 题目内容区 -->
      <view v-if="loading" class="loading">加载中...</view>
      <view v-else-if="questions.length === 0" class="empty">
        <text>该关卡暂无题目</text>
        <button class="back-btn-small" @click="goBack">返回</button>
      </view>
      <view v-else class="question-area">
        <!-- 题号与类型 -->
        <view class="question-header">
          <text class="question-no">第 {{ currentIndex + 1 }} 题</text>
          <text class="question-type">{{ currentQuestion?.question_type }}</text>
          <text class="question-diff">{{ '★'.repeat(Math.round(currentQuestion?.difficulty || 1)) }}</text>
          <!-- B/C模式引导按钮 -->
          <text class="guide-btn guide-b" @click="startGuidance('B')">B模式引导</text>
          <text class="guide-btn guide-c" @click="startGuidance('C')">C模式引导</text>
        </view>

        <!-- 题干（含 LaTeX 渲染） -->
        <view class="question-stem" v-if="currentQuestion">
          <!-- #ifdef H5 -->
          <view v-html="renderedStem"></view>
          <!-- #endif -->
          <!-- #ifndef H5 -->
          <rich-text v-if="currentQuestion.stem_html" :nodes="currentQuestion.stem_html"></rich-text>
          <text v-else>{{ currentQuestion.stem || '暂无题干' }}</text>
          <!-- #endif -->

          <!-- 题目图片 -->
          <view v-if="currentQuestion.images && currentQuestion.images.length > 0" class="question-images">
            <image v-for="(img, i) in currentQuestion.images" :key="i"
                   :src="img.url" mode="widthFix" class="question-image" />
          </view>
        </view>

        <!-- 选项区（仅客观题：单选/多选） -->
        <view v-if="isObjective && currentQuestion?.options?.length > 0" class="options-area">
          <view v-for="opt in currentQuestion.options" :key="opt.label"
                :class="['option-item', { selected: selectedOptions.includes(opt.label) }]"
                @click="toggleOption(opt.label)">
            <view class="option-label">{{ opt.label }}</view>
            <!-- #ifdef H5 -->
            <view class="option-content" v-html="renderOptionHtml(opt.content)"></view>
            <!-- #endif -->
            <!-- #ifndef H5 -->
            <text class="option-content">{{ opt.content }}</text>
            <!-- #endif -->
          </view>
        </view>

        <!-- 答题区 -->
        <view class="answer-area">
          <text class="answer-title">作答：</text>

          <!-- 主观题/填空题/问答题：文字输入 + 拍照 -->
          <template v-if="!isObjective">
            <textarea v-model="textAnswer"
                      placeholder="请输入你的答案..." class="text-input" />
            <!-- 拍照上传 -->
            <view class="photo-section">
              <text class="photo-label">拍照上传答案</text>
              <view class="photo-grid">
                <view v-for="(img, idx) in uploadedImages" :key="idx" class="thumb-item">
                  <image :src="img" mode="aspectFill" class="thumb-image" @click="previewImage(idx)" />
                  <view class="thumb-delete" @click="removeImage(idx)"><text>×</text></view>
                </view>
                <view v-if="uploadedImages.length < 3" @click="takePhoto" class="camera-btn">
                  <text class="camera-icon">📷</text>
                </view>
              </view>
            </view>
          </template>
          <!-- 客观题：仅文字输入（用于写解题思路） -->
          <template v-else>
            <textarea v-model="textAnswer"
                      placeholder="请写出你的解题思路..." class="text-input text-input-short" />
          </template>
        </view>

        <!-- 底部操作按钮 -->
        <view class="action-bar">
          <button class="nav-btn" :disabled="currentIndex === 0" @click="prevQuestion">上一题</button>
          <button class="submit-btn" @click="submitAnswer">提交答案</button>
          <button class="view-answer-btn" :class="{ enabled: hasAnsweredCurrent }" :disabled="!hasAnsweredCurrent" @click="showAnswer">查看答案</button>
          <button class="nav-btn" :disabled="currentIndex === questions.length - 1" @click="nextQuestion">下一题</button>
        </view>
      </view>

      <!-- 底部返回 -->
      <view class="footer-actions">
        <button class="back-btn" @click="goBack">返回任务详情</button>
      </view>
    </view>

    <!-- 答案反馈弹窗 -->
    <view v-if="showFeedback" class="feedback-modal" @click="closeFeedback">
      <view class="feedback-panel" @click.stop>
        <view class="feedback-header">
          <text class="feedback-icon">{{ isCorrect ? '✅' : '❌' }}</text>
          <text class="feedback-title">{{ isCorrect ? '回答正确' : '回答错误' }}</text>
        </view>
        <view class="feedback-body">
          <view class="feedback-row">
            <text class="feedback-label">正确答案：</text>
            <!-- #ifdef H5 -->
            <view class="feedback-value" v-html="renderedFeedbackAnswer"></view>
            <!-- #endif -->
            <!-- #ifndef H5 -->
            <text class="feedback-value">{{ currentQuestion?.answer || '暂无' }}</text>
            <!-- #endif -->
          </view>
          <view v-if="currentQuestion?.analysis" class="feedback-row">
            <text class="feedback-label">解析：</text>
            <!-- #ifdef H5 -->
            <view class="feedback-value" v-html="renderedFeedbackAnalysis"></view>
            <!-- #endif -->
            <!-- #ifndef H5 -->
            <text class="feedback-value">{{ currentQuestion.analysis }}</text>
            <!-- #endif -->
          </view>
        </view>
        <view class="feedback-footer">
          <button class="feedback-next-btn" @click="nextFromFeedback">
            {{ hasNext ? '下一题' : '完成练习' }}
          </button>
        </view>
      </view>
    </view>

    <!-- B/C模式引导弹窗 -->
    <view v-if="showGuidance" class="guidance-modal" @click="closeGuidance">
      <view class="guidance-panel" @click.stop>
        <view class="guidance-header">
          <view class="mode-badge" :class="guidanceMode === 'B' ? 'badge-b' : 'badge-c'">
            {{ guidanceMode === 'B' ? '引导模式 (选择)' : '自由对话' }}
          </view>
          <text class="guidance-close" @click="closeGuidance">✕</text>
        </view>

        <!-- 对话区 -->
        <scroll-view scroll-y class="guidance-chat">
          <view v-for="(msg, i) in guidanceMessages" :key="i"
                :class="['msg', msg.role === 'system' ? 'msg-system' : 'msg-user']">
            <text class="msg-avatar">{{ msg.role === 'system' ? '🤖' : '👤' }}</text>
            <view class="msg-bubble">
              <text>{{ msg.content }}</text>
            </view>
          </view>
        </scroll-view>

        <!-- 操作区 -->
        <view class="guidance-actions">
          <!-- B模式：选项按钮 -->
          <view v-if="guidanceMode === 'B' && guidanceOptions.length > 0 && !guidanceCompleted" class="options-list">
            <button v-for="opt in guidanceOptions" :key="opt"
                    @click="selectGuidanceOption(opt)" class="guide-option-btn">
              {{ opt }}
            </button>
          </view>

          <!-- C模式：文本输入 -->
          <view v-if="guidanceMode === 'C' && !guidanceCompleted" class="guidance-input-row">
            <input v-model="guidanceInput" placeholder="输入你的想法..." class="guidance-text-input" />
            <button @click="sendGuidanceReply" class="guidance-send-btn">发送</button>
          </view>

          <!-- 完成提示 -->
          <view v-if="guidanceCompleted" class="guidance-done">
            <text>🎉 引导完成！</text>
            <button @click="closeGuidance" class="guidance-done-btn">返回练习</button>
          </view>
        </view>
      </view>
    </view>

    <!-- A模式答案弹窗 -->
    <view v-if="showAnswerModal" class="answer-modal" @click="closeAnswerModal">
      <view class="answer-panel" @click.stop>
        <view class="answer-header">
          <text class="answer-title">📖 详细解答（A模式）</text>
          <text class="answer-close" @click="closeAnswerModal">✕</text>
        </view>
        <scroll-view scroll-y class="answer-body">
          <!-- AI解答步骤 -->
          <view v-if="answerAData?.steps && answerAData.steps.length > 0" class="answer-steps">
            <view v-for="(step, i) in answerAData.steps" :key="i" class="step-item">
              <view class="step-badge">步骤 {{ i + 1 }}</view>
              <text class="step-content">{{ step.content || step.description || step }}</text>
            </view>
          </view>
          <!-- AI解答内容 -->
          <view v-else-if="answerAData?.content" class="answer-content">
            <text>{{ answerAData.content }}</text>
          </view>
          <!-- 标准答案 -->
          <view class="answer-standard">
            <text class="answer-label">正确答案：</text>
            <text class="answer-value">{{ currentQuestion?.answer || '暂无' }}</text>
          </view>
          <!-- 解析 -->
          <view v-if="currentQuestion?.analysis" class="answer-analysis">
            <text class="answer-label">解析：</text>
            <text class="answer-value">{{ currentQuestion.analysis }}</text>
          </view>
        </scroll-view>
        <view class="answer-footer">
          <button class="answer-close-btn" @click="closeAnswerModal">关闭</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/index.ts'
import { chooseImage } from '@/utils/image-upload'
import { renderWithKatex } from '@/utils/katex-renderer'

const missionId = ref(0)
const levelId = ref(0)
const levelName = ref('')
const levelType = ref('')
const questions = ref<any[]>([])
const loading = ref(false)
const currentIndex = ref(0)

// 答题状态
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const uploadedImages = ref<string[]>([])
const answeredIds = ref<number[]>([])

// 保存每道题的作答状态（未提交也暂存）
const draftAnswers = ref<Record<number, {
  selectedOptions: string[]
  textAnswer: string
  uploadedImages: string[]
  // 提交后的反馈状态
  isCorrect: boolean | null
  showFeedback: boolean
}>>({})

// 反馈弹窗
const showFeedback = ref(false)
const isCorrect = ref(false)

// B/C引导弹窗
const showGuidance = ref(false)
const guidanceMode = ref<'B' | 'C'>('B')
const guidanceSessionId = ref('')
const guidanceMessages = ref<{ role: string; content: string }[]>([])
const guidanceOptions = ref<string[]>([])
const guidanceInput = ref('')
const guidanceCompleted = ref(false)

// 查看答案弹窗
const showAnswerModal = ref(false)
const answerAData = ref<any>(null)

// LaTeX 渲染
const renderedStem = ref('')
const renderedOptions = ref<Record<string, string>>({})
const renderedFeedbackAnswer = ref('')
const renderedFeedbackAnalysis = ref('')

const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
const isObjective = computed(() =>
  ['single_choice', 'multiple_choice'].includes(currentQuestion.value?.question_type)
)
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)
// 当前题目是否已提交答案（查看答案按钮可用状态）
const hasAnsweredCurrent = computed(() =>
  answeredIds.value.includes(currentQuestion.value?.id)
)

// 监听题目变化，渲染 LaTeX
async function renderCurrentQuestion() {
  const q = currentQuestion.value
  if (!q) return

  // 渲染题干
  if (q.stem_html) {
    // stem_html 可能已包含 HTML，但 LaTeX 公式可能未渲染
    // 检查是否包含 LaTeX 分隔符
    const hasLatex = /\$|\$\$|\\\(|\\\[/.test(q.stem_html)
    if (hasLatex) {
      renderedStem.value = await renderWithKatex(q.stem_html)
    } else {
      renderedStem.value = q.stem_html
    }
  } else if (q.stem) {
    renderedStem.value = await renderWithKatex(q.stem)
  } else {
    renderedStem.value = '<span style="color:#999">暂无题干</span>'
  }

  // 渲染选项
  renderedOptions.value = {}
  if (q.options && Array.isArray(q.options)) {
    for (const opt of q.options) {
      if (opt.content) {
        renderedOptions.value[opt.label] = await renderWithKatex(opt.content)
      }
    }
  }

  // 渲染反馈弹窗内容（正确答案 + 解析）
  if (q.answer) {
    renderedFeedbackAnswer.value = await renderWithKatex(q.answer)
  } else {
    renderedFeedbackAnswer.value = '<span style="color:#999">暂无</span>'
  }
  if (q.analysis) {
    renderedFeedbackAnalysis.value = await renderWithKatex(q.analysis)
  } else {
    renderedFeedbackAnalysis.value = ''
  }
}

onLoad((options: any) => {
  missionId.value = parseInt(options?.missionId || '0')
  levelId.value = parseInt(options?.levelId || '0')
})

onMounted(async () => {
  if (!missionId.value || !levelId.value) {
    uni.showToast({ title: '缺少参数', icon: 'none' })
    return
  }

  await loadLevelDetail()
})

async function loadLevelDetail() {
  loading.value = true
  try {
    const res = await missionApi.levelDetail(missionId.value, levelId.value)
    const data = res.data
    levelName.value = data?.level_name || ''
    levelType.value = data?.level_type || ''
    questions.value = data?.questions || []
    // 渲染当前题目
    await renderCurrentQuestion()
  } catch (e) {
    console.error('Failed to load level detail:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function levelTypeText(type: string): string {
  const map: Record<string, string> = {
    practice: '练习', review: '复习', retry: '重做', variant: '变式', check: '检测'
  }
  return map[type] || type
}

// 题目导航
async function goToQuestion(idx: number) {
  if (idx >= 0 && idx < questions.value.length) {
    saveDraftForCurrent()
    currentIndex.value = idx
    restoreDraftForCurrent()
    await renderCurrentQuestion()
  }
}

async function prevQuestion() {
  if (currentIndex.value > 0) {
    saveDraftForCurrent()
    currentIndex.value--
    restoreDraftForCurrent()
    await renderCurrentQuestion()
  }
}

async function nextQuestion() {
  showFeedback.value = false
  if (currentIndex.value < questions.value.length - 1) {
    saveDraftForCurrent()
    currentIndex.value++
    restoreDraftForCurrent()
    await renderCurrentQuestion()
  } else {
    saveDraftForCurrent()
    uni.showToast({ title: '练习完成！', icon: 'success' })
  }
}

async function nextFromFeedback() {
  saveDraftForCurrent()
  showFeedback.value = false
  if (currentIndex.value < questions.value.length - 1) {
    currentIndex.value++
    restoreDraftForCurrent()
    await renderCurrentQuestion()
  } else {
    uni.showToast({ title: '练习完成！', icon: 'success' })
  }
}

// 保存当前题目的草稿
function saveDraftForCurrent() {
  const q = currentQuestion.value
  if (!q) return
  draftAnswers.value[q.id] = {
    selectedOptions: [...selectedOptions.value],
    textAnswer: textAnswer.value,
    uploadedImages: [...uploadedImages.value],
    isCorrect: isCorrect.value,
    showFeedback: showFeedback.value,
  }
}

// 恢复当前题目的草稿
function restoreDraftForCurrent() {
  const q = currentQuestion.value
  if (!q) return
  const draft = draftAnswers.value[q.id]
  if (draft) {
    selectedOptions.value = [...draft.selectedOptions]
    textAnswer.value = draft.textAnswer
    uploadedImages.value = [...draft.uploadedImages]
    isCorrect.value = draft.isCorrect ?? false
    showFeedback.value = draft.showFeedback ?? false
  } else {
    selectedOptions.value = []
    textAnswer.value = ''
    uploadedImages.value = []
    isCorrect.value = false
    showFeedback.value = false
  }
}

function clearAnswer() {
  selectedOptions.value = []
  textAnswer.value = ''
  uploadedImages.value = []
}

// 选项操作
function toggleOption(label: string) {
  const idx = selectedOptions.value.indexOf(label)
  if (idx >= 0) selectedOptions.value.splice(idx, 1)
  else selectedOptions.value.push(label)
}

// 拍照
async function takePhoto() {
  try {
    const results = await chooseImage({ count: 1, sourceType: ['camera', 'album'] })
    if (results && results.length > 0) {
      uploadedImages.value.push(results[0].path)
    }
  } catch (e: any) {
    console.error('拍照失败:', e)
    uni.showToast({ title: '拍照失败', icon: 'none' })
  }
}

function removeImage(idx: number) {
  uploadedImages.value.splice(idx, 1)
}

function previewImage(idx: number) {
  uni.previewImage({ current: uploadedImages.value[idx], urls: uploadedImages.value })
}

// 提交答案
function submitAnswer() {
  const q = currentQuestion.value
  if (!q) return

  let userAnswer: string
  if (isObjective.value) {
    userAnswer = selectedOptions.value.sort().join('')
  } else {
    userAnswer = textAnswer.value || (uploadedImages.value.length > 0 ? '已上传图片' : '')
  }

  if (!userAnswer) {
    uni.showToast({ title: '请先作答', icon: 'none' })
    return
  }

  // 客观题自动判分
  if (isObjective.value) {
    const correctAnswer = (q.answer || '').replace(/\s/g, '').toUpperCase()
    isCorrect.value = userAnswer.toUpperCase() === correctAnswer
  } else {
    isCorrect.value = true
  }

  if (!answeredIds.value.includes(q.id)) {
    answeredIds.value.push(q.id)
  }

  showFeedback.value = true
}

// 获取渲染后的选项 HTML
function renderOptionHtml(content: string): string {
  return renderedOptions.value[content] || content
}

// ===== 查看答案（A模式） =====
function showAnswer() {
  if (!hasAnsweredCurrent.value) return

  const q = currentQuestion.value
  if (!q) return

  // 获取A模式答案
  answerAData.value = q.ai_answer_a || null
  showAnswerModal.value = true
}

function closeAnswerModal() {
  showAnswerModal.value = false
  answerAData.value = null
}

// ===== B/C 模式引导 =====
function startGuidance(mode: 'B' | 'C') {
  const q = currentQuestion.value
  if (!q) return

  guidanceMode.value = mode
  guidanceMessages.value = []
  guidanceOptions.value = []
  guidanceInput.value = ''
  guidanceCompleted.value = false
  showGuidance.value = true

  // 启动引导会话
  missionApi.startGuidance({ question_id: q.id, mode }).then(res => {
    guidanceSessionId.value = res.data?.session_id || ''
    if (mode === 'B') {
      if (res.data?.hint) {
        guidanceMessages.value.push({ role: 'system', content: res.data.hint })
      }
      if (res.data?.options) {
        guidanceOptions.value = res.data.options
      }
    } else {
      if (res.data?.question) {
        guidanceMessages.value.push({ role: 'system', content: res.data.question })
      }
    }
  }).catch(e => {
    console.error('启动引导失败:', e)
    uni.showToast({ title: '启动引导失败', icon: 'none' })
  })
}

function selectGuidanceOption(opt: string) {
  guidanceMessages.value.push({ role: 'user', content: opt })
  sendGuidanceInternal(opt)
}

function sendGuidanceReply() {
  if (!guidanceInput.value.trim()) return
  guidanceMessages.value.push({ role: 'user', content: guidanceInput.value })
  sendGuidanceInternal(guidanceInput.value)
  guidanceInput.value = ''
}

async function sendGuidanceInternal(answer: string) {
  try {
    const res = await missionApi.guidanceReply(guidanceSessionId.value, { user_answer: answer })
    const data = res.data

    if (data.mode === 'B') {
      if (data.next_hint) {
        guidanceMessages.value.push({ role: 'system', content: data.next_hint })
      }
    } else {
      // C模式：显示AI评价 + 下一个引导问题
      let replyContent = ''
      if (data.evaluation) {
        replyContent += `评价：${data.evaluation}\n\n`
      }
      if (data.next_question) {
        replyContent += data.next_question
      }
      if (replyContent) {
        guidanceMessages.value.push({ role: 'system', content: replyContent })
      }
    }

    if (data.is_completed) {
      guidanceCompleted.value = true
    }
  } catch (e) {
    console.error('引导回复失败:', e)
    uni.showToast({ title: '发送失败', icon: 'none' })
  }
}

function closeGuidance() {
  showGuidance.value = false
}

function closeFeedback() {
  showFeedback.value = false
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.practice-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 20rpx 30rpx;
  max-width: 900px;
}

/* 顶部导航 */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 20rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.top-left { display: flex; align-items: center; gap: 16rpx; }
.level-title { font-size: 28rpx; font-weight: bold; color: #333; }
.level-type { font-size: 20rpx; color: #409eff; background: #ecf5ff; padding: 4rpx 12rpx; border-radius: 4rpx; }
.question-counter { font-size: 24rpx; color: #999; }

/* 题目导航条 */
.question-nav-bar {
  display: flex;
  gap: 12rpx;
  padding: 16rpx 20rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
  flex-wrap: wrap;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.nav-dot {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}
.nav-dot.active { background: #409eff; color: #fff; font-weight: bold; }
.nav-dot.answered { background: #e8f5e9; color: #4caf50; }

/* 题目区 */
.loading, .empty {
  text-align: center;
  padding: 100rpx;
  color: #999;
  font-size: 26rpx;
}
.back-btn-small {
  display: inline-block;
  margin-top: 20rpx;
  padding: 12rpx 32rpx;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  border-radius: 8rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}
.question-area {
  background: #fff;
  border-radius: 12rpx;
  padding: 30rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 16rpx;
}
.question-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx solid #f0f0f0;
  flex-wrap: wrap;
}
.question-no { font-size: 26rpx; font-weight: bold; color: #409eff; }
.question-type { font-size: 20rpx; color: #666; background: #f5f5f5; padding: 4rpx 12rpx; border-radius: 4rpx; }
.question-diff { font-size: 20rpx; color: #ff9800; }
.guide-btn {
  font-size: 20rpx;
  padding: 6rpx 16rpx;
  border-radius: 6rpx;
  cursor: pointer;
  color: #fff;
}
.guide-b { background: #ff9800; }
.guide-c { background: #9c27b0; }
.guide-btn:hover { opacity: 0.85; }

/* 题干 */
.question-stem {
  font-size: 28rpx;
  color: #333;
  line-height: 1.8;
  margin-bottom: 24rpx;
}
.question-images {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-top: 16rpx;
}
.question-image { max-width: 100%; border-radius: 8rpx; }

/* 选项 */
.options-area {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.option-item {
  display: flex;
  gap: 16rpx;
  padding: 20rpx;
  border: 2rpx solid #e0e0e0;
  border-radius: 12rpx;
  cursor: pointer;
  transition: all 0.2s;
}
.option-item:hover { border-color: #409eff; }
.option-item.selected { border-color: #409eff; background: #ecf5ff; }
.option-label {
  width: 48rpx; height: 48rpx;
  border-radius: 50%;
  background: #eee;
  display: flex; align-items: center; justify-content: center;
  font-size: 24rpx; font-weight: bold;
  flex-shrink: 0;
}
.option-item.selected .option-label { background: #409eff; color: #fff; }
.option-content { font-size: 26rpx; color: #333; flex: 1; line-height: 1.6; }

/* 答题区 */
.answer-area {
  margin-top: 24rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid #f0f0f0;
}
.answer-title { font-size: 24rpx; font-weight: bold; color: #333; display: block; margin-bottom: 12rpx; }
.text-input {
  width: 100%;
  min-height: 200rpx;
  border: 2rpx solid #e0e0e0;
  border-radius: 12rpx;
  padding: 20rpx;
  box-sizing: border-box;
  background: #fff;
  font-size: 26rpx;
  margin-bottom: 16rpx;
}
.text-input:focus { border-color: #409eff; }
.text-input-short { min-height: 120rpx; }

/* 拍照区 */
.photo-section { margin-top: 16rpx; }
.photo-label { font-size: 22rpx; color: #666; display: block; margin-bottom: 12rpx; }
.photo-grid { display: flex; flex-wrap: wrap; gap: 16rpx; align-items: center; }
.thumb-item {
  position: relative;
  width: 160rpx; height: 160rpx;
  border-radius: 12rpx;
  overflow: hidden;
  border: 1rpx solid #eee;
}
.thumb-image { width: 100%; height: 100%; }
.thumb-delete {
  position: absolute; top: 0; right: 0;
  width: 40rpx; height: 40rpx;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 0 0 0 12rpx;
  display: flex; align-items: center; justify-content: center;
}
.thumb-delete text { color: #fff; font-size: 24rpx; }
.camera-btn {
  width: 160rpx; height: 160rpx;
  border-radius: 50%;
  background: #409eff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  box-shadow: 0 4rpx 12rpx rgba(64, 158, 255, 0.3);
}
.camera-btn:active { transform: scale(0.95); }
.camera-icon { font-size: 48rpx; }

/* 底部操作栏 */
.action-bar {
  display: flex;
  gap: 16rpx;
  margin-top: 30rpx;
}
.nav-btn {
  flex: 1;
  padding: 16rpx;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}
.nav-btn[disabled] { opacity: 0.4; }
.submit-btn {
  flex: 2;
  padding: 16rpx;
  background: #4caf50;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 28rpx;
  font-weight: bold;
  height: auto;
  line-height: normal;
}
.view-answer-btn {
  flex: 1;
  padding: 16rpx;
  background: #e0e0e0;
  color: #999;
  border: none;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}
.view-answer-btn.enabled {
  background: #2196f3;
  color: #fff;
  cursor: pointer;
}
.view-answer-btn.enabled:hover {
  background: #1976d2;
}

/* 底部返回 */
.footer-actions { text-align: center; margin-top: 20rpx; }
.back-btn {
  display: inline-block;
  padding: 12rpx 40rpx;
  background: #fff;
  color: #666;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}

/* 反馈弹窗 */
.feedback-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 999;
}
.feedback-panel {
  width: 80%; max-width: 600px;
  background: #fff; border-radius: 16rpx;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.15);
  overflow: hidden;
}
.feedback-header {
  display: flex; align-items: center; gap: 12rpx;
  padding: 24rpx; border-bottom: 1rpx solid #f0f0f0;
}
.feedback-icon { font-size: 36rpx; }
.feedback-title { font-size: 28rpx; font-weight: bold; }
.feedback-body { padding: 24rpx; max-height: 50vh; overflow-y: auto; }
.feedback-row { margin-bottom: 16rpx; }
.feedback-label { font-size: 24rpx; font-weight: bold; color: #666; display: block; margin-bottom: 8rpx; }
.feedback-value { font-size: 24rpx; color: #333; line-height: 1.6; display: block; }
.feedback-footer { padding: 16rpx 24rpx; border-top: 1rpx solid #f0f0f0; text-align: center; }
.feedback-next-btn {
  display: inline-block;
  padding: 14rpx 60rpx;
  background: #409eff;
  color: #fff;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}

/* B/C引导弹窗 */
.guidance-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.guidance-panel {
  width: 85%; max-width: 700px; height: 80vh;
  background: #fff; border-radius: 16rpx;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.15);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.guidance-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20rpx 24rpx; border-bottom: 1rpx solid #f0f0f0;
}
.mode-badge { font-size: 22rpx; padding: 6rpx 16rpx; border-radius: 4rpx; color: #fff; }
.badge-b { background: #ff9800; }
.badge-c { background: #9c27b0; }
.guidance-close { font-size: 32rpx; color: #999; cursor: pointer; }
.guidance-chat {
  flex: 1; padding: 20rpx;
}
.msg { display: flex; gap: 12rpx; margin-bottom: 16rpx; }
.msg-user { flex-direction: row-reverse; }
.msg-avatar { font-size: 32rpx; flex-shrink: 0; }
.msg-bubble {
  max-width: 75%;
  padding: 14rpx 18rpx;
  border-radius: 12rpx;
  font-size: 24rpx;
  line-height: 1.6;
}
.msg-system .msg-bubble { background: #f5f5f5; color: #333; }
.msg-user .msg-bubble { background: #409eff; color: #fff; }
.guidance-actions {
  padding: 16rpx 20rpx;
  border-top: 1rpx solid #f0f0f0;
}
.options-list { display: flex; flex-direction: column; gap: 10rpx; }
.guide-option-btn {
  background: #f8f8f8;
  border: 1rpx solid #ddd;
  text-align: left;
  padding: 14rpx 18rpx;
  font-size: 24rpx;
  border-radius: 8rpx;
  height: auto;
  line-height: normal;
}
.guide-option-btn:hover { background: #ecf5ff; border-color: #409eff; }
.guidance-input-row { display: flex; gap: 10rpx; }
.guidance-text-input {
  flex: 1;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 14rpx;
  font-size: 24rpx;
}
.guidance-send-btn {
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
  padding: 14rpx 24rpx;
  height: auto;
  line-height: normal;
}
.guidance-done {
  text-align: center;
  padding: 20rpx;
  font-size: 28rpx;
}
.guidance-done-btn {
  margin-top: 12rpx;
  background: #4caf50;
  color: #fff;
  font-size: 24rpx;
  padding: 12rpx 40rpx;
  border-radius: 8rpx;
  height: auto;
  line-height: normal;
}

/* 查看答案弹窗 */
.answer-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1001;
}
.answer-panel {
  width: 85%; max-width: 650px; height: 75vh;
  background: #fff; border-radius: 16rpx;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.15);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.answer-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 24rpx; border-bottom: 1rpx solid #f0f0f0;
  background: #f8f9fa;
}
.answer-title { font-size: 28rpx; font-weight: bold; color: #333; }
.answer-close { font-size: 32rpx; color: #999; cursor: pointer; }
.answer-body {
  flex: 1; padding: 24rpx; overflow-y: auto;
}
.answer-steps { margin-bottom: 20rpx; }
.step-item { margin-bottom: 16rpx; }
.step-badge {
  display: inline-block;
  font-size: 22rpx;
  font-weight: bold;
  color: #fff;
  background: #409eff;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
  margin-bottom: 8rpx;
}
.step-content {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
  display: block;
  padding-left: 12rpx;
}
.answer-content {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
  margin-bottom: 20rpx;
}
.answer-standard, .answer-analysis {
  padding: 16rpx;
  border-radius: 8rpx;
  margin-bottom: 12rpx;
}
.answer-standard { background: #e8f5e9; }
.answer-analysis { background: #fff3e0; }
.answer-label {
  font-size: 22rpx;
  font-weight: bold;
  display: block;
  margin-bottom: 8rpx;
}
.answer-standard .answer-label { color: #4caf50; }
.answer-analysis .answer-label { color: #ff9800; }
.answer-value {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
  display: block;
}
.answer-footer {
  padding: 16rpx 24rpx;
  border-top: 1rpx solid #f0f0f0;
  text-align: center;
}
.answer-close-btn {
  display: inline-block;
  padding: 12rpx 48rpx;
  background: #fff;
  color: #666;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main { margin-left: 60px; padding: 16rpx; }
}
</style>
