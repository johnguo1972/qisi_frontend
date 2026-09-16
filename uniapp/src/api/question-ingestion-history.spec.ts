import { beforeEach, describe, expect, it, vi } from 'vitest'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('@/utils/request', () => ({
  get,
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  del: vi.fn(),
}))

import { getQuestionIngestionHistory, importCourseJsonPackage, importCourseDocument, getCourseDocumentImportStatus } from './questions'

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

describe('importCourseJsonPackage', () => {
  beforeEach(() => {
    vi.stubGlobal('uni', { getStorageSync: vi.fn().mockReturnValue('token') })
    vi.stubGlobal('fetch', vi.fn())
  })

  it('rejects a missing course id before it can fall back to the bank import endpoint', async () => {
    await expect(importCourseJsonPackage(new File(['{}'], 'package.zip'), { courseId: '' }))
      .rejects.toThrow('course_id is required')

    expect(fetch).not.toHaveBeenCalled()
  })

  it('posts only to the explicit course import endpoint', async () => {
    vi.mocked(fetch).mockResolvedValue({
      json: async () => ({ code: 0, data: { course_id: 'course-1' } }),
    } as Response)

    await importCourseJsonPackage(new File(['{}'], 'package.zip'), {
      courseId: 'course-1',
      treeNodeId: 'node-1',
    })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/courses/course-1/questions/import-json-package/'),
      expect.objectContaining({ method: 'POST' }),
    )
  })
})

describe('importCourseDocument', () => {
  beforeEach(() => {
    vi.stubGlobal('uni', { getStorageSync: vi.fn().mockReturnValue('token') })
    vi.stubGlobal('fetch', vi.fn())
  })

  it('posts a PDF/DOCX file to the explicit current-course document endpoint', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ code: 0, data: { task_id: 'task-1' } }),
    } as Response)

    await importCourseDocument(new File(['%PDF'], 'paper.pdf'), { courseId: 'course-1' })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/courses/course-1/questions/import-document/'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows the backend validation array instead of the generic submit error', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ['DOCX 文档等价页数不能超过 100 页'],
    } as Response)

    await expect(importCourseDocument(new File(['docx'], 'paper.docx'), { courseId: 'course-1' }))
      .rejects.toThrow('DOCX 文档等价页数不能超过 100 页')
  })

  it('reads persisted document status from its current-course endpoint', () => {
    getCourseDocumentImportStatus('course-1', 'task-1')
    expect(get).toHaveBeenCalledWith('/courses/course-1/questions/import-document/task-1/status/')
  })
})
