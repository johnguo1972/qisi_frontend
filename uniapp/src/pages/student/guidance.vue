<template>
  <view class="guidance-page">
    <!-- 左侧对话区 -->
    <view class="chat-panel">
      <view class="mode-header">
        <view class="mode-badge">
          <text>{{ mode === 'B' ? '引导模式 (选择)' : '自由对话' }}</text>
        </view>
      </view>
      <scroll-view scroll-y class="chat-area">
        <view v-for="(msg, i) in messages" :key="i" :class="['msg', msg.role]">
          <view class="msg-avatar">{{ msg.role === 'system' ? '🤖' : '👤' }}</view>
          <view class="msg-bubble">
            <text>{{ msg.content }}</text>
          </view>
        </view>
      </scroll-view>
    </view>
    <!-- 右侧操作区 -->
    <view class="action-panel">
      <!-- B 模式：选项 -->
      <view v-if="mode === 'B' && options.length > 0" class="options-section">
        <text class="section-title">选择你的答案</text>
        <button v-for="opt in options" :key="opt" @click="selectOption(opt)" class="option-btn">
          {{ opt }}
        </button>
      </view>

      <!-- C 模式：文本输入 -->
      <view v-if="mode === 'C'" class="input-section">
        <text class="section-title">输入你的想法</text>
        <view class="input-row">
          <input v-model="inputText" placeholder="输入你的想法..." class="text-input" />
          <button @click="sendReply" class="send-btn">发送</button>
        </view>
      </view>

      <!-- 完成状态 -->
      <view v-if="isCompleted" class="complete-section">
        <text class="complete-icon">🎉</text>
        <text class="complete-text">引导完成！返回做题页继续吧。</text>
        <button @click="goBack" class="back-btn">返回做题</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { studentApi } from '@/api/student.ts'

const questionId = ref(0)
const sessionId = ref(0)
const mode = ref('B')
const messages = ref<{ role: string; content: string }[]>([])
const options = ref<string[]>([])
const inputText = ref('')
const isCompleted = ref(false)

<<<<<<< HEAD
onMounted(async () => {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  questionId.value = parseInt(page.options.questionId || '0')
  // 从 URL 参数获取 mode，默认 B
  const urlMode = page.options.mode || 'B'

=======
onLoad((options: any) => {
  questionId.value = parseInt(options.questionId || '0')
>>>>>>> c39c149702ee1b34309a8b0675bb400fbacd2398
  if (!questionId.value) {
    uni.showToast({ title: '缺少题目ID', icon: 'none' })
    return
  }
})

onMounted(async () => {
  if (!questionId.value) return

  try {
    const res = await studentApi.startGuidance({ question_id: questionId.value, mode_type: urlMode })
    sessionId.value = res.data?.session_id || 0
    mode.value = res.data?.mode || urlMode
    if (res.data?.hint) {
      messages.value.push({ role: 'system', content: res.data.hint })
    }
    if (res.data?.options) {
      options.value = res.data.options
    }
    if (res.data?.question) {
      messages.value.push({ role: 'system', content: res.data.question })
    }
  } catch (e) {
    uni.showToast({ title: '启动引导失败', icon: 'none' })
  }
})

function selectOption(opt: string) {
  messages.value.push({ role: 'user', content: opt })
  sendReplyInternal(opt)
}

function sendReply() {
  if (!inputText.value.trim()) return
  messages.value.push({ role: 'user', content: inputText.value })
  sendReplyInternal(inputText.value)
  inputText.value = ''
}

async function sendReplyInternal(reply: string) {
  try {
    const res = await studentApi.guidanceReply(sessionId.value, reply)
    // C 模式：先显示真实 LLM 评价，再显示下一个引导问题
    const seg: string[] = []
    if (res.data?.evaluation) seg.push(`老师评价：${res.data.evaluation}`)
    const hint = res.data?.next_hint || res.data?.next_question
    if (hint) seg.push(hint)
    if (seg.length) messages.value.push({ role: 'system', content: seg.join('\n\n') })
    if (res.data?.is_completed) {
      isCompleted.value = true
    }
    if (res.data?.mode === 'B' && res.data?.reason) {
      mode.value = 'B'
      messages.value.push({ role: 'system', content: `已降级到B模式：${res.data.reason}` })
    }
  } catch (e) {
    uni.showToast({ title: '发送失败', icon: 'none' })
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.guidance-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.mode-header {
  padding: 16rpx 24rpx;
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
}
.mode-badge {
  display: inline-block;
  padding: 6rpx 20rpx;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 4rpx;
  font-size: 24rpx;
}
.chat-area {
  flex: 1;
  padding: 24rpx;
}
.msg {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.msg.user {
  flex-direction: row-reverse;
}
.msg-avatar {
  font-size: 36rpx;
}
.msg-bubble {
  max-width: 70%;
  padding: 16rpx 20rpx;
  border-radius: 12rpx;
  font-size: 26rpx;
  line-height: 1.6;
}
.msg.system .msg-bubble {
  background: #fff;
  color: #333;
}
.msg.user .msg-bubble {
  background: #409eff;
  color: #fff;
}
.action-panel {
  width: 320px;
  background: #fff;
  border-left: 1rpx solid #e8e8e8;
  padding: 24rpx;
  display: flex;
  flex-direction: column;
}
.section-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 16rpx;
  display: block;
}
.options-section {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.option-btn {
  background: #f8f8f8;
  border: 1rpx solid #ddd;
  text-align: left;
  padding: 16rpx 20rpx;
  font-size: 24rpx;
  border-radius: 8rpx;
}
.option-btn:hover {
  background: #ecf5ff;
  border-color: #409eff;
}
.input-section {
  display: flex;
  flex-direction: column;
}
.input-row {
  display: flex;
  gap: 12rpx;
}
.text-input {
  flex: 1;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 16rpx;
  font-size: 24rpx;
}
.send-btn {
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
  padding: 16rpx 24rpx;
}
.complete-section {
  text-align: center;
  padding: 40rpx 0;
  background: #f8f8f8;
  border-radius: 12rpx;
  margin-top: auto;
}
.complete-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 16rpx;
}
.complete-text {
  font-size: 26rpx;
  color: #666;
  display: block;
  margin-bottom: 20rpx;
}
.back-btn {
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .guidance-page {
    flex-direction: column;
  }
  .action-panel {
    width: 100%;
    border-left: none;
    border-top: 1rpx solid #e8e8e8;
    max-height: 400px;
  }
}
</style>
