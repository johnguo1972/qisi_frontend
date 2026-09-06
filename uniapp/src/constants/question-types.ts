export const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '\u5355\u9009\u9898' },
  { value: 'multiple_choice', label: '\u591a\u9009\u9898' },
  { value: 'fill_blank', label: '\u586b\u7a7a\u9898' },
  { value: 'true_false', label: '\u5224\u65ad\u9898' },
  { value: 'short_answer', label: '\u7b80\u7b54\u9898' },
  { value: 'question_answer', label: '\u95ee\u7b54\u9898' },
  { value: 'proof', label: '\u8bc1\u660e\u9898' },
  { value: 'experiment', label: '\u5b9e\u9a8c\u9898' },
  { value: 'computation', label: '\u8ba1\u7b97\u9898' },
  { value: 'drawing', label: '\u4f5c\u56fe\u9898' },
  { value: 'essay', label: '\u4f5c\u6587\u9898' },
] as const

const QUESTION_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  QUESTION_TYPE_OPTIONS.map(item => [item.value, item.label]),
)

export function getQuestionTypeLabel(type: unknown): string {
  const normalized = String(type || '').trim().toLowerCase()
  return QUESTION_TYPE_LABELS[normalized] || '\u672a\u8bc6\u522b\u9898\u578b'
}
