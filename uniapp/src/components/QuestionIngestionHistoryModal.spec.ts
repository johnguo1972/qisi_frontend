import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QuestionIngestionHistoryModal from './QuestionIngestionHistoryModal.vue'
import { QUESTION_TYPE_OPTIONS, getQuestionTypeLabel } from '@/constants/question-types'

const { getQuestionIngestionHistory } = vi.hoisted(() => ({
  getQuestionIngestionHistory: vi.fn(),
}))

vi.mock('@/api/questions', () => ({ getQuestionIngestionHistory }))

describe('QuestionIngestionHistoryModal', () => {
  beforeEach(() => {
    getQuestionIngestionHistory.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows ingestion details and emits close from its close control', async () => {
    getQuestionIngestionHistory.mockResolvedValue({
      code: 0,
      data: {
        items: [{
          id: 'batch-1',
          created_at: '2026-09-06T09:30:00+08:00',
          source_type: 'json_package',
          source_name: '九年级物理.json',
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

    expect(wrapper.text()).toContain('新增/导入习题历史')
    expect(wrapper.text()).toContain('九年级物理.json')
    expect(wrapper.text()).toContain('新增 8')
    expect(wrapper.text()).toContain('已跳过 2')
    expect(wrapper.text()).toContain('失败 1')
    await wrapper.get('[data-test="ingestion-history-close"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
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
    expect(wrapper.text()).toContain('最近一个月暂无新增或导入习题记录')
  })

  it('shows an explicit error instead of an empty history for an error envelope', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    getQuestionIngestionHistory.mockResolvedValue({
      code: 403,
      message: '无权查看该课程',
      data: { items: [] },
    })

    const wrapper = mount(QuestionIngestionHistoryModal, {
      props: { visible: true, scope: 'course', courseId: 'forbidden-course' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('加载历史记录失败')
    expect(wrapper.text()).not.toContain('最近一个月暂无新增或导入习题记录')
  })
})

describe('canonical question types', () => {
  it('offers exactly the eleven supported types and never unknown', () => {
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
      '单选题',
      '多选题',
      '填空题',
      '判断题',
      '简答题',
      '问答题',
      '证明题',
      '实验题',
      '计算题',
      '作图题',
      '作文题',
    ])
    expect(QUESTION_TYPE_OPTIONS.some(item => item.value === 'unknown')).toBe(false)
    expect(getQuestionTypeLabel('unknown')).not.toBe('unknown')
  })
})
