export type MissionQuestionFilterInput = {
  page: number
  pageSize: number
  subject: string
  knowledgePointIds?: Array<string | number>
  difficulties?: number[]
  stages?: string[]
  questionType?: string
  keyword?: string
  questionUuid?: string
  tag?: string
  errorRateMin?: number | null
  errorRateMax?: number | null
}

export function buildMissionQuestionFilterParams(input: MissionQuestionFilterInput) {
  const params: Record<string, string | number> = {
    page: input.page,
    page_size: input.pageSize,
    subject: input.subject,
  }
  if (input.knowledgePointIds?.length) params.knowledge_point_id = input.knowledgePointIds.join(',')
  if (input.difficulties?.length) params.difficulty = input.difficulties.join(',')
  if (input.stages?.length) params.stages = input.stages.join(',')
  if (input.questionType?.trim()) params.question_type = input.questionType.trim()
  if (input.keyword?.trim()) params.keyword = input.keyword.trim()
  if (input.questionUuid?.trim()) params.uuid = input.questionUuid.trim()
  if (input.tag?.trim()) params.tag = input.tag.trim()
  if (typeof input.errorRateMin === 'number' && Number.isFinite(input.errorRateMin)) {
    params.error_rate_min = input.errorRateMin
  }
  if (typeof input.errorRateMax === 'number' && Number.isFinite(input.errorRateMax)) {
    params.error_rate_max = input.errorRateMax
  }
  return params
}
