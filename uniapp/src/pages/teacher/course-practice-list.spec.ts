import { describe, expect, it, vi } from 'vitest'
import {
  buildCourseQuestionQuery,
  loadCourseQuestionList,
  normalizeCourseQuestionList,
  serializeCourseQuestionQuery,
} from './course-practice-list'

describe('course practice question list query state', () => {
  it('serializes only non-empty filters with the selected node', () => {
    expect(buildCourseQuestionQuery({
      treeNodeId: 'node-1', page: 2, pageSize: 50,
      questionType: 'single_choice', difficulty: '3.2',
      knowledgePointId: '9001', tag: 'tag-value', keyword: 'speed change',
    })).toEqual({
      tree_node_id: 'node-1', page: 2, page_size: 50,
      question_type: 'single_choice', difficulty: '3.2',
      knowledge_point_id: '9001', tag: 'tag-value', keyword: 'speed change',
    })
  })

  it('does not build a request when no course node is selected', () => {
    expect(buildCourseQuestionQuery({ treeNodeId: '', page: 1, pageSize: 20 })).toBeNull()
  })

  it('does not serialize undefined, null, or whitespace-only optional filters', () => {
    const query = serializeCourseQuestionQuery({
      tree_node_id: 'node-1', page: 1, page_size: 20,
      question_type: undefined, difficulty: null, knowledge_point_id: '  ',
      tag: '', keyword: '  ',
    })
    expect(query.toString()).toBe('tree_node_id=node-1&page=1&page_size=20')
  })

  it('does not call the fetch callback when no node is selected', async () => {
    let calls = 0
    const result = await loadCourseQuestionList(
      { treeNodeId: '', page: 1, pageSize: 20 },
      async () => { calls += 1; return { data: { items: [], total: 0, page_no: 1, page_size: 20 } } },
    )
    expect(calls).toBe(0)
    expect(result.items).toEqual([])
  })

  it('normalizes the paginated response envelope', () => {
    expect(normalizeCourseQuestionList({
      data: { items: [{ question_id: 'q-1' }], total: 1, page_no: 2, page_size: 50 },
    })).toEqual({ items: [{ question_id: 'q-1' }], total: 1, pageNo: 2, pageSize: 50 })
  })

  it('does not treat a legacy array response as a question list', () => {
    expect(normalizeCourseQuestionList([{ question_id: 'legacy' }])).toEqual({
      items: [], total: 0, pageNo: 1, pageSize: 20,
    })
  })

  it('submits selected course questions to the background batch AI API', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    expect(helpers.submitCourseBatchAi).toBeTypeOf('function')

    const batchAi = vi.fn().mockResolvedValue({ data: { job_id: 'job-1' } })
    await (helpers.submitCourseBatchAi as (input: {
      selectedIds: string[]
      batchAi: (ids: string[]) => Promise<unknown>
    }) => Promise<unknown>)({ selectedIds: ['q-1', 'q-2'], batchAi })

    expect(batchAi).toHaveBeenCalledOnce()
    expect(batchAi).toHaveBeenCalledWith(['q-1', 'q-2'])
  })

  it('does not invoke variant APIs for an explicitly disabled course action', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    expect(helpers.handleDisabledVariantAction).toBeTypeOf('function')

    const generate = vi.fn()
    const batchGenerate = vi.fn()
    await (helpers.handleDisabledVariantAction as (input: {
      generate: () => unknown
      batchGenerate: () => unknown
    }) => Promise<void>)({ generate, batchGenerate })

    expect(generate).not.toHaveBeenCalled()
    expect(batchGenerate).not.toHaveBeenCalled()
  })

  it('keeps the newest selected node result when the previous request resolves last', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    expect(helpers.createCourseQuestionListController).toBeTypeOf('function')

    let resolveFirst!: (value: unknown) => void
    let resolveSecond!: (value: unknown) => void
    const fetchList = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve }))
    const controller = (helpers.createCourseQuestionListController as (fetch: typeof fetchList) => any)(fetchList)

    const first = controller.selectNode('node-1', { pageSize: 20 })
    controller.state.selectedIds = ['old-question']
    const second = controller.selectNode('node-2', { pageSize: 20 })
    expect(controller.state).toMatchObject({ treeNodeId: 'node-2', page: 1, items: [], selectedIds: [] })

    resolveSecond({ data: { items: [{ question_id: 'new-question' }], total: 1, page_no: 1, page_size: 20 } })
    await second
    resolveFirst({ data: { items: [{ question_id: 'old-question' }], total: 1, page_no: 1, page_size: 20 } })
    await first

    expect(controller.state.items).toEqual([{ question_id: 'new-question' }])
    expect(controller.state.selectedIds).toEqual([])
    expect(fetchList.mock.calls.map(([query]) => query.tree_node_id)).toEqual(['node-1', 'node-2'])
  })

  it('flattens only selectable knowledge-point leaves with their real IDs', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    expect(helpers.flattenKnowledgePointOptions).toBeTypeOf('function')

    const options = (helpers.flattenKnowledgePointOptions as (tree: unknown) => Array<{ id: string; name: string }>)([
      { id: 'grade_1', label: '一年级', children: [{ id: 'term_1', label: '上学期', children: [{ id: 21, label: '整数' }, { id: -1, label: '未分类', is_unclassified: true }] }] },
    ])

    expect(options).toEqual([{ id: '21', name: '整数' }])
  })

  it('retries the corrected last page when a response reports an out-of-range page', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    const fetchList = vi.fn()
      .mockResolvedValueOnce({ data: { items: [], total: 1, page_no: 3, page_size: 20 } })
      .mockResolvedValueOnce({ data: { items: [{ question_id: 'q-1' }], total: 1, page_no: 1, page_size: 20 } })
    const controller = (helpers.createCourseQuestionListController as (fetch: typeof fetchList) => any)(fetchList)
    controller.state.treeNodeId = 'node-1'
    controller.state.page = 3

    await controller.load()

    expect(fetchList.mock.calls.map(([query]) => query.page)).toEqual([3, 1])
    expect(controller.state.page).toBe(1)
  })

  it('marks current-node mutations unavailable while a list refresh is in flight', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    let resolve!: (value: unknown) => void
    const controller = (helpers.createCourseQuestionListController as (fetch: any) => any)(
      () => new Promise(next => { resolve = next }),
    )
    controller.state.treeNodeId = 'node-1'
    controller.state.selectedIds = ['q-1']

    const loading = controller.load()
    expect(controller.canMutateCurrentNode()).toBe(false)
    resolve({ data: { items: [{ question_id: 'q-1' }], total: 1, page_no: 1, page_size: 20 } })
    await loading
    controller.state.selectedIds = ['q-1']
    expect(controller.canMutateCurrentNode()).toBe(true)
  })

  it('polls submitted batch and probe background tasks then refreshes once for terminal work', async () => {
    const helpers = await import('./course-practice-list') as Record<string, unknown>
    expect(helpers.submitCourseBatchAi).toBeTypeOf('function')
    expect(helpers.submitCourseAiTasks).toBeTypeOf('function')

    const refresh = vi.fn()
    const poll = vi.fn().mockResolvedValue('complete')
    await (helpers.submitCourseBatchAi as (input: any) => Promise<unknown>)({
      selectedIds: ['q-1'], batchAi: vi.fn().mockResolvedValue({ data: { job_id: 'job-1' } }), poll, refresh,
    })
    await (helpers.submitCourseAiTasks as (input: any) => Promise<unknown>)({
      selectedIds: ['q-1', 'q-2'],
      submit: vi.fn()
        .mockResolvedValueOnce({ data: { task_id: 'task-1' } })
        .mockRejectedValueOnce(new Error('network')),
      poll: vi.fn().mockResolvedValue('partial'),
      refresh,
    })

    expect(poll).toHaveBeenCalledWith('job-1')
    expect(refresh).toHaveBeenCalledTimes(2)
  })
})
