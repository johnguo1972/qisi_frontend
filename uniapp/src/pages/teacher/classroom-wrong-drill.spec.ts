import { flushPromises, mount } from '@vue/test-utils'
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

describe('classroom wrong-drill page', () => {
  beforeEach(() => {
    onLoad.mockReset()
    vi.stubGlobal('__uniConfig', { locales: {}, router: { base: '/' } })
    vi.stubGlobal('uni', { showToast: vi.fn(), chooseFile: vi.fn(), chooseMessageFile: vi.fn() })
    wrongDrillContext.mockResolvedValue({ data: { mission_id: 'mission-1', class_ids: ['class-1'] } })
    wrongDrillSources.mockResolvedValue({ data: { sources: [{ source_set_id: 'source-1' }] } })
    wrongDrillSourceDetail.mockResolvedValue({
      data: {
        questions: [{
          question_id: 'question-1', question_no: '4',
          snapshot: {
            stem: '如图，判断下列说法。',
            image_items: [{ url: '/media/exams/imported/diagram.png', placement: 'stem', display_width: 100 }],
          },
        }],
      },
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders persisted document illustration snapshots below their question stem', async () => {
    const wrapper = mount(ClassroomWrongDrill)
    await onLoad.mock.calls[0][0]({ course_id: 'course-1' })
    await flushPromises()
    await flushPromises()

    const image = wrapper.find('.question-image')
    expect(image.exists()).toBe(true)
  })
})
