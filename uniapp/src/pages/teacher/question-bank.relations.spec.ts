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

function page(items: typeof candidate[]) {
  return { data: { items, total: items.length, reason: '' } }
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
})
