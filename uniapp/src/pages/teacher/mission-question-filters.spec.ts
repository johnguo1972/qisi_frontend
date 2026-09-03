import { describe, expect, it } from 'vitest'
import { buildMissionQuestionFilterParams } from './mission-question-filters'

describe('mission question filters', () => {
  it('serializes supported filters and omits retired knowledge-count and attempt-count filters', () => {
    expect(buildMissionQuestionFilterParams({
      page: 2,
      pageSize: 20,
      subject: 'physics',
      knowledgePointIds: ['kp-1', 'kp-2'],
      difficulties: [2, 4],
      stages: ['八年级 上学期'],
      questionType: 'multiple_choice',
      keyword: '速度, 加速度  匀变速',
      questionUuid: '019ff9fc',
      tag: '九年级秋季班课件练习',
      errorRateMin: 10,
      errorRateMax: 35,
    })).toEqual({
      page: 2,
      page_size: 20,
      subject: 'physics',
      knowledge_point_id: 'kp-1,kp-2',
      difficulty: '2,4',
      stages: '八年级 上学期',
      question_type: 'multiple_choice',
      keyword: '速度, 加速度  匀变速',
      uuid: '019ff9fc',
      tag: '九年级秋季班课件练习',
      error_rate_min: 10,
      error_rate_max: 35,
    })
  })

  it('does not send blank optional filters', () => {
    expect(buildMissionQuestionFilterParams({
      page: 1,
      pageSize: 10,
      subject: 'physics',
      keyword: '   ',
      questionUuid: ' ',
      tag: '',
      knowledgePointIds: [],
      difficulties: [],
      stages: [],
      questionType: '',
    })).toEqual({ page: 1, page_size: 10, subject: 'physics' })
  })
})
