const QUESTION_PREFIX_RE = /^第\s*([^：:]+?)\s*题\s*[：:]\s*/
const QUESTION_JSON_RE = /["']question_no["']\s*:\s*["']?([^,"'}\s]+)/i

const ERROR_LABELS = {
  timeout: 'AI响应超时',
  format: 'AI返回格式错误',
  config: 'AI配置错误',
  asset: '题目资源处理失败',
  unknown: '题目处理失败',
} as const

function errorLabel(message: string): string {
  if (/timed out|timeout|超时/i.test(message)) return ERROR_LABELS.timeout
  if (/not valid json|invalid json|json|schema|格式错误|response content is missing|结构化/i.test(message)) {
    return ERROR_LABELS.format
  }
  if (/credential|api[_ -]?key|配置/i.test(message)) return ERROR_LABELS.config
  if (/asset|image|图片|资源/i.test(message)) return ERROR_LABELS.asset
  return ERROR_LABELS.unknown
}

/** Convert backend/import-history diagnostics into short, safe popup text. */
export function formatDocumentImportError(value: unknown): string {
  const message = String(value ?? '').trim()
  if (!message) return ''

  const prefixedQuestion = message.match(QUESTION_PREFIX_RE)
  const questionNo = prefixedQuestion?.[1]?.trim() || message.match(QUESTION_JSON_RE)?.[1]?.trim()
  const label = errorLabel(message)
  return questionNo ? `第${questionNo}题：${label}` : label
}

export function formatDocumentImportErrors(values: unknown): string[] {
  return Array.from(new Set((Array.isArray(values) ? values : [])
    .map(formatDocumentImportError)
    .filter(Boolean)))
}
