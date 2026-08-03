<template>
  <view v-if="visible" class="question-ai-controls__mask" @click.self="handleClose">
    <view class="question-ai-controls">
      <view class="question-ai-controls__header">
        <text class="question-ai-controls__title">AI处理题目</text>
        <button class="question-ai-controls__close" @click="handleClose">关闭</button>
      </view>
      <view class="question-ai-controls__actions">
        <button :disabled="isRunningForSelectedQuestion" @click="startAction('all')">一键全部AI处理</button>
        <button :disabled="isRunningForSelectedQuestion" @click="startAction('probe')">AI探查</button>
        <button :disabled="isRunningForSelectedQuestion" @click="startAction('A')">A模式</button>
        <button :disabled="isRunningForSelectedQuestion" @click="startAction('B')">B模式</button>
        <button :disabled="isRunningForSelectedQuestion" @click="startAction('C')">C模式</button>
      </view>
      <text v-if="isRunningForSelectedQuestion" class="question-ai-controls__status">AI任务处理中，请稍候</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { aiProcessProbe, aiProcessQuestion, aiProcessSingleMode, getAiTaskStatus } from '@/api/questions'

type AIAction = 'all' | 'probe' | 'A' | 'B' | 'C'
type TerminalStatus = 'complete' | 'partial' | 'failed' | 'skipped'

const props = defineProps<{
  visible: boolean
  questionId: string | number | null
}>()

const emit = defineEmits<{
  close: []
  completed: [payload: { action: AIAction }]
}>()

const running = ref(false)
const runningQuestionId = ref<string | number | null>(null)
const activeTaskId = ref<string | null>(null)
const activeAction = ref<AIAction | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const terminalStatuses: TerminalStatus[] = ['complete', 'partial', 'failed', 'skipped']
const isRunningForSelectedQuestion = computed(() => (
  running.value && runningQuestionId.value === props.questionId
))

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  activeTaskId.value = null
  activeAction.value = null
  running.value = false
  runningQuestionId.value = null
}

function showToast(title: string, icon: 'none' | 'success' = 'none') {
  uni.showToast({ title, icon })
}

function handleClose() {
  if (pollTimer) clearInterval(pollTimer)
  stopPolling()
  emit('close')
}

async function pollStatus() {
  const taskId = activeTaskId.value
  if (!taskId) return

  try {
    const response: any = await getAiTaskStatus(taskId)
    if (taskId !== activeTaskId.value) return

    const task = response?.data ?? response
    const status = task?.status as TerminalStatus | undefined
    if (!status || !terminalStatuses.includes(status)) return

    const action = activeAction.value
    stopPolling()
    if (status === 'complete' || status === 'partial') {
      showToast(status === 'complete' ? 'AI处理完成' : 'AI处理部分完成', 'success')
      if (action) emit('completed', { action })
      return
    }
    showToast(status === 'skipped' ? 'AI处理已跳过' : 'AI处理失败，请稍后重试')
  } catch {
    if (taskId !== activeTaskId.value) return
    stopPolling()
    showToast('AI任务状态获取失败，请稍后重试')
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(pollStatus, 2000)
  void pollStatus()
}

async function startAction(action: AIAction) {
  if (props.questionId === null) {
    showToast('请先保存题目')
    return
  }
  if (running.value) return

  running.value = true
  runningQuestionId.value = props.questionId
  activeAction.value = action
  try {
    let response: any
    if (action === 'all') {
      response = await aiProcessQuestion(props.questionId)
    } else if (action === 'probe') {
      response = await aiProcessProbe(props.questionId)
    } else if (action === 'A') {
      response = await aiProcessSingleMode(props.questionId, 'A')
    } else if (action === 'B') {
      response = await aiProcessSingleMode(props.questionId, 'B')
    } else if (action === 'C') {
      response = await aiProcessSingleMode(props.questionId, 'C')
    }

    const taskId = response?.data?.task_id ?? response?.task_id
    if (!taskId) throw new Error('Missing AI task ID')
    activeTaskId.value = String(taskId)
    startPolling()
  } catch {
    stopPolling()
    showToast('AI处理启动失败，请稍后重试')
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) stopPolling()
  },
)

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  stopPolling()
})
</script>

<style scoped>
.question-ai-controls__mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  background: rgba(0, 0, 0, 0.45);
}

.question-ai-controls {
  width: 100%;
  padding: 32rpx;
  box-sizing: border-box;
  border-radius: 24rpx 24rpx 0 0;
  background: #fff;
}

.question-ai-controls__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24rpx;
}

.question-ai-controls__title {
  font-size: 32rpx;
  font-weight: 600;
}

.question-ai-controls__close {
  margin: 0;
  padding: 0 16rpx;
  font-size: 26rpx;
  line-height: 1.8;
  color: #666;
  background: transparent;
}

.question-ai-controls__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16rpx;
}

.question-ai-controls__actions button:first-child {
  grid-column: span 2;
}

.question-ai-controls__actions button {
  margin: 0;
  font-size: 28rpx;
  color: #fff;
  background: #3478f6;
}

.question-ai-controls__status {
  display: block;
  margin-top: 20rpx;
  font-size: 24rpx;
  color: #666;
  text-align: center;
}
</style>
