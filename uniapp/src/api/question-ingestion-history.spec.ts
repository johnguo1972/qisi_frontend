import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('@/utils/request', () => ({
  get,
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))

import { getQuestionIngestionHistory } from './questions'

describe('getQuestionIngestionHistory', () => {
  beforeEach(() => get.mockReset())

  it('sends the selected course id as course_id for course history', () => {
    getQuestionIngestionHistory({ scope: 'course', courseId: '019ff9fc-85d8-7542-9241-2456a2e70dd0' })

    expect(get).toHaveBeenCalledWith('/questions/ingestion-history/', {
      scope: 'course',
      course_id: '019ff9fc-85d8-7542-9241-2456a2e70dd0',
    })
  })

  it('uses the bank scope without a course id', () => {
    getQuestionIngestionHistory({ scope: 'bank' })

    expect(get).toHaveBeenCalledWith('/questions/ingestion-history/', { scope: 'bank' })
  })
})
