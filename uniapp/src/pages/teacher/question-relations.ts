import type { QuestionRelationItem } from '@/api/questions'
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
  relations: (questionId: UUID, params?: { page?: number; page_size?: number }) => Promise<unknown>
  relationCandidates: (questionId: UUID, params?: { page?: number; page_size?: number }) => Promise<unknown>
  createRelations: (questionId: UUID, questionIds: UUID[]) => Promise<unknown>
  removeRelation: (questionId: UUID, relatedId: UUID) => Promise<unknown>
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
}

function responseData(response: any): any {
  const data = response?.data
  return data?.data ?? data ?? {}
}

function pageFromResponse(response: unknown, requestedPage: number, requestedPageSize: number): RelationPage {
  const data = responseData(response)
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
    const data = (error as any).data
    if (typeof data?.message === 'string' && data.message) return data.message
    if (typeof (error as any).message === 'string' && (error as any).message) return (error as any).message
  }
  return '关联题操作失败，请稍后重试'
}

function ensureRequestSucceeded(response: unknown): unknown {
  const code = (response as any)?.code
  if (code !== undefined && code !== 0 && code !== '0') {
    throw new Error((response as any)?.message || '关联题操作失败，请稍后重试')
  }
  return response
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
  })
  let generation = 0
  let activeRequestCount = 0

  function isCurrent(requestGeneration: number, questionId: UUID): boolean {
    return state.visible && generation === requestGeneration && state.questionId === questionId
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
    const response = await withLoading(requestGeneration, questionId, () => api.relationCandidates(questionId, { page, page_size: state.candidatePageSize }))
    if (!isCurrent(requestGeneration, questionId)) return
    const data = pageFromResponse(ensureRequestSucceeded(response), page, state.candidatePageSize)
    const lastPage = totalPages(data.total, data.pageSize)
    const normalizedPage = Math.min(data.pageNo, lastPage)
    if (allowPageFallback && data.pageNo !== normalizedPage) {
      state.candidatePage = normalizedPage
      await loadCandidates(normalizedPage, requestGeneration, false)
      return
    }
    state.candidates = data.items
    state.candidatePage = normalizedPage
    state.candidateTotal = data.total
    state.candidatePageSize = data.pageSize
    state.reason = data.reason || ''
  }

  async function loadLinked(page = state.linkedPage, requestGeneration = generation, allowPageFallback = true): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const response = await withLoading(requestGeneration, questionId, () => api.relations(questionId, { page, page_size: state.linkedPageSize }))
    if (!isCurrent(requestGeneration, questionId)) return
    const data = pageFromResponse(ensureRequestSucceeded(response), page, state.linkedPageSize)
    const lastPage = totalPages(data.total, data.pageSize)
    const normalizedPage = Math.min(data.pageNo, lastPage)
    if (allowPageFallback && data.pageNo !== normalizedPage) {
      state.linkedPage = normalizedPage
      await loadLinked(normalizedPage, requestGeneration, false)
      return
    }
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

  function totalPages(total: number, pageSize: number): number {
    return Math.max(1, Math.ceil(total / pageSize))
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
    try {
      await refresh(requestGeneration)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
    }
  }

  function close(): void {
    generation += 1
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

  async function createSelected(): Promise<boolean> {
    const questionId = currentQuestionId()
    if (!questionId || state.selectedIds.length === 0) return false
    const requestGeneration = generation
    state.error = ''
    try {
      const response = await withLoading(requestGeneration, questionId, () => api.createRelations(questionId, [...state.selectedIds]))
      if (!isCurrent(requestGeneration, questionId)) return false
      ensureRequestSucceeded(response)
      state.selectedIds = []
      await refresh(requestGeneration)
      if (isCurrent(requestGeneration, questionId)) {
        state.tab = 'linked'
        return true
      }
      return false
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
      return false
    }
  }

  async function remove(relatedId: UUID): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const requestGeneration = generation
    state.error = ''
    try {
      const response = await withLoading(requestGeneration, questionId, () => api.removeRelation(questionId, relatedId))
      if (!isCurrent(requestGeneration, questionId)) return
      ensureRequestSucceeded(response)
      await refresh(requestGeneration)
    } catch (error) {
      if (isCurrent(requestGeneration, questionId)) state.error = errorMessage(error)
      throw error
    }
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
