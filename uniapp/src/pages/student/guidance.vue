<template>
  <view class="guidance-page">
    <!-- 全屏加载（初始加载 + 切换题目时） -->
    <view v-if="loading || switching" class="fullscreen-loading">
      <view class="loading-spinner" />
      <text class="loading-text">{{ switching ? '正在加载下一题...' : '正在加载引导...' }}</text>
    </view>

    <!-- 主内容 -->
    <view v-if="!loading" class="guidance-main">

      <!-- 顶部导航栏 -->
      <view class="top-bar">
        <view class="top-bar-left">
          <text class="back-btn" @click="goBack">← 返回做题</text>
          <text class="q-position" v-if="currentIndex >= 0 && questions.length > 0">
            第 {{ currentIndex + 1 }}/{{ questions.length }} 题
          </text>
          <text class="q-type-tag">{{ questionTypeLabel }}</text>
        </view>
        <view class="top-bar-right">
          <view class="mode-badge" :class="mode === 'B' ? 'badge-b' : 'badge-c'">
            {{ mode === 'B' ? '固定选项引导' : '自由对话引导' }}
          </view>
          <text class="step-indicator" v-if="mode === 'B'">
            第 {{ stepIndex + 1 }}/{{ totalSteps }} 步
          </text>
        </view>
      </view>

      <!-- 原题题干区（可折叠，默认收起） -->
      <view class="stem-section" v-if="currentQuestion.stem || currentQuestion.stem_html">
        <view class="stem-header" @click="showStem = !showStem">
          <text class="stem-title">📖 查看原题</text>
          <text class="stem-toggle">{{ showStem ? '收起 ▲' : '展开 ▼' }}</text>
        </view>
        <view v-if="showStem" class="stem-body">
          <view class="stem-content" v-html="currentQuestion.stem_html || currentQuestion.stem" />
          <!-- 原题选项（只读展示） -->
          <view v-if="currentQuestion.options && currentQuestion.options.length > 0" class="stem-options">
            <view v-for="opt in currentQuestion.options" :key="opt.label" class="stem-option">
              <text class="stem-opt-label">{{ opt.label }}.</text>
              <text class="stem-opt-content">{{ opt.content }}</text>
            </view>
          </view>
          <!-- 原题图片 -->
          <view v-if="currentQuestion.images && currentQuestion.images.length > 0" class="stem-images">
            <image v-for="(img, idx) in currentQuestion.images" :key="idx"
                   :src="img.url || img.file_path" mode="widthFix" class="stem-image" />
          </view>
        </view>
      </view>

      <!-- 引导对话区（可滚动） -->
      <scroll-view scroll-y class="chat-area" :scroll-top="scrollTop">
        <view v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <view class="msg-avatar">{{ msg.role === 'system' ? '🤖' : '👤' }}</view>
          <view class="msg-bubble" :class="msg.type || ''">
            <text>{{ msg.content }}</text>
          </view>
        </view>
        <!-- 思考中指示器（C 模式请求时） -->
        <view v-if="showThinking" class="msg system">
          <view class="msg-avatar">🤖</view>
          <view class="msg-bubble thinking-bubble">
            <text class="thinking-text">思考中<text class="thinking-dots"><text>.</text><text>.</text><text>.</text></text></text>
          </view>
        </view>
      </scroll-view>

      <!-- 操作区（固定在底部） -->
      <view class="action-panel">
        <!-- B 模式：引导选项按钮 -->
        <view v-if="mode === 'B' && !isCompleted && options.length > 0" class="options-section">
          <text class="section-title">选择你的答案</text>
          <button v-for="opt in options" :key="opt"
                  @click="selectOption(opt)"
                  :disabled="submitting"
                  :class="['option-btn', { selected: selectedOption === opt }]">
            <text v-if="submitting && selectedOption === opt" class="btn-loading">⏳</text>
            {{ opt }}
          </button>
        </view>

        <!-- C 模式：文本输入 -->
        <view v-if="mode === 'C' && !isCompleted" class="input-section">
          <text class="section-title">输入你的想法</text>
          <view class="input-row">
            <input v-model="inputText" :placeholder="inputPlaceholder" class="text-input" />
            <button @click="sendReply" :disabled="submitting || !inputText.trim()" class="send-btn">
              <text v-if="submitting">发送中...</text>
              <text v-else>发送</text>
            </button>
          </view>
        </view>

        <!-- 引导中：底部导航 -->
        <view v-if="!isCompleted && questions.length > 1" class="bottom-nav">
          <button v-if="hasPrevQuestion" @click="prevQuestion" :disabled="switching" class="nav-btn">← 上一题</button>
          <button v-if="hasNextQuestion" @click="nextQuestion" :disabled="switching" class="nav-btn">下一题 →</button>
        </view>

        <!-- ======== 引导完成 ======== -->
        <view v-if="isCompleted">

          <!-- 步骤 1：引导完成 + 选择原题答案 -->
          <view v-if="!showAnswerSelect && !submitResult">
            <view class="complete-icon">🎉</view>
            <text class="complete-title">引导完成！</text>
            <view v-if="summary" class="complete-summary">
              <text class="summary-label">📝 总结：</text>
              <text class="summary-text">{{ summary }}</text>
            </view>
            <view v-if="finalAnswer" class="complete-final">
              <text class="final-label">🎯 最终答案：</text>
              <text class="final-text">{{ finalAnswer }}</text>
            </view>
            <view class="complete-actions">
              <button v-if="hasPrevQuestion" @click="prevQuestion" class="action-btn prev-btn">← 上一题</button>
              <button @click="showAnswerSelect = true" class="action-btn submit-btn">选择答案并提交</button>
              <button @click="goBack" class="action-btn back-btn">返回做题</button>
              <button v-if="hasNextQuestion" @click="nextQuestion" class="action-btn next-btn">下一题 →</button>
            </view>
          </view>

          <!-- 步骤 2：选择原题答案 -->
          <view v-if="showAnswerSelect && !submitResult" class="answer-select-section">
            <text class="select-title">请选择本题的答案</text>
            <!-- 原题选项（可交互） -->
            <view v-if="currentQuestion.options && currentQuestion.options.length > 0" class="select-options">
              <button v-for="opt in currentQuestion.options" :key="opt.label"
                      @click="selectedOriginalOption = opt.label"
                      :class="['select-option-btn', { selected: selectedOriginalOption === opt.label }]">
                <text class="select-opt-label">{{ opt.label }}.</text>
                <text class="select-opt-content">{{ opt.content }}</text>
              </button>
            </view>
            <!-- 主观题：文本输入 -->
            <view v-else class="select-text-area">
              <textarea v-model="originalTextAnswer" placeholder="请输入你的答案..." class="select-text-input" />
            </view>
            <view class="complete-actions">
              <button @click="showAnswerSelect = false" class="action-btn back-btn">返回</button>
              <button @click="submitAnswer" :disabled="submittingAnswer || !canSubmitAnswer" class="action-btn submit-btn">
                {{ submittingAnswer ? '提交中...' : '确认提交' }}
              </button>
            </view>
          </view>

          <!-- 步骤 3：提交结果 -->
          <view v-if="submitResult" class="submit-result-section">
            <view :class="['result-icon', submitResult.is_correct ? 'correct' : 'incorrect']">
              {{ submitResult.is_correct ? '✅' : '❌' }}
            </view>
            <text :class="['result-title', submitResult.is_correct ? 'correct' : 'incorrect']">
              {{ submitResult.is_correct ? '回答正确！' : '回答错误' }}
            </text>
            <text class="result-score">得分：{{ submitResult.score }} 分</text>
            <text v-if="submitResult.feedback" class="result-feedback">{{ submitResult.feedback }}</text>
            <view v-if="!submitResult.is_correct && originalAnswer" class="result-answer">
              <text class="result-label">正确答案：</text>
              <text class="result-value">{{ originalAnswer }}</text>
            </view>
            <view v-if="!submitResult.is_correct && originalAnalysis" class="result-analysis">
              <text class="result-label">解析：</text>
              <text class="result-value">{{ originalAnalysis }}</text>
            </view>
            <view class="complete-actions">
              <button v-if="hasPrevQuestion" @click="prevQuestion" class="action-btn prev-btn">← 上一题</button>
              <button v-if="hasNextQuestion" @click="nextQuestion" class="action-btn next-btn">下一题 →</button>
              <button @click="goBack" class="action-btn back-btn">返回做题</button>
            </view>
          </view>

        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { studentApi } from '@/api/student.ts'

// 页面核心状态
const questionId = ref(0)
const levelId = ref(0)
const questions = ref<any[]>([])
const currentIndex = ref(0)
const showStem = ref(true)

// 引导会话状态
const sessionId = ref(0)
const mode = ref('')
const stepIndex = ref(0)
const totalSteps = ref(3)
const isCompleted = ref(false)
const isFallback = ref(false)

// 对话消息列表
const messages = ref<{ role: string; content: string; type?: string }[]>([])

// 思考中指示器（C 模式请求时显示在对话区）
const showThinking = ref(false)

// B 模式选项
const options = ref<string[]>([])
const selectedOption = ref('')
const isCorrect = ref<boolean | null>(null)
const correctAnswer = ref('')
const analysis = ref('')

// C 模式输入
const inputText = ref('')
const inputPlaceholder = ref('输入你的想法...')

// AI 总结
const summary = ref('')
const finalAnswer = ref('')

// 加载状态
const loading = ref(false)
const submitting = ref(false)
const switching = ref(false)
const scrollTop = ref(0)            // 用于 scroll-view 自动滚动

// 原题信息
const currentQuestion = ref<any>({})

// 提交答案结果
const submitResult = ref<{ is_correct: boolean; score: number; feedback: string } | null>(null)
const submittingAnswer = ref(false)
const originalAnswer = ref('')      // 原题正确答案（从 question_info 获取）
const originalAnalysis = ref('')    // 原题解析（从 question_info 获取）
const showAnswerSelect = ref(false) // 是否显示选择答案界面
const selectedOriginalOption = ref('')  // 用户从原题选项中选择的答案
const originalTextAnswer = ref('')  // 主观题用户输入的答案

// 计算属性
const canSubmitAnswer = computed(() => {
  if (currentQuestion.value.options && currentQuestion.value.options.length > 0) {
    return selectedOriginalOption.value !== ''
  }
  return originalTextAnswer.value.trim() !== ''
})

// 计算属性
const questionTypeLabel = computed(() => {
  const typeMap: Record<string, string> = {
    single_choice: '单选题', multiple_choice: '多选题', fill_blank: '填空题',
    solution: '解答题', short_answer: '简答题', essay: '论述题',
    true_false: '判断题', computation: '计算题', proof: '证明题',
  }
  return typeMap[currentQuestion.value.question_type] || currentQuestion.value.question_type || '题目'
})
const hasPrevQuestion = computed(() => currentIndex.value > 0)
const hasNextQuestion = computed(() => currentIndex.value < questions.value.length - 1)

// 页面加载
onLoad((options: any) => {
  questionId.value = parseInt(options?.questionId || '0')
  levelId.value = parseInt(options?.levelId || '0')
  mode.value = options?.mode || ''
})

onMounted(async () => {
  if (!questionId.value) {
    uni.showToast({ title: '缺少题目ID', icon: 'none' })
    return
  }

  // 1. 如果有 levelId，预加载关卡题目列表（用于切题功能）
  if (levelId.value) {
    try {
      const res = await studentApi.levelDetail(levelId.value)
      questions.value = res.data?.questions || []
      currentIndex.value = questions.value.findIndex((q: any) => q.id === questionId.value)
      if (currentIndex.value === -1) currentIndex.value = 0
    } catch (e) {
      console.warn('加载关卡题目列表失败:', e)
    }
  }

  // 2. 启动引导
  await startGuidance()
})

// 启动引导
async function startGuidance() {
  // C 模式：在对话区显示"思考中..."，不显示全屏加载
  if (mode.value === 'C') {
    showThinking.value = true
    await nextTick()
    scrollToBottom()
  } else {
    loading.value = true
  }
  try {
    const res = await studentApi.startGuidance({
      question_id: questionId.value,
      mode_type: mode.value,
    })
    if (res.code !== 0) {
      uni.showToast({ title: res.message || '启动引导失败', icon: 'none' })
      return
    }
    const data = res.data || {}
    sessionId.value = data.session_id || 0
    mode.value = data.mode || mode.value
    stepIndex.value = data.step_index || 0
    totalSteps.value = data.total_steps || 3
    isFallback.value = data.is_fallback || false
    isCorrect.value = null
    selectedOption.value = ''
    isCompleted.value = false
    summary.value = ''
    finalAnswer.value = ''
    options.value = []

    // 添加系统消息
    if (data.hint) {
      messages.value.push({ role: 'system', content: data.hint })
    }
    if (data.options) {
      options.value = data.options
    }
    // 缓存原题信息
    if (data.question_info) {
      currentQuestion.value = data.question_info
      // 从 questions 列表获取原题的正确答案和解析（如果 levelDetail 已加载）
      if (questions.value.length > 0 && currentIndex.value >= 0) {
        const q = questions.value[currentIndex.value]
        originalAnswer.value = q.answer || ''
        originalAnalysis.value = q.analysis || ''
      }
    }
    // 自动滚动到底部
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error('启动引导失败:', e)
    uni.showToast({ title: '启动引导失败', icon: 'none' })
  } finally {
    loading.value = false
    showThinking.value = false
  }
}

// 选择选项（B 模式）
async function selectOption(opt: string) {
  if (submitting.value || !sessionId.value) return
  submitting.value = true
  selectedOption.value = opt
  messages.value.push({ role: 'user', content: opt })

  try {
    const res = await studentApi.guidanceReply(sessionId.value, opt)
    if (res.code !== 0) {
      uni.showToast({ title: res.message || '提交失败', icon: 'none' })
      return
    }
    handleReplyResponse(res.data)
  } catch (e) {
    console.error('提交失败:', e)
    uni.showToast({ title: '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 发送文本（C 模式）
async function sendReply() {
  if (!inputText.value.trim() || submitting.value || !sessionId.value) return
  submitting.value = true
  showThinking.value = true
  const text = inputText.value
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''

  await nextTick()
  scrollToBottom()

  try {
    const res = await studentApi.guidanceReply(sessionId.value, text)
    if (res.code !== 0) {
      uni.showToast({ title: res.message || '发送失败', icon: 'none' })
      return
    }
    handleReplyResponse(res.data)
  } catch (e) {
    console.error('发送失败:', e)
    uni.showToast({ title: '发送失败', icon: 'none' })
  } finally {
    submitting.value = false
    showThinking.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 处理回复响应
function handleReplyResponse(data: any) {
  // 处理降级响应
  if (data.downgraded) {
    mode.value = data.mode || 'B'
    messages.value.push({
      role: 'system',
      content: `⚠️ ${data.downgrade_reason || '已降级到固定选项引导模式'}`,
      type: 'warning',
    })
    if (data.options) {
      options.value = data.options
    }
    if (data.next_hint) {
      messages.value.push({ role: 'system', content: data.next_hint })
    }
    stepIndex.value = data.step_index || 0
    totalSteps.value = data.total_steps || 3
    return
  }

  // B 模式反馈
  if (data.mode === 'B') {
    if (data.is_correct === true) {
      messages.value.push({ role: 'system', content: '✅ 回答正确！', type: 'feedback' })
    } else if (data.is_correct === false) {
      messages.value.push({
        role: 'system',
        content: `❌ 回答错误，正确答案是 ${data.correct_answer}`,
        type: 'feedback',
      })
    }
    if (data.analysis) {
      messages.value.push({ role: 'system', content: `解析：${data.analysis}`, type: 'analysis' })
    }
  }

  // C 模式评价
  if (data.evaluation) {
    messages.value.push({ role: 'system', content: `💬 老师评价：${data.evaluation}`, type: 'evaluation' })
  }

  // 完成状态
  if (data.is_completed) {
    isCompleted.value = true
    summary.value = data.summary || ''
    finalAnswer.value = data.final_answer || ''
    if (summary.value) {
      messages.value.push({ role: 'system', content: `📝 总结：${summary.value}`, type: 'summary' })
    }
    if (finalAnswer.value) {
      messages.value.push({ role: 'system', content: `🎯 最终答案：${finalAnswer.value}`, type: 'final_answer' })
    }
  } else {
    // 更新下一步
    stepIndex.value = data.step_index
    if (data.next_hint) {
      messages.value.push({ role: 'system', content: data.next_hint })
    }
    if (data.options) {
      options.value = data.options
    }
  }
}

// 切换题目
async function nextQuestion() {
  if (!hasNextQuestion.value) {
    uni.showToast({ title: '已经是最后一题', icon: 'none' })
    return
  }
  switching.value = true
  currentIndex.value++
  questionId.value = questions.value[currentIndex.value].id
  resetState()
  await startGuidance()
  switching.value = false
}

async function prevQuestion() {
  if (!hasPrevQuestion.value) {
    uni.showToast({ title: '已经是第一题', icon: 'none' })
    return
  }
  switching.value = true
  currentIndex.value--
  questionId.value = questions.value[currentIndex.value].id
  resetState()
  await startGuidance()
  switching.value = false
}

function resetState() {
  sessionId.value = 0
  messages.value = []
  options.value = []
  isCompleted.value = false
  summary.value = ''
  finalAnswer.value = ''
  isCorrect.value = null
  selectedOption.value = ''
  stepIndex.value = 0
  totalSteps.value = 3
  inputText.value = ''
  submitResult.value = null
  showAnswerSelect.value = false
  selectedOriginalOption.value = ''
  originalTextAnswer.value = ''
  showThinking.value = false
}

// 提交答案（提交用户从原题选项中选择的答案）
async function submitAnswer() {
  if (submittingAnswer.value) return
  submittingAnswer.value = true
  submitResult.value = null

  // 构建答案内容：提交用户从原题选项中选择的答案，而非引导选项
  let answerContent: Record<string, any> = {}
  if (currentQuestion.value.options && currentQuestion.value.options.length > 0) {
    // 客观题：提交用户选择的原题选项标签
    answerContent = { selected_options: [selectedOriginalOption.value] }
  } else {
    // 主观题：提交用户输入的文本
    answerContent = { text: originalTextAnswer.value.trim() }
  }

  try {
    const res = await studentApi.submitAnswer({
      question_id: questionId.value,
      answer_content: answerContent,
      level_id: levelId.value || undefined,
    })
    if (res.code === 0) {
      const data = res.data as any
      submitResult.value = {
        is_correct: data?.is_correct || false,
        score: data?.score || 0,
        feedback: data?.feedback || '',
      }
    } else {
      uni.showToast({ title: res.message || '提交失败', icon: 'none' })
    }
  } catch (e) {
    console.error('提交答案失败:', e)
    uni.showToast({ title: '提交失败，请重试', icon: 'none' })
  } finally {
    submittingAnswer.value = false
  }
}

// 重置提交结果，返回完成页
function resetSubmitResult() {
  submitResult.value = null
  showAnswerSelect.value = false
  selectedOriginalOption.value = ''
  originalTextAnswer.value = ''
}

function goBack() {
  uni.navigateBack()
}

function scrollToBottom() {
  // 每次触发递增 scrollTop 值，强制 scroll-view 滚动到底部
  scrollTop.value += 1
}
</script>

<style scoped>
.guidance-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f0f2f5;
}

/* ====== 全屏加载 ====== */
.fullscreen-loading {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.9);
  z-index: 999;
}
.loading-spinner {
  width: 60rpx; height: 60rpx;
  border: 4rpx solid #ecf5ff;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-text { font-size: 26rpx; color: #666; margin-top: 16rpx; }

/* ====== 思考中指示器（对话区） ====== */
.thinking-bubble {
  background: #f0f2f5 !important;
  color: #666 !important;
  font-size: 24rpx;
}
.thinking-text {
  display: flex;
  align-items: center;
  gap: 2rpx;
}
.thinking-dots text {
  animation: dot-bounce 1.4s infinite;
  font-size: 28rpx;
  font-weight: bold;
  color: #999;
  display: inline-block;
}
.thinking-dots text:nth-child(1) { animation-delay: 0s; }
.thinking-dots text:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots text:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { opacity: 0; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-4rpx); }
}

/* ====== 主内容 ====== */
.guidance-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
}

/* ====== 顶部导航栏 ====== */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10rpx 16rpx;
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
  flex-shrink: 0;
  min-height: 40rpx;
}
.top-bar-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
  min-width: 0;
  flex: 1;
}
.back-btn { font-size: 22rpx; color: #409eff; cursor: pointer; white-space: nowrap; }
.q-position { font-size: 22rpx; color: #333; font-weight: bold; white-space: nowrap; }
.q-type-tag {
  font-size: 18rpx; color: #409eff; background: #ecf5ff;
  padding: 2rpx 10rpx; border-radius: 4rpx; white-space: nowrap;
}
.top-bar-right {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-shrink: 0;
}
.mode-badge {
  font-size: 18rpx; padding: 3rpx 10rpx; border-radius: 4rpx; white-space: nowrap;
}
.mode-badge.badge-b { background: #fff3e0; color: #ff9800; }
.mode-badge.badge-c { background: #e8f5e9; color: #4caf50; }
.step-indicator { font-size: 20rpx; color: #ff9800; font-weight: bold; white-space: nowrap; }

/* ====== 原题题干区 ====== */
.stem-section {
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
  flex-shrink: 0;
  max-height: 30vh;
  overflow-y: auto;
}
.stem-header {
  display: flex;
  justify-content: space-between;
  padding: 6rpx 16rpx;
  cursor: pointer;
  background: #fafafa;
}
.stem-title { font-size: 20rpx; color: #666; }
.stem-toggle { font-size: 18rpx; color: #409eff; }
.stem-body { padding: 0 16rpx 10rpx; }
.stem-content {
  font-size: 22rpx; color: #333; line-height: 1.6;
  white-space: pre-wrap;
}
.stem-options { margin-top: 8rpx; }
.stem-option {
  display: flex; gap: 6rpx;
  padding: 6rpx 10rpx; font-size: 22rpx; color: #555;
  background: #f8f9fa; border-radius: 6rpx; margin-bottom: 4rpx;
}
.stem-opt-label { font-weight: bold; color: #409eff; flex-shrink: 0; }
.stem-images { margin-top: 8rpx; }
.stem-image { width: 100%; border-radius: 6rpx; margin-bottom: 6rpx; }

/* ====== 对话区 ====== */
.chat-area {
  flex: 1;
  padding: 12rpx 16rpx;
  overflow-y: auto;
  min-height: 0;
}
.msg {
  display: flex;
  gap: 8rpx;
  margin-bottom: 14rpx;
}
.msg.user { flex-direction: row-reverse; }
.msg-avatar { font-size: 30rpx; flex-shrink: 0; }
.msg-bubble {
  max-width: 78%;
  padding: 10rpx 14rpx;
  border-radius: 10rpx;
  font-size: 24rpx;
  line-height: 1.5;
}
.msg.system .msg-bubble { background: #fff; color: #333; }
.msg.user .msg-bubble { background: #409eff; color: #fff; }
.msg-bubble.feedback { background: #e8f5e9; color: #2e7d32; }
.msg-bubble.analysis { background: #fff8e1; color: #f57c00; }
.msg-bubble.evaluation { background: #e3f2fd; color: #1565c0; }
.msg-bubble.warning { background: #fff3e0; color: #e65100; }
.msg-bubble.summary { background: #f3e5f5; color: #7b1fa2; }
.msg-bubble.final_answer { background: #e8f5e9; color: #1b5e20; font-weight: bold; }

/* ====== 操作区 ====== */
.action-panel {
  background: #fff;
  border-top: 1rpx solid #e8e8e8;
  padding: 10rpx 16rpx 12rpx;
  flex-shrink: 0;
  max-height: 45vh;
  overflow-y: auto;
}
.section-title {
  font-size: 22rpx; font-weight: bold; color: #333;
  margin-bottom: 8rpx; display: block;
}

/* B 模式选项 */
.options-section {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.option-btn {
  background: #f8f9fa;
  border: 1rpx solid #ddd;
  text-align: left;
  padding: 10rpx 16rpx;
  font-size: 22rpx;
  border-radius: 8rpx;
  height: auto;
  line-height: 1.4;
}
.option-btn.selected {
  background: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
}
.option-btn:disabled {
  opacity: 0.7;
}
.btn-loading { margin-right: 6rpx; }

/* C 模式输入 */
.input-section { display: flex; flex-direction: column; }
.input-row { display: flex; gap: 8rpx; }
.text-input {
  flex: 1;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 10rpx 14rpx;
  font-size: 22rpx;
  height: auto;
  min-height: 66rpx;
}
.send-btn {
  background: #409eff;
  color: #fff;
  font-size: 22rpx;
  padding: 10rpx 24rpx;
  height: auto;
  border-radius: 8rpx;
  flex-shrink: 0;
}
.send-btn:disabled { background: #ccc; }

/* 完成状态 */
.complete-section {
  text-align: center;
  padding: 10rpx 0;
}
.complete-icon { font-size: 56rpx; display: block; margin-bottom: 4rpx; }
.complete-title { font-size: 26rpx; font-weight: bold; color: #333; display: block; margin-bottom: 10rpx; }
.complete-summary, .complete-final {
  text-align: left;
  background: #f8f9fa;
  border-radius: 8rpx;
  padding: 10rpx 14rpx;
  margin-bottom: 8rpx;
}
.summary-label, .final-label { font-size: 22rpx; font-weight: bold; color: #666; }
.summary-text, .final-text { font-size: 22rpx; color: #333; line-height: 1.5; }

/* 选择原题答案区域 */
.answer-select-section {
  text-align: center;
  padding: 6rpx 0;
}
.select-title {
  font-size: 24rpx; font-weight: bold; color: #333;
  display: block; margin-bottom: 10rpx;
}
.select-options {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 12rpx;
}
.select-option-btn {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: #f8f9fa;
  border: 2rpx solid #ddd;
  text-align: left;
  padding: 10rpx 16rpx;
  font-size: 22rpx;
  border-radius: 10rpx;
  height: auto;
  line-height: 1.4;
  transition: all 0.2s;
}
.select-option-btn.selected {
  background: #ecf5ff;
  border-color: #409eff;
  box-shadow: 0 0 0 2rpx rgba(64, 158, 255, 0.3);
}
.select-opt-label {
  font-weight: bold;
  color: #409eff;
  flex-shrink: 0;
  width: 36rpx;
  height: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecf5ff;
  border-radius: 50%;
  font-size: 20rpx;
}
.select-option-btn.selected .select-opt-label {
  background: #409eff;
  color: #fff;
}
.select-opt-content { color: #333; font-size: 22rpx; }
.select-text-area { margin-bottom: 12rpx; }
.select-text-input {
  width: 100%;
  min-height: 100rpx;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 10rpx 14rpx;
  font-size: 22rpx;
  box-sizing: border-box;
}

/* 提交结果 */
.submit-result-section {
  text-align: center;
  padding: 10rpx 0;
}
.result-icon { font-size: 60rpx; display: block; margin-bottom: 4rpx; }
.result-title { font-size: 28rpx; font-weight: bold; display: block; margin-bottom: 6rpx; }
.result-title.correct { color: #4caf50; }
.result-title.incorrect { color: #f44336; }
.result-score { font-size: 24rpx; color: #666; display: block; margin-bottom: 8rpx; }
.result-feedback {
  font-size: 22rpx; color: #333; display: block; margin-bottom: 10rpx;
  background: #f8f9fa; border-radius: 8rpx; padding: 10rpx 14rpx; text-align: left;
}
.result-answer, .result-analysis {
  text-align: left;
  background: #fff8e1;
  border-radius: 8rpx;
  padding: 10rpx 14rpx;
  margin-bottom: 8rpx;
}
.result-label { font-size: 22rpx; font-weight: bold; color: #f57c00; }
.result-value { font-size: 22rpx; color: #333; line-height: 1.5; }

.complete-actions {
  display: flex;
  gap: 8rpx;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 10rpx;
}
.action-btn {
  font-size: 22rpx;
  padding: 10rpx 20rpx;
  height: auto;
  border-radius: 8rpx;
  min-width: 100rpx;
}
.submit-btn { background: #409eff; color: #fff; }
.back-btn { background: #fff; color: #409eff; border: 1rpx solid #409eff; }
.prev-btn { background: #fff; color: #666; border: 1rpx solid #ddd; }
.next-btn { background: #ff9800; color: #fff; }

/* 底部导航 */
.bottom-nav {
  display: flex;
  gap: 8rpx;
  justify-content: space-between;
}
.nav-btn {
  flex: 1;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  font-size: 22rpx;
  padding: 10rpx 0;
  height: auto;
  border-radius: 8rpx;
}
.nav-btn:disabled { opacity: 0.5; }

/* ====== 平板适配（横向） ====== */
@media (min-width: 768px) {
  .chat-area {
    padding: 16rpx 24rpx;
  }
  .msg-bubble {
    max-width: 65%;
    font-size: 26rpx;
    padding: 12rpx 18rpx;
  }
  .action-panel {
    padding: 14rpx 24rpx 16rpx;
  }
  .option-btn, .select-option-btn {
    padding: 12rpx 20rpx;
    font-size: 24rpx;
  }
  .complete-actions {
    gap: 12rpx;
  }
  .action-btn {
    font-size: 24rpx;
    padding: 12rpx 28rpx;
    min-width: 120rpx;
  }
}

/* 小屏适配 */
@media (max-width: 768px) {
  .top-bar { flex-wrap: wrap; gap: 4rpx; padding: 8rpx 12rpx; }
  .top-bar-left, .top-bar-right { width: 100%; justify-content: space-between; }
  .complete-actions { flex-direction: column; align-items: stretch; }
  .action-btn { width: 100%; }
  .stem-section { max-height: 25vh; }
  .action-panel { max-height: 40vh; padding: 8rpx 12rpx 10rpx; }
}
</style>