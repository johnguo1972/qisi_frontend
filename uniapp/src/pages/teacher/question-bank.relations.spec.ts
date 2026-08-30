import { describe, expect, it } from 'vitest'
import { createQuestionRelationsController, type RelationApi } from './question-relations'

const candidate = {
  id: 'candidate-1',
  question_no: '2',
  stem_preview: '候选题题干',
  difficulty: 3.2,
  knowledge_points_display: [{ id: 'kp-1', name: '分子动理论' }],
  common_knowledge_point_names: ['分子动理论'],
}

const linked = {
  id: 'linked-1',
  question_no: '3',
  stem_preview: '已关联题题干',
  difficulty: 3.1,
  knowledge_points_display: [{ id: 'kp-1', name: '分子动理论' }],
}

function page(items: typeof candidate[], pageNo = 1, pageSize = 50, total = items.length) {
  return { data: { items, total, page_no: pageNo, page_size: pageSize, reason: '' } }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
}

describe('题库关联题状态', () => {
  it('建立关联后清空选择、刷新两页并切换到已关联题', async () => {
    let candidateItems = [candidate]
    let linkedItems: typeof candidate[] = []
    const calls: string[] = []
    const api: RelationApi = {
      relationCandidates: async () => page(candidateItems),
      relations: async () => page(linkedItems),
      createRelations: async (_questionId, questionIds) => {
        calls.push(questionIds.join(','))
        candidateItems = []
        linkedItems = [candidate]
        return { data: { created_count: 1, existing_count: 0, invalid_question_ids: [] } }
      },
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)

    await controller.open('origin-1')
    controller.toggleSelection('candidate-1')
    await controller.createSelected()

    expect(calls).toEqual(['candidate-1'])
    expect(controller.state.selectedIds).toEqual([])
    expect(controller.state.tab).toBe('linked')
    expect(controller.state.candidates).toEqual([])
    expect(controller.state.linked).toEqual([candidate])
  })

  it('解除关联失败时保留已关联题，成功后重新加载候选和已关联题', async () => {
    let shouldFail = true
    let candidateItems: typeof candidate[] = []
    let linkedItems = [linked]
    const api: RelationApi = {
      relationCandidates: async () => page(candidateItems),
      relations: async () => page(linkedItems),
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => {
        if (shouldFail) throw new Error('网络异常')
        linkedItems = []
        candidateItems = [linked]
        return { data: { removed: true } }
      },
    }
    const controller = createQuestionRelationsController(api)

    await controller.open('origin-1')
    await expect(controller.remove('linked-1')).rejects.toThrow('网络异常')
    expect(controller.state.linked).toEqual([linked])

    shouldFail = false
    await controller.remove('linked-1')
    expect(controller.state.linked).toEqual([])
    expect(controller.state.candidates).toEqual([linked])
  })

  it('接口返回业务错误时保留选择并展示错误，而不是误报关联成功', async () => {
    const api: RelationApi = {
      relationCandidates: async () => page([candidate]),
      relations: async () => page([]),
      createRelations: async () => ({ code: 403, message: '没有关联题权限', data: null }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)

    await controller.open('origin-1')
    controller.toggleSelection('candidate-1')
    const created = await controller.createSelected()

    expect(created).toBe(false)
    expect(controller.state.selectedIds).toEqual(['candidate-1'])
    expect(controller.state.error).toBe('没有关联题权限')
  })

  it('候选和已关联题都支持超过 50 条翻页，且候选勾选可跨页保留', async () => {
    const candidatePageOne = { ...candidate, id: 'candidate-page-1' }
    const candidatePageTwo = { ...candidate, id: 'candidate-page-2' }
    const linkedPageOne = { ...linked, id: 'linked-page-1' }
    const linkedPageTwo = { ...linked, id: 'linked-page-2' }
    const api: RelationApi = {
      relationCandidates: async (_id, params) => params?.page === 2
        ? page([candidatePageTwo], 2, 50, 51)
        : page([candidatePageOne], 1, 50, 51),
      relations: async (_id, params) => params?.page === 2
        ? page([linkedPageTwo], 2, 50, 51)
        : page([linkedPageOne], 1, 50, 51),
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)

    await controller.open('origin-1')
    controller.toggleSelection('candidate-page-1')
    await controller.nextCandidatePage()
    await controller.nextLinkedPage()

    expect(controller.state.candidatePage).toBe(2)
    expect(controller.state.candidateTotal).toBe(51)
    expect(controller.state.candidatePageSize).toBe(50)
    expect(controller.state.candidates).toEqual([candidatePageTwo])
    expect(controller.state.selectedIds).toEqual(['candidate-page-1'])
    expect(controller.state.linkedPage).toBe(2)
    expect(controller.state.linkedTotal).toBe(51)
    expect(controller.state.linkedPageSize).toBe(50)
    expect(controller.state.linked).toEqual([linkedPageTwo])
  })

  it('关闭弹窗后忽略慢响应，避免重新写回已清空的关联题列表', async () => {
    const candidateRequest = deferred<ReturnType<typeof page>>()
    const linkedRequest = deferred<ReturnType<typeof page>>()
    const api: RelationApi = {
      relationCandidates: async () => candidateRequest.promise,
      relations: async () => linkedRequest.promise,
      createRelations: async () => ({ data: {} }),
      removeRelation: async () => ({ data: {} }),
    }
    const controller = createQuestionRelationsController(api)
    const opening = controller.open('origin-1')

    controller.close()
    candidateRequest.resolve(page([candidate]))
    linkedRequest.resolve(page([linked]))
    await opening

    expect(controller.state.visible).toBe(false)
    expect(controller.state.questionId).toBeNull()
    expect(controller.state.candidates).toEqual([])
    expect(controller.state.linked).toEqual([])
  })

  it('从题 A 切换至题 B 时忽略题 A 的迟到响应', async () => {
    const requests: Record<string, { candidates: ReturnType<typeof deferred<ReturnType<typeof page>>>; linked: ReturnType<typeof deferred<ReturnType<typeof page>>> }> = {}
    const api: RelationApi = {
      relationCandidates: async (questionId) => {
        requests[questionId] ||= { candidates: deferred(), linked: deferred() }
        return requests[questionId].candidates.promise
      },
      relations: async (questionId) => {
        requests[questionId] ||= { candidates: deferred(), linked: deferred() }
        return requests[questionId].linked.promise
      },
      createRelations: async () => ({ data: {} }),
      removeRelation: async () => ({ data: {} }),
    }
    const controller = createQuestionRelationsController(api)
    const openingA = controller.open('question-a')
    const openingB = controller.open('question-b')

    requests['question-b'].candidates.resolve(page([{ ...candidate, id: 'candidate-b' }]))
    requests['question-b'].linked.resolve(page([{ ...linked, id: 'linked-b' }]))
    await openingB
    requests['question-a'].candidates.resolve(page([{ ...candidate, id: 'candidate-a' }]))
    requests['question-a'].linked.resolve(page([{ ...linked, id: 'linked-a' }]))
    await openingA

    expect(controller.state.questionId).toBe('question-b')
    expect(controller.state.candidates.map((item) => item.id)).toEqual(['candidate-b'])
    expect(controller.state.linked.map((item) => item.id)).toEqual(['linked-b'])
  })
})
