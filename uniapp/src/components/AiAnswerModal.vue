<template>
  <view v-if="visible" class="ai-answer-mask" @click.self="close">
    <view class="ai-answer-modal">
      <view class="ai-answer-header">
        <view>
          <text class="ai-answer-title">AI答案</text>
          <text v-if="question?.question_no" class="ai-answer-question">题目 {{ question.question_no }}</text>
        </view>
        <button class="modal-close" @click="close">关闭</button>
      </view>

      <view class="answer-columns" :class="{ 'single-column': mode !== 'ALL' }">
        <view v-for="item in visibleModes" :key="item" class="answer-column">
          <view class="column-header">
            <text class="column-title">{{ item }}模式答案</text>
            <text v-if="answerExists(item)" class="answer-status">已生成</text>
            <text v-else class="answer-status empty">未生成</text>
          </view>

          <scroll-view v-if="editingMode !== item" scroll-y class="column-content">
            <rich-text v-if="answerHtml[item]" :nodes="answerHtml[item]"></rich-text>
            <text v-else class="empty-answer">暂无答案，请点击重新处理。</text>
          </scroll-view>

          <textarea
            v-else
            v-model="editingText"
            class="answer-editor"
            maxlength="-1"
            placeholder="请输入答案内容"
          />

          <view class="column-actions">
            <template v-if="editingMode === item">
              <button size="mini" @click="cancelEdit">取消</button>
              <button size="mini" type="primary" :disabled="saving" @click="saveEdit(item)">
                {{ saving ? '保存中' : '保存内容' }}
              </button>
            </template>
            <template v-else>
              <button size="mini" type="primary" :disabled="reprocessing[item]" @click="reprocess(item)">
                {{ reprocessing[item] ? '处理中...' : '重新处理' }}
              </button>
              <button size="mini" @click="startEdit(item)" :disabled="!answerExists(item)">编辑内容</button>
            </template>
          </view>
        </view>
      </view>

    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { questionApi, getAiTaskStatus } from '@/api/questions'
import { renderWithKatex } from '@/utils/katex-renderer'

type AnswerMode = 'A' | 'B' | 'C'

const props = defineProps<{
  visible: boolean
  question: any | null
  mode?: AnswerMode | 'ALL'
}>()

const emit = defineEmits<{
  close: []
  saved: [payload: { mode: AnswerMode }]
  reprocessed: [payload: { mode: AnswerMode }]
}>()

const modes: AnswerMode[] = ['A', 'B', 'C']
const answerHtml = ref<Record<AnswerMode, string>>({ A: '', B: '', C: '' })
const editingMode = ref<AnswerMode | null>(null)
const editingText = ref('')
const saving = ref(false)
const reprocessing = ref<Record<AnswerMode, boolean>>({ A: false, B: false, C: false })
const reprocessTimers: Partial<Record<AnswerMode, ReturnType<typeof setInterval>>> = {}

const mode = computed(() => props.mode || 'ALL')
const visibleModes = computed(() => mode.value === 'ALL' ? modes : [mode.value])

function rawAnswer(answerMode: AnswerMode) {
  return props.question?.[`ai_answer_${answerMode.toLowerCase()}`]
}

function answerExists(answerMode: AnswerMode) {
  return !!rawAnswer(answerMode)
}

function getEditableText(answer: any) {
  if (!answer) return ''
  if (answer.edited_content?.content) return String(answer.edited_content.content)
  return formatAnswer(answer)
}

function formatAnswer(answer: any): string {
  if (!answer) return ''
  if (typeof answer === 'string') return answer
  try {
    const value = typeof answer === 'object' ? answer : JSON.parse(answer)
    if (value.edited_content?.content) return String(value.edited_content.content)
    if (value.steps) {
      return value.steps.map((step: any, index: number) =>
        `步骤${step.step_number ?? step.step ?? index + 1}：${step.description ? `${step.description}\n` : ''}${step.content || ''}`
      ).join('\n\n') + `\n\n最终答案：${value.final_answer || '-'}` + (value.summary ? `\n\n总结：${value.summary}` : '')
    }
    if (value.questions) {
      return value.questions.map((item: any, index: number) => {
        const options = item.options
          ? (Array.isArray(item.options) ? item.options.join('\n') : Object.entries(item.options).map(([key, text]) => `${key}. ${text}`).join('\n'))
          : ''
        return `问题${index + 1}：${item.question || ''}\n${options}${item.correct_option ? `\n正确答案：${item.correct_option}` : ''}${item.reference_answer ? `\n参考答案：${item.reference_answer}` : ''}${item.analysis ? `\n解析：${item.analysis}` : ''}`
      }).join('\n\n') + `\n\n最终答案：${value.final_answer || '-'}` + (value.summary ? `\n\n总结：${value.summary}` : '')
    }
    return JSON.stringify(value, null, 2)
  } catch {
    return String(answer)
  }
}

async function renderAnswers() {
  for (const item of modes) {
    answerHtml.value[item] = answerExists(item) ? await renderWithKatex(formatAnswer(rawAnswer(item))) : ''
  }
}

function close() {
  if (editingMode.value) cancelEdit()
  emit('close')
}

function startEdit(item: AnswerMode) {
  editingMode.value = item
  editingText.value = getEditableText(rawAnswer(item))
}

function cancelEdit() {
  editingMode.value = null
  editingText.value = ''
}

async function saveEdit(item: AnswerMode) {
  if (!props.question?.id || !editingText.value.trim()) return
  saving.value = true
  try {
    await questionApi.aiUpdateAnswer(props.question.id, item, { content: editingText.value.trim() })
    uni.showToast({ title: '答案内容已保存', icon: 'success' })
    cancelEdit()
    emit('saved', { mode: item })
  } catch {
    uni.showToast({ title: '答案保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function stopReprocessPolling(item: AnswerMode) {
  const timer = reprocessTimers[item]
  if (timer) clearInterval(timer)
  delete reprocessTimers[item]
  reprocessing.value[item] = false
}

async function pollReprocessStatus(item: AnswerMode, taskId: string) {
  try {
    const response: any = await getAiTaskStatus(taskId)
    const task = response?.data ?? response
    const status = task?.status
    if (!['complete', 'partial', 'failed', 'skipped'].includes(status)) return

    stopReprocessPolling(item)
    if (status === 'complete' || status === 'partial') {
      uni.showToast({ title: status === 'complete' ? `${item}模式处理完成` : `${item}模式部分完成`, icon: 'success' })
      emit('reprocessed', { mode: item })
      return
    }
    uni.showToast({ title: `${item}模式处理失败，请稍后重试`, icon: 'none' })
  } catch {
    stopReprocessPolling(item)
    uni.showToast({ title: `${item}模式任务状态获取失败`, icon: 'none' })
  }
}

async function reprocess(item: AnswerMode) {
  if (!props.question?.id) return
  if (reprocessing.value[item]) return
  reprocessing.value[item] = true
  try {
    const response: any = await questionApi.aiProcessMode(props.question.id, item)
    const taskId = response?.data?.task_id ?? response?.task_id
    if (!taskId) throw new Error('Missing AI task ID')
    reprocessTimers[item] = setInterval(() => void pollReprocessStatus(item, String(taskId)), 2000)
    void pollReprocessStatus(item, String(taskId))
  } catch {
    stopReprocessPolling(item)
    uni.showToast({ title: `${item}模式处理启动失败`, icon: 'none' })
  }
}

watch(() => [props.visible, props.question, props.mode], () => {
  if (props.visible) void renderAnswers()
}, { deep: true, immediate: true })

watch(() => props.visible, (visible) => {
  if (!visible) modes.forEach(stopReprocessPolling)
})

onUnmounted(() => modes.forEach(stopReprocessPolling))
</script>

<style scoped>
.ai-answer-mask { position: fixed; inset: 0; z-index: 1001; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, .45); padding: 20px; box-sizing: border-box; }
.ai-answer-modal { width: min(1120px, 96vw); max-height: 90vh; display: flex; flex-direction: column; padding: 20px; box-sizing: border-box; background: #fff; border-radius: 8px; overflow: hidden; }
.ai-answer-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.ai-answer-title { display: block; font-size: 18px; font-weight: 600; color: #303133; }
.ai-answer-question { display: block; margin-top: 5px; font-size: 12px; color: #909399; }
.modal-close { margin: 0; padding: 3px 10px; font-size: 12px; color: #606266; background: #fff; border: 1px solid #dcdfe6; }
.answer-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; min-height: 0; overflow-y: auto; }
.answer-columns.single-column { grid-template-columns: minmax(0, 1fr); }
.answer-column { min-width: 0; display: flex; flex-direction: column; padding: 12px; border: 1px solid #ebeef5; border-radius: 6px; background: #fafafa; }
.column-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.column-title { color: #409eff; font-size: 14px; font-weight: 600; }
.answer-status { color: #67c23a; font-size: 11px; }
.answer-status.empty { color: #909399; }
.column-content { height: 360px; padding: 10px; box-sizing: border-box; background: #fff; border: 1px solid #ebeef5; color: #606266; font-size: 13px; line-height: 1.7; }
.empty-answer { color: #909399; }
.answer-editor { width: 100%; height: 360px; padding: 10px; box-sizing: border-box; background: #fff; border: 1px solid #409eff; color: #303133; font-size: 13px; line-height: 1.7; }
.column-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
.column-actions button { margin: 0; }
@media (max-width: 760px) { .ai-answer-mask { padding: 8px; } .ai-answer-modal { padding: 14px; } .answer-columns { grid-template-columns: 1fr; } .column-content, .answer-editor { height: 260px; } }
</style>
