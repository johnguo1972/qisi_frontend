import { describe, expect, it } from 'vitest'
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
})
