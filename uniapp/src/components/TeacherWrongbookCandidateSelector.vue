<template>
  <view class="selector-mask" @click.self="$emit('close')">
    <view class="selector-dialog">
      <view class="selector-header">
        <view>
          <text class="selector-title">手动选择同类题</text>
          <text class="selector-subtitle">AI推荐失败、无关联题或推荐不足时使用</text>
        </view>
        <button size="mini" class="close-button" @click="$emit('close')">关闭</button>
      </view>

      <scroll-view scroll-y class="selector-body">
        <view v-for="group in groups" :key="group.item_id" class="candidate-group">
          <view class="group-header">
            <view>
              <text class="group-title">{{ group.student_name }} · 第{{ group.source_question_no || '?' }}题</text>
              <text class="group-reason">{{ group.reason_label }}</text>
            </view>
            <text class="group-count">
              已选择 {{ (selected[group.item_id] || []).length }}/{{ group.selection_limit || 3 }}
            </text>
          </view>
          <view v-if="group.source_question?.stem" class="source-question">
            <text class="source-label">原错题：</text>
            <text class="source-text">{{ group.source_question.stem }}</text>
          </view>
          <view v-if="!group.candidates?.length" class="empty-candidates">
            暂无符合条件的同类题，请重新尝试 AI 推荐或调整错题范围。
          </view>
          <view
            v-for="candidate in (group.candidates || [])"
            :key="candidate.recommendation_id"
            class="candidate-row"
            :class="{ selected: isSelected(group, candidate) }"
            @click="toggleCandidate(group, candidate)"
          >
            <checkbox
              :checked="isSelected(group, candidate)"
              :disabled="!isSelected(group, candidate) && isGroupFull(group)"
              @click.stop="toggleCandidate(group, candidate)"
            />
            <view class="candidate-content">
              <view class="candidate-meta">
                <text class="candidate-no">第{{ candidate.candidate?.question_no || '?' }}题</text>
                <text class="candidate-source">{{ candidate.provider === 'ai' ? 'AI推荐' : '题库同类题' }}</text>
              </view>
              <rich-text
                v-if="candidate.candidate?.stem_html"
                class="candidate-stem"
                :nodes="candidate.candidate.stem_html"
              />
              <text v-else class="candidate-stem">{{ candidate.candidate?.stem || '暂无题干内容' }}</text>
            </view>
          </view>
        </view>
        <view v-if="!groups.length" class="empty-groups">暂无需要人工选择的错题。</view>
      </scroll-view>

      <view class="selector-footer">
        <text class="footer-tip">每道错题最多选择 3 道同类题</text>
        <view class="footer-actions">
          <button size="mini" @click="$emit('close')">取消</button>
          <button size="mini" type="primary" :disabled="submitting || !canConfirm" @click="confirm">
            {{ submitting ? '生成中...' : '确认生成错题练习' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface CandidateGroup {
  item_id: string
  selection_limit?: number
  candidates?: Array<{ recommendation_id: string; candidate_question_id?: string; candidate?: { id?: string; question_no?: string; stem?: string; stem_html?: string }; provider?: string }>
  [key: string]: any
}

const props = defineProps<{
  groups: CandidateGroup[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'confirm', groups: Array<{ student_id: string; source_wrong_book_item_id: string; candidate_question_ids: string[] }>): void
}>()

const selected = ref<Record<string, string[]>>({})

watch(() => props.groups, (groups) => {
  const next: Record<string, string[]> = {}
  for (const group of groups || []) next[group.item_id] = selected.value[group.item_id] || []
  selected.value = next
}, { immediate: true, deep: true })

const canConfirm = computed(() => (props.groups || []).length > 0 && props.groups.every((group) => {
  const required = Math.min(group.selection_limit || 3, (group.candidates || []).length)
  return required > 0 && (selected.value[group.item_id] || []).length === required
}))

function isSelected(group: CandidateGroup, candidate: any) {
  return (selected.value[group.item_id] || []).includes(candidate.recommendation_id)
}

function isGroupFull(group: CandidateGroup) {
  return (selected.value[group.item_id] || []).length >= (group.selection_limit || 3)
}

function toggleCandidate(group: CandidateGroup, candidate: any) {
  const current = selected.value[group.item_id] || []
  if (current.includes(candidate.recommendation_id)) {
    selected.value[group.item_id] = current.filter(id => id !== candidate.recommendation_id)
    return
  }
  if (isGroupFull(group)) return
  selected.value[group.item_id] = [...current, candidate.recommendation_id]
}

function confirm() {
  if (!canConfirm.value) {
    uni.showToast({ title: '请完成所有错题的同类题选择', icon: 'none' })
    return
  }
  emit('confirm', (props.groups || []).map(group => ({
    student_id: group.student_id,
    source_wrong_book_item_id: group.source_wrong_book_item_id,
    candidate_question_ids: (selected.value[group.item_id] || []).map((recommendationId) => {
      const candidate = (group.candidates || []).find(item => item.recommendation_id === recommendationId)
      return candidate?.candidate_question_id || candidate?.candidate?.id || recommendationId
    }),
  })))
}
</script>

<style scoped>
.selector-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; box-sizing: border-box; background: rgba(0, 0, 0, .45); }
.selector-dialog { width: min(860px, 94vw); max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; background: #fff; border-radius: 10px; box-shadow: 0 8px 30px rgba(0, 0, 0, .2); }
.selector-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px 20px; border-bottom: 1px solid #ebeef5; }
.selector-title, .selector-subtitle, .group-title, .group-reason, .source-label, .source-text, .candidate-no, .candidate-source, .candidate-stem, .footer-tip { display: block; }
.selector-title { color: #303133; font-size: 17px; font-weight: 600; }
.selector-subtitle { margin-top: 5px; color: #909399; font-size: 12px; }
.close-button { margin: 0; color: #606266; background: #fff; border: 1px solid #dcdfe6; }
.selector-body { flex: 1; min-height: 180px; max-height: calc(90vh - 138px); padding: 14px 20px; box-sizing: border-box; }
.candidate-group { padding: 14px; margin-bottom: 12px; background: #f8fafc; border: 1px solid #ebeef5; border-radius: 8px; }
.group-header { display: flex; justify-content: space-between; gap: 12px; }
.group-title { color: #303133; font-size: 14px; font-weight: 600; }
.group-reason { margin-top: 5px; color: #e6a23c; font-size: 12px; }
.group-count { flex: 0 0 auto; color: #409eff; font-size: 12px; }
.source-question { padding: 10px 0; color: #606266; font-size: 12px; line-height: 1.6; }
.source-label { display: inline; color: #909399; }
.source-text { display: inline; }
.candidate-row { display: flex; align-items: flex-start; gap: 8px; padding: 11px 8px; margin-top: 7px; background: #fff; border: 1px solid #ebeef5; border-radius: 6px; }
.candidate-row.selected { background: #ecf5ff; border-color: #409eff; }
.candidate-content { flex: 1; min-width: 0; }
.candidate-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
.candidate-no { color: #303133; font-size: 13px; font-weight: 600; }
.candidate-source { padding: 2px 6px; color: #67c23a; background: #f0f9eb; border-radius: 3px; font-size: 11px; }
.candidate-stem { color: #606266; font-size: 12px; line-height: 1.6; word-break: break-word; }
.empty-candidates, .empty-groups { padding: 28px 10px; color: #909399; text-align: center; font-size: 13px; }
.selector-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 20px; border-top: 1px solid #ebeef5; }
.footer-tip { color: #909399; font-size: 12px; }
.footer-actions { display: flex; gap: 8px; }
.footer-actions button { margin: 0; }
@media (max-width: 640px) {
  .selector-mask { padding: 8px; align-items: flex-end; }
  .selector-dialog { width: 100%; max-height: 94vh; }
  .selector-body { padding: 10px; max-height: calc(94vh - 145px); }
  .selector-header, .selector-footer { padding: 13px; }
  .selector-footer { align-items: flex-end; flex-direction: column; }
  .footer-actions { width: 100%; justify-content: flex-end; }
}
</style>
