import { flushPromises, mount } from '@vue/test-utils'
import { h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ClassroomWrongDrill from './classroom-wrong-drill.vue'

const { onLoad, wrongDrillContext, wrongDrillSources, wrongDrillSourceDetail } = vi.hoisted(() => ({
  onLoad: vi.fn(),
  wrongDrillContext: vi.fn(),
  wrongDrillSources: vi.fn(),
  wrongDrillSourceDetail: vi.fn(),
}))

vi.mock('@dcloudio/uni-app', () => ({ onLoad, onUnload: vi.fn() }))

vi.mock('@/api/courses', () => ({
  courseApi: { wrongDrillContext },
}))

vi.mock('@/api/classroom-wrongbook', () => ({
  classroomWrongbookApi: {
    wrongDrillSources,
    wrongDrillSourceDetail,
    uploadWrongDrill: vi.fn(),
  },
}))

vi.mock('@/api/questions', () => ({
  getTagList: vi.fn().mockResolvedValue({ data: [] }),
  aiProcessProbe: vi.fn(),
  questionApi: { batchAi: vi.fn(), aiProcessMode: vi.fn() },
}))

vi.mock('@/api/favorites', () => ({ favoriteApi: { add: vi.fn() } }))

const QuestionDetailCardStub = {
  name: 'QuestionDetailCard',
  props: ['question'],
  render() { return h('div', { 'data-test': 'wrong-drill-question-card' }, this.question.id) },
}

describe('classroom wrong-drill page', () => {
  beforeEach(() => {
    onLoad.mockReset()
    vi.stubGlobal('__uniConfig', { locales: {}, router: { base: '/' } })
    vi.stubGlobal('getCurrentPages', () => [])
    vi.stubGlobal('uni', {
      showToast: vi.fn(), chooseFile: vi.fn(), chooseMessageFile: vi.fn(),
      getSystemInfoSync: vi.fn(() => ({ windowWidth: 375, windowHeight: 667 })),
    })
    wrongDrillContext.mockResolvedValue({ data: { mission_id: 'mission-1', class_ids: ['class-1'] } })
    wrongDrillSources.mockResolvedValue({ data: { sources: [{ source_set_id: 'source-1' }] } })
    wrongDrillSourceDetail.mockResolvedValue({
      data: {
        questions: [{
          id: 'question-1', question_no: '101', source_document_question_no: '4',
          stem: '如图，判断下列说法。', question_type: 'single_choice', difficulty: 2,
          images: [{ url: '/media/exams/imported/diagram.png', placement: 'stem', display_width: 100 }],
        }],
        total: 1, page_no: 1, page_size: 20,
      },
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders imported questions through the shared course-practice card with their document number', async () => {
    const wrapper = mount(ClassroomWrongDrill, { global: { stubs: { QuestionDetailCard: QuestionDetailCardStub, RightActionPanel: { render: () => h('div') }, AiAnswerModal: true, Input: { render: () => h('input') } } } })
    await onLoad.mock.calls[0][0]({ course_id: 'course-1' })
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('[data-test="wrong-drill-question-card"]').text()).toBe('question-1')
    expect(wrapper.find('[data-test="wrong-drill-document-no"]').text()).toContain('4')
  })
})
