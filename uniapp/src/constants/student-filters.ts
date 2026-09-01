export interface StudentSubjectOption {
  code: string
  name: string
}

// 学生首页和错题页共用同一份科目字典，避免两个页面出现选项不一致。
export const STUDENT_SUBJECT_OPTIONS: StudentSubjectOption[] = [
  { code: '', name: '全部科目' },
  { code: 'chinese', name: '语文' },
  { code: 'math', name: '数学' },
  { code: 'english', name: '英语' },
  { code: 'physics', name: '物理' },
  { code: 'chemistry', name: '化学' },
  { code: 'biology', name: '生物' },
  { code: 'geography', name: '地理' },
  { code: 'history', name: '历史' },
]
