export interface CourseQuestionListInput {
  treeNodeId: string
  page: number
  pageSize: number
  questionType?: string
  difficulty?: string
  knowledgePointId?: string
  tag?: string
  keyword?: string
}

export interface CourseQuestionListQuery {
  tree_node_id: string
  page: number
  page_size: number
  question_type?: string | null
  difficulty?: string | null
  knowledge_point_id?: string | null
  tag?: string | null
  keyword?: string | null
}

export interface CourseQuestionListResult<T = unknown> {
  items: T[]
  total: number
  pageNo: number
  pageSize: number
}

export function serializeCourseQuestionQuery(query: CourseQuestionListQuery): URLSearchParams {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value == null || (typeof value === 'string' && !value.trim())) return
    params.set(key, String(value))
  })
  return params
}

export function buildCourseQuestionQuery(input: CourseQuestionListInput): CourseQuestionListQuery | null {
  if (!input.treeNodeId) return null

  const query: CourseQuestionListQuery = {
    tree_node_id: input.treeNodeId,
    page: input.page,
    page_size: input.pageSize,
  }
  if (input.questionType) query.question_type = input.questionType
  if (input.difficulty) query.difficulty = input.difficulty
  if (input.knowledgePointId) query.knowledge_point_id = input.knowledgePointId
  if (input.tag?.trim()) query.tag = input.tag.trim()
  if (input.keyword?.trim()) query.keyword = input.keyword.trim()
  return query
}

export function normalizeCourseQuestionList<T = unknown>(response: unknown): CourseQuestionListResult<T> {
  const data = (response as { data?: { items?: unknown; total?: unknown; page_no?: unknown; page_size?: unknown } } | null)?.data
  return {
    items: Array.isArray(data?.items) ? data.items as T[] : [],
    total: Number(data?.total || 0),
    pageNo: Number(data?.page_no || 1),
    pageSize: Number(data?.page_size || 20),
  }
}

export async function loadCourseQuestionList<T = unknown>(
  input: CourseQuestionListInput,
  fetchList: (query: CourseQuestionListQuery) => Promise<unknown>,
): Promise<CourseQuestionListResult<T>> {
  const query = buildCourseQuestionQuery(input)
  if (!query) return normalizeCourseQuestionList<T>(null)
  return normalizeCourseQuestionList<T>(await fetchList(query))
}
