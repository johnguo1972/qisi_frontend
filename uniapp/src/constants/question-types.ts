export const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选题' },
  { value: 'multiple_choice', label: '多选题' },
  { value: 'fill_blank', label: '填空题' },
  { value: 'true_false', label: '判断题' },
  { value: 'short_answer', label: '简答题' },
  { value: 'question_answer', label: '问答题' },
  { value: 'proof', label: '证明题' },
  { value: 'experiment', label: '实验题' },
  { value: 'computation', label: '计算题' },
  { value: 'drawing', label: '作图题' },
  { value: 'essay', label: '作文题' },
] as const

const QUESTION_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  QUESTION_TYPE_OPTIONS.map(item => [item.value, item.label]),
)

export function getQuestionTypeLabel(type: unknown): string {
  const normalized = String(type || '').trim().toLowerCase()
  return QUESTION_TYPE_LABELS[normalized] || '未识别题型'
}
