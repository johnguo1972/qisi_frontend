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
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

it('loads ten candidates initially and swaps to a non-overlapping next batch when nothing is selected', async () => {
  const first = { ...candidate, id: 'candidate-page-1' }
  const second = { ...candidate, id: 'candidate-page-2' }
  const candidateCalls: Array<{ page?: number; page_size?: number }> = []
  const api: RelationApi = {
    relationCandidates: async (_id, params) => {
      candidateCalls.push(params || {})
      return params?.page === 2 ? page([second], 2, 10, 20) : page([first], 1, 10, 20)
    },
    relations: async () => page([]),
    createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
    removeRelation: async () => ({ data: { removed: true } }),
  }
  const controller = createQuestionRelationsController(api)

  await controller.open('origin-1')
  await controller.nextCandidateBatch()

  expect(candidateCalls.map(call => call.page_size)).toEqual([10, 10])
  expect(controller.state.candidatePage).toBe(2)
  expect(controller.state.candidates.map(item => item.id)).toEqual(['candidate-page-2'])
})

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

    expect(created).toMatchObject({ status: 'failed', message: '没有关联题权限' })
    expect(controller.state.selectedIds).toEqual(['candidate-1'])
    expect(controller.state.error).toBe('没有关联题权限')
  })

  it('候选题按十题一批翻页，已关联题保持五十题分页且候选勾选可跨页保留', async () => {
    const candidatePageOne = { ...candidate, id: 'candidate-page-1' }
    const candidatePageTwo = { ...candidate, id: 'candidate-page-2' }
    const linkedPageOne = { ...linked, id: 'linked-page-1' }
    const linkedPageTwo = { ...linked, id: 'linked-page-2' }
    const api: RelationApi = {
      relationCandidates: async (_id, params) => params?.page === 2
        ? page([candidatePageTwo], 2, 10, 51)
        : page([candidatePageOne], 1, 10, 51),
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
    expect(controller.state.candidatePageSize).toBe(10)
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

  it('建立或解除关联使末页越界时回退到最后有效页，而不是停在空页', async () => {
    const candidatePageOne = { ...candidate, id: 'candidate-page-1' }
    const candidatePageTwo = { ...candidate, id: 'candidate-page-2' }
    const linkedPageOne = { ...linked, id: 'linked-page-1' }
    const linkedPageTwo = { ...linked, id: 'linked-page-2' }
    let candidateTotal = 51
    let linkedTotal = 51
    const candidateCalls: number[] = []
    const linkedCalls: number[] = []
    const api: RelationApi = {
      relationCandidates: async (_id, params) => {
        const currentPage = params?.page || 1
        candidateCalls.push(currentPage)
        return currentPage === 2
          ? page(candidateTotal > 50 ? [candidatePageTwo] : [], 2, 50, candidateTotal)
          : page([candidatePageOne], 1, 50, candidateTotal)
      },
      relations: async (_id, params) => {
        const currentPage = params?.page || 1
        linkedCalls.push(currentPage)
        return currentPage === 2
          ? page(linkedTotal > 50 ? [linkedPageTwo] : [], 2, 50, linkedTotal)
          : page([linkedPageOne], 1, 50, linkedTotal)
      },
      createRelations: async () => {
        candidateTotal = 50
        return { data: { created_count: 1, existing_count: 0, invalid_question_ids: [] } }
      },
      removeRelation: async () => {
        linkedTotal = 50
        return { data: { removed: true } }
      },
    }
    const controller = createQuestionRelationsController(api)

    await controller.open('origin-1')
    await controller.nextCandidatePage()
    controller.toggleSelection('candidate-page-2')
    await controller.createSelected()
    expect(controller.state.candidatePage).toBe(1)
    expect(controller.state.candidates).toEqual([candidatePageOne])
    expect(candidateCalls.slice(-2)).toEqual([2, 1])

    await controller.nextLinkedPage()
    await controller.remove('linked-page-2')
    expect(controller.state.linkedPage).toBe(1)
    expect(controller.state.linked).toEqual([linkedPageOne])
    expect(linkedCalls.slice(-2)).toEqual([2, 1])
  })

  it('同一题快速翻页时，候选和已关联题都只接受最新页响应', async () => {
    const candidateRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const linkedRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const api: RelationApi = {
      relationCandidates: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([candidate], 1, 50, 150)
        candidateRequests[requestedPage] ||= deferred()
        return candidateRequests[requestedPage].promise
      },
      relations: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([linked], 1, 50, 150)
        linkedRequests[requestedPage] ||= deferred()
        return linkedRequests[requestedPage].promise
      },
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')

    const candidatePageTwo = controller.changeCandidatePage(2)
    const candidatePageThree = controller.changeCandidatePage(3)
    candidateRequests[3].resolve(page([{ ...candidate, id: 'candidate-page-3' }], 3, 50, 150))
    await candidatePageThree
    candidateRequests[2].resolve(page([{ ...candidate, id: 'candidate-page-2' }], 2, 50, 150))
    await candidatePageTwo

    const linkedPageTwo = controller.changeLinkedPage(2)
    const linkedPageThree = controller.changeLinkedPage(3)
    linkedRequests[3].resolve(page([{ ...linked, id: 'linked-page-3' }], 3, 50, 150))
    await linkedPageThree
    linkedRequests[2].resolve(page([{ ...linked, id: 'linked-page-2' }], 2, 50, 150))
    await linkedPageTwo

    expect(controller.state.candidatePage).toBe(3)
    expect(controller.state.candidates.map((item) => item.id)).toEqual(['candidate-page-3'])
    expect(controller.state.linkedPage).toBe(3)
    expect(controller.state.linked.map((item) => item.id)).toEqual(['linked-page-3'])
  })

  it.each(['candidates', 'linked'] as const)('%s 的旧页仍悬挂时，最新页成功后立即结束加载且旧页结束不再改变状态', async (listKind) => {
    const candidateRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const linkedRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const api: RelationApi = {
      relationCandidates: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([candidate], 1, 50, 150)
        candidateRequests[requestedPage] ||= deferred()
        return candidateRequests[requestedPage].promise
      },
      relations: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([linked], 1, 50, 150)
        linkedRequests[requestedPage] ||= deferred()
        return linkedRequests[requestedPage].promise
      },
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')

    const oldPage = listKind === 'candidates'
      ? controller.changeCandidatePage(2)
      : controller.changeLinkedPage(2)
    const latestPage = listKind === 'candidates'
      ? controller.changeCandidatePage(3)
      : controller.changeLinkedPage(3)
    const requests = listKind === 'candidates' ? candidateRequests : linkedRequests
    const baseItem = listKind === 'candidates' ? candidate : linked
    requests[3].resolve(page([{ ...baseItem, id: `${listKind}-page-3` }], 3, 50, 150))

    await latestPage

    const visibleItems = listKind === 'candidates' ? controller.state.candidates : controller.state.linked
    expect(visibleItems.map(item => item.id)).toEqual([`${listKind}-page-3`])
    expect(controller.state.loading).toBe(false)

    requests[2].resolve(page([{ ...baseItem, id: `${listKind}-page-2` }], 2, 50, 150))
    await oldPage
    expect(controller.state.loading).toBe(false)
  })

  it.each(['create', 'remove'] as const)('%s 关联变更执行期间仍保持加载状态', async (mutationKind) => {
    const createRequest = deferred<{ data: { created_count: number; existing_count: number; invalid_question_ids: string[] } }>()
    const removeRequest = deferred<{ data: { removed: boolean } }>()
    const api: RelationApi = {
      relationCandidates: async () => page([candidate]),
      relations: async () => page([linked]),
      createRelations: async () => createRequest.promise,
      removeRelation: async () => removeRequest.promise,
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')

    if (mutationKind === 'create') controller.toggleSelection(candidate.id)
    const operation = mutationKind === 'create'
      ? controller.createSelected()
      : controller.remove(linked.id)

    expect(controller.state.loading).toBe(true)

    if (mutationKind === 'create') {
      createRequest.resolve({ data: { created_count: 1, existing_count: 0, invalid_question_ids: [] } })
    } else {
      removeRequest.resolve({ data: { removed: true } })
    }
    await operation
    expect(controller.state.loading).toBe(false)
  })

  it('最新页成功后，候选和已关联题的旧页迟到失败都不能覆盖当前错误状态', async () => {
    const candidateRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const linkedRequests: Record<number, ReturnType<typeof deferred<ReturnType<typeof page>>>> = {}
    const api: RelationApi = {
      relationCandidates: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([candidate], 1, 50, 150)
        candidateRequests[requestedPage] ||= deferred()
        return candidateRequests[requestedPage].promise
      },
      relations: async (_id, params) => {
        const requestedPage = params?.page || 1
        if (requestedPage === 1) return page([linked], 1, 50, 150)
        linkedRequests[requestedPage] ||= deferred()
        return linkedRequests[requestedPage].promise
      },
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')

    const candidatePageTwo = controller.changeCandidatePage(2)
    const candidatePageThree = controller.changeCandidatePage(3)
    candidateRequests[3].resolve(page([{ ...candidate, id: 'candidate-page-3' }], 3, 50, 150))
    await candidatePageThree
    candidateRequests[2].reject(new Error('候选旧页失败'))
    await candidatePageTwo
    const candidateError = controller.state.error

    controller.state.error = ''
    const linkedPageTwo = controller.changeLinkedPage(2)
    const linkedPageThree = controller.changeLinkedPage(3)
    linkedRequests[3].resolve(page([{ ...linked, id: 'linked-page-3' }], 3, 50, 150))
    await linkedPageThree
    linkedRequests[2].reject(new Error('已关联旧页失败'))
    await linkedPageTwo

    expect({ candidateError, linkedError: controller.state.error }).toEqual({ candidateError: '', linkedError: '' })
    expect(controller.state.candidatePage).toBe(3)
    expect(controller.state.linkedPage).toBe(3)
    expect(controller.state.loading).toBe(false)
  })

  it('部分成功只移除有效选择，全部无效则保留全部选择并返回明确统计', async () => {
    const selectedCandidates = [
      { ...candidate, id: 'candidate-created' },
      { ...candidate, id: 'candidate-existing' },
      { ...candidate, id: 'candidate-invalid' },
    ]
    let responseData = { created_count: 1, existing_count: 1, invalid_question_ids: ['candidate-invalid'] }
    const api: RelationApi = {
      relationCandidates: async () => page(selectedCandidates),
      relations: async () => page([]),
      createRelations: async () => ({ data: responseData }),
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')
    selectedCandidates.forEach((item) => controller.toggleSelection(item.id))

    const partial = await controller.createSelected()

    expect(partial).toMatchObject({
      status: 'partial',
      createdCount: 1,
      existingCount: 1,
      invalidQuestionIds: ['candidate-invalid'],
    })
    expect(controller.state.selectedIds).toEqual(['candidate-invalid'])
    expect(partial.message).toContain('2')
    expect(partial.message).toContain('1')

    responseData = { created_count: 0, existing_count: 0, invalid_question_ids: ['candidate-invalid'] }
    const invalid = await controller.createSelected()
    expect(invalid).toMatchObject({ status: 'invalid', createdCount: 0, existingCount: 0 })
    expect(controller.state.selectedIds).toEqual(['candidate-invalid'])
  })

  it('建立关联已成功但刷新失败时保留成功结果，并将刷新问题标记为警告', async () => {
    let refreshFails = false
    const api: RelationApi = {
      relationCandidates: async () => {
        if (refreshFails) throw new Error('刷新超时')
        return page([candidate])
      },
      relations: async () => {
        if (refreshFails) throw new Error('刷新超时')
        return page([])
      },
      createRelations: async () => {
        refreshFails = true
        return { data: { created_count: 1, existing_count: 0, invalid_question_ids: [] } }
      },
      removeRelation: async () => ({ data: { removed: true } }),
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')
    controller.toggleSelection('candidate-1')

    const result = await controller.createSelected()

    expect(result).toMatchObject({ status: 'success', createdCount: 1 })
    expect(controller.state.selectedIds).toEqual([])
    expect(controller.state.error).toBe('')
    expect(controller.state.warning).toContain('操作已成功')
  })

  it('解除关联已成功但刷新失败时立即本地移除，并返回成功与刷新警告', async () => {
    let refreshFails = false
    const api: RelationApi = {
      relationCandidates: async () => {
        if (refreshFails) throw new Error('刷新超时')
        return page([])
      },
      relations: async () => {
        if (refreshFails) throw new Error('刷新超时')
        return page([linked])
      },
      createRelations: async () => ({ data: { created_count: 0, existing_count: 0, invalid_question_ids: [] } }),
      removeRelation: async () => {
        refreshFails = true
        return { data: { removed: true } }
      },
    }
    const controller = createQuestionRelationsController(api)
    await controller.open('origin-1')
    controller.toggleSelection('linked-1')

    const result = await controller.remove('linked-1')

    expect(result).toMatchObject({ success: true, removed: true })
    expect(controller.state.linked).toEqual([])
    expect(controller.state.linkedTotal).toBe(0)
    expect(controller.state.selectedIds).toEqual([])
    expect(controller.state.error).toBe('')
    expect(controller.state.warning).toContain('操作已成功')
  })
})
