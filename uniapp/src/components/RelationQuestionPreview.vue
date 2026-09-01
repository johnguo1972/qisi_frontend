<template>
  <view class="relation-question-preview">
    <view class="relation-question-row">
      <view v-if="$slots.leading" class="relation-question-leading">
        <slot name="leading" />
      </view>
      <view class="relation-question-content">
        <view class="relation-question-stem">
          <text class="relation-question-number">{{ item.question_no }}：</text>
          <rich-text :nodes="stemHtml" />
        </view>

        <view v-if="item.option_previews?.length" class="relation-question-options">
          <view v-for="option in item.option_previews" :key="`${item.id}-${option.label}`" class="relation-question-option">
            <text class="relation-option-label">{{ option.label }}.</text>
            <rich-text :nodes="optionHtmls[option.label] || ''" />
          </view>
        </view>

        <view class="relation-question-meta">
          <text v-if="item.common_knowledge_point_names?.length" class="relation-meta-item">
            共同知识点：{{ item.common_knowledge_point_names.join('、') }}
          </text>
          <text class="relation-meta-item">难度系数：{{ difficultyText }}</text>
        </view>
      </view>
      <view v-if="$slots.trailing" class="relation-question-trailing">
        <slot name="trailing" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { QuestionRelationItem } from '@/api/questions'
import { renderWithKatex } from '@/utils/katex-renderer'

const props = defineProps<{
  item: QuestionRelationItem
}>()

const stemHtml = ref('')
const optionHtmls = ref<Record<string, string>>({})
let renderSequence = 0

const difficultyText = computed(() => {
  const value = props.item.difficulty
  if (value === null || value === undefined || value === '') return '未设置'
  return String(value)
})

async function renderPreview(): Promise<void> {
  const sequence = ++renderSequence
  const options = props.item.option_previews || []
  const [nextStemHtml, ...nextOptionHtmls] = await Promise.all([
    renderWithKatex(props.item.stem_preview || ''),
    ...options.map((option) => renderWithKatex(option.content || '')),
  ])
  if (sequence !== renderSequence) return
  stemHtml.value = nextStemHtml
  optionHtmls.value = Object.fromEntries(
    options.map((option, index) => [option.label, nextOptionHtmls[index] || '']),
  )
}

watch(() => props.item, () => {
  void renderPreview()
}, { immediate: true, deep: true })
</script>

<style scoped>
.relation-question-preview {
  padding: 8px 0;
  border-bottom: 1px solid #edf1f7;
  font-size: 12px;
  color: #2d3a4b;
}

.relation-question-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.relation-question-leading {
  flex: none;
  padding-top: 3px;
}

.relation-question-content {
  min-width: 0;
  flex: 1;
}

.relation-question-stem,
.relation-question-option {
  display: flex;
  gap: 4px;
  line-height: 1.55;
}

.relation-question-stem {
  font-size: 13px;
  font-weight: 500;
}

.relation-question-number,
.relation-option-label {
  flex: none;
  color: #53657a;
}

.relation-question-options {
  margin-top: 4px;
  padding-left: 2px;
  color: #53657a;
}

.relation-question-option + .relation-question-option {
  margin-top: 2px;
}

.relation-question-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 5px;
  color: #8b98a8;
  font-size: 11px;
  line-height: 1.45;
}

.relation-question-trailing {
  flex: none;
}
</style>
