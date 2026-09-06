import { getQuestionTypeLabel as getCanonicalQuestionTypeLabel } from '@/constants/question-types'

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
  return getCanonicalQuestionTypeLabel(resolved)
}
