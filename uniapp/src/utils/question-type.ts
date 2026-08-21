const QUESTION_TYPE_LABELS: Record<string, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  fill_blank: '填空题',
  short_answer: '简答题',
  solution: '解答题',
  essay: '论述题',
  true_false: '判断题',
  computation: '计算题',
  calculation: '计算题',
  proof: '证明题',
  experiment: '实验题',
  reading_comprehension: '阅读理解题',
}

export function resolveQuestionType(
  type: unknown,
  stem = '',
  options: unknown[] = [],
  answer = '',
): string {
  const normalized = String(type || '').trim().toLowerCase()
  if (normalized && normalized !== 'unknown') return normalized

  const normalizedStem = String(stem || '').replace(/\\\\/g, '\\')
  if (/(选填|填空|\\underline|_{2,})/i.test(normalizedStem)) return 'fill_blank'

  if (/(\u5224\u65ad|\u6b63\u786e|\u9519\u8bef|\u5bf9\u9519)/i.test(normalizedStem)) return 'true_false'

  if (Array.isArray(options) && options.length > 0
    || /\\mathrm\s*\{[A-D]\}|(?:^|\n)\s*[A-D][.．、]/i.test(normalizedStem)) {
    const answerLetters = String(answer || '').toUpperCase().match(/[A-D]/g) || []
    return new Set(answerLetters).size > 1 ? 'multiple_choice' : 'single_choice'
  }

  return normalized || 'unknown'
}

export function getQuestionTypeLabel(
  type: unknown,
  stem = '',
  options: unknown[] = [],
  answer = '',
): string {
  const resolved = resolveQuestionType(type, stem, options, answer)
  return QUESTION_TYPE_LABELS[resolved] || '未识别题型'
}
