import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import QuestionIngestionHistoryModal from './QuestionIngestionHistoryModal.vue'
import { QUESTION_TYPE_OPTIONS, getQuestionTypeLabel } from '@/constants/question-types'

const { getQuestionIngestionHistory } = vi.hoisted(() => ({
  getQuestionIngestionHistory: vi.fn(),
}))

vi.mock('@/api/questions', () => ({ getQuestionIngestionHistory }))

const TITLE = '\u65b0\u589e/\u5bfc\u5165\u4e60\u9898\u5386\u53f2'
const CLOSE = '\u5173\u95ed'
const EMPTY = '\u6700\u8fd1\u4e00\u4e2a\u6708\u6682\u65e0\u65b0\u589e\u6216\u5bfc\u5165\u4e60\u9898\u8bb0\u5f55'
const ERROR = '\u52a0\u8f7d\u5386\u53f2\u8bb0\u5f55\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5'

describe('QuestionIngestionHistoryModal', () => {
  beforeEach(() => {
    getQuestionIngestionHistory.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the exact Chinese loading state while the request is pending', async () => {
    getQuestionIngestionHistory.mockReturnValue(new Promise(() => undefined))

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'bank' },
    })
    await nextTick()

    expect(wrapper.text()).toContain('\u52a0\u8f7d\u4e2d...')
  })

  it('renders exact Chinese history details and emits close from its close control', async () => {
    getQuestionIngestionHistory.mockResolvedValue({
      code: 0,
      data: {
        items: [{
          id: 'batch-1',
          created_at: '2026-09-06T09:30:00+08:00',
          source_type: 'json_import',
          source_name: '\u4e5d\u5e74\u7ea7\u7269\u7406.json',
          created_count: 8,
          skipped_existing_count: 2,
          failed_count: 1,
        }],
      },
    })

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'bank' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(TITLE)
    expect(wrapper.text()).toContain('JSON \u6570\u636e\u5305\u5bfc\u5165')
    expect(wrapper.text()).toContain('\u4e5d\u5e74\u7ea7\u7269\u7406.json')
    expect(wrapper.text()).toContain('\u65b0\u589e 8')
    expect(wrapper.text()).toContain('\u5df2\u8df3\u8fc7 2')
    expect(wrapper.text()).toContain('\u5931\u8d25 1')
    const closeButton = wrapper.get('[data-test="ingestion-history-close"]')
    expect(closeButton.text()).toBe(CLOSE)
    await closeButton.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it.each([
    ['json_import', 'JSON \u6570\u636e\u5305\u5bfc\u5165'],
    ['manual_create', '\u624b\u52a8\u65b0\u589e'],
    ['photo_create', '\u62cd\u7167\u5bfc\u5165'],
    ['course_material_import', '\u8bfe\u4ef6\u5bfc\u5165'],
    ['course_link_import', '\u8bfe\u7a0b\u5173\u8054\u5bfc\u5165'],
  ])('renders backend source %s as %s', async (sourceType, expectedLabel) => {
    getQuestionIngestionHistory.mockResolvedValue({
      code: 0,
      data: {
        items: [{
          id: sourceType,
          source_type: sourceType,
          source_name: '\u6765\u6e90\u540d\u79f0',
        }],
      },
    })

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'bank' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(expectedLabel)
    expect(wrapper.text()).toContain('\u6765\u6e90\u540d\u79f0')
  })

  it('requests the exact current course id and renders a clear empty state', async () => {
    getQuestionIngestionHistory.mockResolvedValue({ code: 0, data: { items: [] } })

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'course', courseId: 'course-019ff9fc' },
    })
    await flushPromises()

    expect(getQuestionIngestionHistory).toHaveBeenCalledWith({
      scope: 'course',
      courseId: 'course-019ff9fc',
    })
    expect(wrapper.text()).toContain(EMPTY)
  })

  it('shows an explicit error instead of an empty history for an error envelope', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    getQuestionIngestionHistory.mockResolvedValue({
      code: 403,
      message: '\u65e0\u6743\u67e5\u770b\u8be5\u8bfe\u7a0b',
      data: { items: [] },
    })

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'course', courseId: 'forbidden-course' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain(ERROR)
    expect(wrapper.text()).not.toContain(EMPTY)
  })
})

describe('canonical question types', () => {
  it('offers exactly the eleven supported types with exact Chinese labels and never unknown', () => {
    expect(QUESTION_TYPE_OPTIONS.map(item => item.value)).toEqual([
      'single_choice',
      'multiple_choice',
      'fill_blank',
      'true_false',
      'short_answer',
      'question_answer',
      'proof',
      'experiment',
      'computation',
      'drawing',
      'essay',
    ])
    expect(QUESTION_TYPE_OPTIONS.map(item => item.label)).toEqual([
      '\u5355\u9009\u9898',
      '\u591a\u9009\u9898',
      '\u586b\u7a7a\u9898',
      '\u5224\u65ad\u9898',
      '\u7b80\u7b54\u9898',
      '\u95ee\u7b54\u9898',
      '\u8bc1\u660e\u9898',
      '\u5b9e\u9a8c\u9898',
      '\u8ba1\u7b97\u9898',
      '\u4f5c\u56fe\u9898',
      '\u4f5c\u6587\u9898',
    ])
    expect(QUESTION_TYPE_OPTIONS.some(item => item.value === 'unknown')).toBe(false)
    expect(getQuestionTypeLabel('unknown')).toBe('\u672a\u8bc6\u522b\u9898\u578b')
  })
})
