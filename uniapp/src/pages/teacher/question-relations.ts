import type {
  QuestionRelationCreateData,
  QuestionRelationApiEnvelope,
  QuestionRelationItem,
  QuestionRelationPageData,
  QuestionRelationRemoveData,
} from '@/api/questions'
import type { UUID } from '@/types/uuid'
import { reactive } from 'vue'

export type RelationPage = {
  items: QuestionRelationItem[]
  total: number
  pageNo: number
  pageSize: number
  reason?: string
}

export type RelationApi = {
  relations: (questionId: UUID, params?: { page?: number; page_size?: number }) => Promise<QuestionRelationApiEnvelope<QuestionRelationPageData>>
  relationCandidates: (questionId: UUID, params?: { page?: number; page_size?: number }) => Promise<QuestionRelationApiEnvelope<QuestionRelationPageData>>
  createRelations: (questionId: UUID, questionIds: UUID[]) => Promise<QuestionRelationApiEnvelope<QuestionRelationCreateData>>
  removeRelation: (questionId: UUID, relatedId: UUID) => Promise<QuestionRelationApiEnvelope<QuestionRelationRemoveData>>
}

export type CreateRelationsResult = {
  status: 'success' | 'partial' | 'invalid' | 'failed' | 'cancelled'
  createdCount: number
  existingCount: number
  invalidQuestionIds: UUID[]
  message: string
  warning: string
}

export type RemoveRelationResult = {
  success: boolean
  removed: boolean
  message: string
  warning: string
}

export type RelationState = {
  visible: boolean
  questionId: UUID | null
  tab: 'candidates' | 'linked'
  candidates: QuestionRelationItem[]
  linked: QuestionRelationItem[]
  candidatePage: number
  candidateTotal: number
  candidatePageSize: number
  linkedPage: number
  linkedTotal: number
  linkedPageSize: number
  selectedIds: UUID[]
  loading: boolean
  reason: string
  error: string
  warning: string
}

function isApiResponse(value: unknown): value is QuestionRelationApiEnvelope<unknown> {
  return typeof value === 'object' && value !== null && 'data' in value
}

function responsePayload<T>(response: QuestionRelationApiEnvelope<T>): T {
  let current: unknown = response
  while (isApiResponse(current)) {
    const code = current.code
    if (code !== undefined && code !== 0 && code !== '0') {
      throw new Error(current.message || '关联题操作失败，请稍后重试')
    }
    current = current.data
  }
  return current as T
}

function pageFromResponse(
  response: QuestionRelationApiEnvelope<QuestionRelationPageData>,
  requestedPage: number,
  requestedPageSize: number,
): RelationPage {
  const data = responsePayload(response)
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: Number(data?.total) || 0,
    pageNo: Math.max(1, Number(data?.page_no) || requestedPage),
    pageSize: Math.max(1, Number(data?.page_size) || requestedPageSize),
    reason: typeof data?.reason === 'string' ? data.reason : '',
  }
}

function errorMessage(error: unknown): string {
  if (typeof error === 'object' && error) {
    const data = 'data' in error ? (error as { data?: unknown }).data : undefined
    if (typeof data === 'object' && data && 'message' in data) {
      const message = (data as { message?: unknown }).message
      if (typeof message === 'string' && message) return message
    }
    if ('message' in error) {
      const message = (error as { message?: unknown }).message
      if (typeof message === 'string' && message) return message
    }
  }
  return '关联题操作失败，请稍后重试'
}

function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize))
}

function emptyCreateResult(status: CreateRelationsResult['status'], message: string): CreateRelationsResult {
  return { status, createdCount: 0, existingCount: 0, invalidQuestionIds: [], message, warning: '' }
}

export function createQuestionRelationsController(api: RelationApi) {
  const state = reactive<RelationState>({
    visible: false,
    questionId: null,
    tab: 'candidates',
    candidates: [],
    linked: [],
    candidatePage: 1,
    candidateTotal: 0,
    candidatePageSize: 50,
    linkedPage: 1,
    linkedTotal: 0,
    linkedPageSize: 50,
    selectedIds: [],
    loading: false,
    reason: '',
    error: '',
    warning: '',
  })
  let generation = 0
  let candidateRequestSequence = 0
  let linkedRequestSequence = 0
  let activeRequestCount = 0

  function isCurrent(requestGeneration: number, questionId: UUID): boolean {
    return state.visible && generation === requestGeneration && state.questionId === questionId
  }

  function isCandidateRequestCurrent(requestGeneration: number, questionId: UUID, sequence: number): boolean {
    return isCurrent(requestGeneration, questionId) && candidateRequestSequence === sequence
  }

  function isLinkedRequestCurrent(requestGeneration: number, questionId: UUID, sequence: number): boolean {
    return isCurrent(requestGeneration, questionId) && linkedRequestSequence === sequence
  }

  async function withLoading<T>(requestGeneration: number, questionId: UUID, operation: () => Promise<T>): Promise<T> {
    if (isCurrent(requestGeneration, questionId)) {
      activeRequestCount += 1
      state.loading = true
    }
    try {
      return await operation()
    } finally {
      if (isCurrent(requestGeneration, questionId)) {
        activeRequestCount = Math.max(0, activeRequestCount - 1)
        state.loading = activeRequestCount > 0
      }
    }
  }

  function currentQuestionId(): UUID | null {
    return state.questionId
  }

  async function loadCandidates(page = state.candidatePage, requestGeneration = generation, allowPageFallback = true): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const requestSequence = ++candidateRequestSequence
    let response: QuestionRelationApiEnvelope<QuestionRelationPageData>
    try {
      response = await withLoading(requestGeneration, questionId, () => api.relationCandidates(questionId, { page, page_size: state.candidatePageSize }))
    } catch (error) {
      if (isCandidateRequestCurrent(requestGeneration, questionId, requestSequence)) throw error
      return
    }
    if (!isCandidateRequestCurrent(requestGeneration, questionId, requestSequence)) return
    const data = pageFromResponse(response, page, state.candidatePageSize)
    const lastPage = totalPages(data.total, data.pageSize)
    const normalizedPage = Math.min(data.pageNo, lastPage)
    if (allowPageFallback && data.pageNo !== normalizedPage) {
      state.candidatePage = normalizedPage
      await loadCandidates(normalizedPage, requestGeneration, false)
      return
    }
    if (!isCandidateRequestCurrent(requestGeneration, questionId, requestSequence)) return
    state.candidates = data.items
    state.candidatePage = normalizedPage
    state.candidateTotal = data.total
    state.candidatePageSize = data.pageSize
    state.reason = data.reason || ''
  }

  async function loadLinked(page = state.linkedPage, requestGeneration = generation, allowPageFallback = true): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const requestSequence = ++linkedRequestSequence
    let response: QuestionRelationApiEnvelope<QuestionRelationPageData>
    try {
      response = await withLoading(requestGeneration, questionId, () => api.relations(questionId, { page, page_size: state.linkedPageSize }))
    } catch (error) {
      if (isLinkedRequestCurrent(requestGeneration, questionId, requestSequence)) throw error
      return
    }
    if (!isLinkedRequestCurrent(requestGeneration, questionId, requestSequence)) return
    const data = pageFromResponse(response, page, state.linkedPageSize)
    const lastPage = totalPages(data.total, data.pageSize)
    const normalizedPage = Math.min(data.pageNo, lastPage)
    if (allowPageFallback && data.pageNo !== normalizedPage) {
      state.linkedPage = normalizedPage
      await loadLinked(normalizedPage, requestGeneration, false)
      return
    }
    if (!isLinkedRequestCurrent(requestGeneration, questionId, requestSequence)) return
    state.linked = data.items
    state.linkedPage = normalizedPage
    state.linkedTotal = data.total
    state.linkedPageSize = data.pageSize
  }

  async function refresh(requestGeneration = generation): Promise<void> {
    await Promise.all([
      loadCandidates(state.candidatePage, requestGeneration),
      loadLinked(state.linkedPage, requestGeneration),
    ])
  }

  async function changeCandidatePage(page: number): Promise<void> {
    const requestGeneration = generation
    const questionId = currentQuestionId()
    if (!questionId) return
    try {
      await loadCandidates(Math.max(1, Math.min(totalPages(state.candidateTotal, state.candidatePageSize), page)), requestGeneration)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
    }
  }

  async function changeLinkedPage(page: number): Promise<void> {
    const requestGeneration = generation
    const questionId = currentQuestionId()
    if (!questionId) return
    try {
      await loadLinked(Math.max(1, Math.min(totalPages(state.linkedTotal, state.linkedPageSize), page)), requestGeneration)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
    }
  }

  async function nextCandidatePage(): Promise<void> { await changeCandidatePage(state.candidatePage + 1) }
  async function previousCandidatePage(): Promise<void> { await changeCandidatePage(state.candidatePage - 1) }
  async function nextLinkedPage(): Promise<void> { await changeLinkedPage(state.linkedPage + 1) }
  async function previousLinkedPage(): Promise<void> { await changeLinkedPage(state.linkedPage - 1) }

  async function open(questionId: UUID): Promise<void> {
    generation += 1
    candidateRequestSequence += 1
    linkedRequestSequence += 1
    const requestGeneration = generation
    activeRequestCount = 0
    state.visible = true
    state.questionId = questionId
    state.tab = 'candidates'
    state.candidates = []
    state.linked = []
    state.candidatePage = 1
    state.candidateTotal = 0
    state.candidatePageSize = 50
    state.linkedPage = 1
    state.linkedTotal = 0
    state.linkedPageSize = 50
    state.selectedIds = []
    state.reason = ''
    state.error = ''
    state.warning = ''
    try {
      await refresh(requestGeneration)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
    }
  }

  function close(): void {
    generation += 1
    candidateRequestSequence += 1
    linkedRequestSequence += 1
    activeRequestCount = 0
    state.visible = false
    state.questionId = null
    state.tab = 'candidates'
    state.candidates = []
    state.linked = []
    state.candidatePage = 1
    state.candidateTotal = 0
    state.candidatePageSize = 50
    state.linkedPage = 1
    state.linkedTotal = 0
    state.linkedPageSize = 50
    state.selectedIds = []
    state.reason = ''
    state.error = ''
    state.warning = ''
  }

  function selectTab(tab: RelationState['tab']): void {
    state.tab = tab
    state.error = ''
  }

  function toggleSelection(questionId: UUID): void {
    const index = state.selectedIds.indexOf(questionId)
    if (index >= 0) state.selectedIds.splice(index, 1)
    else state.selectedIds.push(questionId)
  }

  async function createSelected(): Promise<CreateRelationsResult> {
    const questionId = currentQuestionId()
    if (!questionId || state.selectedIds.length === 0) return emptyCreateResult('invalid', '请先选择要关联的题目')
    const requestGeneration = generation
    const submittedIds = [...state.selectedIds]
    state.error = ''
    state.warning = ''

    let data: QuestionRelationCreateData
    try {
      const response = await withLoading(requestGeneration, questionId, () => api.createRelations(questionId, submittedIds))
      if (!isCurrent(requestGeneration, questionId)) return emptyCreateResult('cancelled', '')
      data = responsePayload(response)
    } catch (error) {
      const message = errorMessage(error)
      if (isCurrent(requestGeneration, questionId)) state.error = message
      return emptyCreateResult('failed', message)
    }

    const createdCount = Math.max(0, Number(data.created_count) || 0)
    const existingCount = Math.max(0, Number(data.existing_count) || 0)
    const invalidQuestionIds = Array.isArray(data.invalid_question_ids) ? data.invalid_question_ids.map(String) : []
    const invalidSet = new Set(invalidQuestionIds)
    const successfulIds = submittedIds.filter(id => !invalidSet.has(id))
    const successfulCount = createdCount + existingCount

    if (successfulCount === 0) {
      const message = `未建立关联：${invalidQuestionIds.length || submittedIds.length} 题无效`
      return { status: 'invalid', createdCount, existingCount, invalidQuestionIds, message, warning: '' }
    }

    state.selectedIds = state.selectedIds.filter(id => !successfulIds.includes(id))
    const successfulSet = new Set(successfulIds)
    const removedFromCurrentPage = state.candidates.filter(item => successfulSet.has(item.id)).length
    state.candidates = state.candidates.filter(item => !successfulSet.has(item.id))
    state.candidateTotal = Math.max(0, state.candidateTotal - removedFromCurrentPage)
    state.tab = 'linked'

    const status: CreateRelationsResult['status'] = invalidQuestionIds.length ? 'partial' : 'success'
    const message = status === 'partial'
      ? `部分关联完成：成功或已存在 ${successfulCount} 题，${invalidQuestionIds.length} 题无效`
      : `关联完成：新建 ${createdCount} 题，已有关联 ${existingCount} 题`
    const result: CreateRelationsResult = { status, createdCount, existingCount, invalidQuestionIds, message, warning: '' }

    try {
      await refresh(requestGeneration)
    } catch {
      if (isCurrent(requestGeneration, questionId)) {
        result.warning = '操作已成功，列表刷新失败，请重试'
        state.warning = result.warning
      }
    }
    return result
  }

  async function remove(relatedId: UUID): Promise<RemoveRelationResult> {
    const questionId = currentQuestionId()
    if (!questionId) return { success: false, removed: false, message: '', warning: '' }
    const requestGeneration = generation
    state.error = ''
    state.warning = ''

    let data: QuestionRelationRemoveData
    try {
      const response = await withLoading(requestGeneration, questionId, () => api.removeRelation(questionId, relatedId))
      if (!isCurrent(requestGeneration, questionId)) return { success: false, removed: false, message: '', warning: '' }
      data = responsePayload(response)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
      throw error
    }

    const existedLocally = state.linked.some(item => item.id === relatedId)
    state.linked = state.linked.filter(item => item.id !== relatedId)
    state.selectedIds = state.selectedIds.filter(id => id !== relatedId)
    if (existedLocally) state.linkedTotal = Math.max(0, state.linkedTotal - 1)
    state.linkedPage = Math.min(state.linkedPage, totalPages(state.linkedTotal, state.linkedPageSize))

    const result: RemoveRelationResult = {
      success: true,
      removed: data.removed !== false,
      message: '已解除关联',
      warning: '',
    }
    try {
      await refresh(requestGeneration)
    } catch {
      if (isCurrent(requestGeneration, questionId)) {
        result.warning = '操作已成功，列表刷新失败，请重试'
        state.warning = result.warning
      }
    }
    return result
  }

  return {
    state,
    open,
    close,
    selectTab,
    toggleSelection,
    loadCandidates,
    loadLinked,
    changeCandidatePage,
    changeLinkedPage,
    nextCandidatePage,
    previousCandidatePage,
    nextLinkedPage,
    previousLinkedPage,
    createSelected,
    remove,
  }
}
