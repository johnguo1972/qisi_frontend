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
  tree_node_id?: string
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

export function buildCourseQuestionQuery(input: CourseQuestionListInput): CourseQuestionListQuery {
  const query: CourseQuestionListQuery = {
    page: input.page,
    page_size: input.pageSize,
  }
  if (input.treeNodeId) query.tree_node_id = input.treeNodeId
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
  return normalizeCourseQuestionList<T>(await fetchList(query))
}

export async function submitCourseBatchAi(input: {
  selectedIds: string[]
  batchAi: (ids: string[]) => Promise<unknown>
  poll?: (taskId: string) => Promise<BackgroundAiTerminalStatus>
  refresh?: () => Promise<unknown> | unknown
  onTerminal?: () => void
}): Promise<{ submitted: number; failed: number; taskIds: string[]; noNewTask?: boolean }> {
  if (!input.selectedIds.length) return { submitted: 0, failed: 0, taskIds: [] }
  const response = await input.batchAi([...input.selectedIds])
  const taskId = extractBackgroundTaskId(response)
  if (!taskId) {
    const data = (response as { data?: { accepted?: unknown; deduplicated?: unknown } } | null)?.data
    const accepted = Number(data?.accepted)
    const deduplicated = Array.isArray(data?.deduplicated) ? data.deduplicated.length : 0
    if (accepted === 0 && deduplicated > 0) return { submitted: 0, failed: 0, taskIds: [], noNewTask: true }
    return { submitted: 0, failed: input.selectedIds.length, taskIds: [] }
  }
  if (input.poll) {
    void input.poll(taskId).then(status => {
      if (isRefreshableAiStatus(status)) void input.refresh?.()
    }).catch(() => undefined).finally(input.onTerminal)
  }
  return { submitted: input.selectedIds.length, failed: 0, taskIds: [taskId] }
}

export async function handleDisabledVariantAction(_input: {
  generate: () => unknown
  batchGenerate: () => unknown
}): Promise<void> {
  // Course variant actions are intentionally unavailable in this view.
}

export type BackgroundAiTerminalStatus = 'complete' | 'partial' | 'failed' | 'skipped' | 'cancelled'

export function extractBackgroundTaskId(response: unknown): string | null {
  const root = response as { task_id?: unknown; job_id?: unknown; data?: { task_id?: unknown; job_id?: unknown } } | null
  const value = root?.data?.task_id || root?.data?.job_id || root?.task_id || root?.job_id
  return value == null || value === '' ? null : String(value)
}

export function normalizeBackgroundAiStatus(status: unknown): BackgroundAiTerminalStatus | null {
  if (status === 'completed') return 'complete'
  return ['complete', 'partial', 'failed', 'skipped', 'cancelled'].includes(String(status))
    ? String(status) as BackgroundAiTerminalStatus
    : null
}

export function isRefreshableAiStatus(status: BackgroundAiTerminalStatus | null): boolean {
  return status === 'complete' || status === 'partial'
}

export async function submitCourseAiTasks(input: {
  selectedIds: string[]
  submit: (questionId: string) => Promise<unknown>
  poll: (taskId: string) => Promise<BackgroundAiTerminalStatus>
  refresh: () => Promise<unknown> | unknown
  onTerminal?: () => void
}): Promise<{ submitted: number; failed: number; taskIds: string[] }> {
  const responses = await Promise.all(input.selectedIds.map(async questionId => {
    try { return await input.submit(questionId) } catch { return null }
  }))
  const taskIds = responses.map(extractBackgroundTaskId).filter((id): id is string => Boolean(id))
  if (taskIds.length) {
    void Promise.all(taskIds.map(taskId => input.poll(taskId).catch(() => 'failed' as BackgroundAiTerminalStatus)))
      .then(statuses => {
        if (statuses.some(isRefreshableAiStatus)) void input.refresh()
      })
      .finally(input.onTerminal)
  }
  return { submitted: taskIds.length, failed: input.selectedIds.length - taskIds.length, taskIds }
}

export type CourseQuestionListControllerState<T> = {
  treeNodeId: string
  page: number
  pageSize: number
  items: T[]
  total: number
  loading: boolean
  selectedIds: string[]
}

export function createCourseQuestionListController<T = unknown>(
  fetchList: (query: CourseQuestionListQuery) => Promise<unknown>,
) {
  const state: CourseQuestionListControllerState<T> = {
    treeNodeId: '', page: 1, pageSize: 20, items: [], total: 0, loading: false, selectedIds: [],
  }
  let requestSequence = 0

  function resetForNode(treeNodeId: string, pageSize = state.pageSize) {
    requestSequence += 1
    state.treeNodeId = treeNodeId
    state.page = 1
    state.pageSize = pageSize
    state.items = []
    state.total = 0
    state.selectedIds = []
    state.loading = true
  }

  async function load(input: Omit<CourseQuestionListInput, 'treeNodeId' | 'page' | 'pageSize'> = {}, allowPageCorrection = true) {
    const sequence = ++requestSequence
    state.loading = true
    let result: CourseQuestionListResult<T>
    try {
      result = await loadCourseQuestionList<T>({
        treeNodeId: state.treeNodeId,
        page: state.page,
        pageSize: state.pageSize,
        ...input,
      }, fetchList)
    } catch (error) {
      if (sequence === requestSequence) state.loading = false
      if (sequence !== requestSequence) return { applied: false, result: normalizeCourseQuestionList<T>(null) }
      throw error
    }
    if (sequence !== requestSequence) return { applied: false, result }
    const lastPage = Math.max(1, Math.ceil(result.total / result.pageSize))
    const correctedPage = Math.min(lastPage, Math.max(1, result.pageNo))
    if (allowPageCorrection && correctedPage !== result.pageNo) {
      state.page = correctedPage
      return load(input, false)
    }
    state.items = result.items
    state.total = result.total
    state.page = correctedPage
    state.pageSize = result.pageSize
    state.selectedIds = state.selectedIds.filter(id => result.items.some((item: any) => String(item?.id || item?.question_id) === id))
    state.loading = false
    return { applied: true, result }
  }

  async function selectNode(treeNodeId: string, input: Omit<CourseQuestionListInput, 'treeNodeId' | 'page' | 'pageSize'> & { pageSize?: number } = {}) {
    resetForNode(treeNodeId, input.pageSize || state.pageSize)
    const { pageSize: _pageSize, ...filters } = input
    return load(filters)
  }

  function setPage(page: number) { state.page = Math.max(1, page) }
  function canMutateCurrentNode() { return !state.loading && state.selectedIds.length > 0 }

  return { state, load, selectNode, setPage, resetForNode, canMutateCurrentNode }
}

export function flattenKnowledgePointOptions(tree: unknown): Array<{ id: string; name: string }> {
  const result: Array<{ id: string; name: string }> = []
  const seen = new Set<string>()
  const visit = (node: unknown) => {
    if (Array.isArray(node)) return node.forEach(visit)
    if (!node || typeof node !== 'object') return
    const value = node as { id?: unknown; label?: unknown; name?: unknown; children?: unknown; is_unclassified?: boolean }
    if (Array.isArray(value.children)) return value.children.forEach(visit)
    const id = value.id == null ? '' : String(value.id)
    const name = typeof value.label === 'string' ? value.label : typeof value.name === 'string' ? value.name : ''
    if (!id || !name || value.is_unclassified || id.startsWith('grade_') || id.startsWith('term_') || seen.has(id)) return
    seen.add(id)
    result.push({ id, name })
  }
  visit(tree)
  return result
}

export async function loadCourseKnowledgePointOptions(
  subject: string,
  fetchTree: (subject: string) => Promise<unknown>,
): Promise<Array<{ id: string; name: string }>> {
  const response = await fetchTree(subject)
  const data = (response as { data?: unknown } | null)?.data || response || []
  return flattenKnowledgePointOptions(data)
}
