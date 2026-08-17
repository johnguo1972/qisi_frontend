const STATUS_LABELS: Record<string, string> = {
  locked: '未开始',
  not_started: '未开始',
  not_reviewed: '待复习',
  reviewing: '复习中',
  in_progress: '进行中',
  running: '进行中',
  completed: '已完成',
  passed: '已通过',
  mastered: '已掌握',
  weak: '需加强',
  rejected: '已拒绝',
  pending: '待确认',
  active: '已生效',
  removed: '已解除',
}

const MASTERY_LABELS: Record<string, string> = {
  mastered: '已掌握',
  reviewing: '复习中',
  weak: '需加强',
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

/** Format backend ISO timestamps consistently for H5, App and MP. */
export function formatDateTime(value: string | number | Date | null | undefined, fallback = '暂无时间') {
  if (!value) return fallback
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function statusLabel(value: string | null | undefined, fallback = '未知状态') {
  if (!value) return fallback
  return STATUS_LABELS[value] || fallback
}

export function masteryLabel(value: string | null | undefined) {
  if (!value) return '待学习'
  return MASTERY_LABELS[value] || statusLabel(value, '待学习')
}
