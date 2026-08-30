import type { QuestionRelationItem } from '@/api/questions'
import type { UUID } from '@/types/uuid'
import { reactive } from 'vue'

export type RelationPage = {
  items: QuestionRelationItem[]
  total: number
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
  selectedIds: UUID[]
  loading: boolean
  reason: string
  error: string
}

function responseData(response: any): any {
  const data = response?.data
  return data?.data ?? data ?? {}
}

function pageFromResponse(response: unknown): RelationPage {
  const data = responseData(response)
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: Number(data?.total) || 0,
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
    selectedIds: [],
    loading: false,
    reason: '',
    error: '',
  })
  let pendingRequests = 0

  async function withLoading<T>(operation: () => Promise<T>): Promise<T> {
    pendingRequests += 1
    state.loading = true
    try {
      return await operation()
    } finally {
      pendingRequests -= 1
      state.loading = pendingRequests > 0
    }
  }

  function currentQuestionId(): UUID | null {
    return state.questionId
  }

  async function loadCandidates(): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const page = ensureRequestSucceeded(await withLoading(() => api.relationCandidates(questionId, { page: 1, page_size: 50 })))
    const data = pageFromResponse(page)
    state.candidates = data.items
    state.reason = data.reason || ''
  }

  async function loadLinked(): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    const page = ensureRequestSucceeded(await withLoading(() => api.relations(questionId, { page: 1, page_size: 50 })))
    state.linked = pageFromResponse(page).items
  }

  async function refresh(): Promise<void> {
    await Promise.all([loadCandidates(), loadLinked()])
  }

  async function open(questionId: UUID): Promise<void> {
    state.visible = true
    state.questionId = questionId
    state.tab = 'candidates'
    state.candidates = []
    state.linked = []
    state.selectedIds = []
    state.reason = ''
    state.error = ''
    try {
      await refresh()
    } catch (error) {
      state.error = errorMessage(error)
    }
  }

  function close(): void {
    state.visible = false
    state.questionId = null
    state.tab = 'candidates'
    state.candidates = []
    state.linked = []
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
    state.error = ''
    try {
      ensureRequestSucceeded(await withLoading(() => api.createRelations(questionId, [...state.selectedIds])))
      state.selectedIds = []
      await refresh()
      state.tab = 'linked'
      return true
    } catch (error) {
      state.error = errorMessage(error)
      return false
    }
  }

  async function remove(relatedId: UUID): Promise<void> {
    const questionId = currentQuestionId()
    if (!questionId) return
    state.error = ''
    try {
      ensureRequestSucceeded(await withLoading(() => api.removeRelation(questionId, relatedId)))
      await refresh()
    } catch (error) {
      state.error = errorMessage(error)
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
    createSelected,
    remove,
  }
}
