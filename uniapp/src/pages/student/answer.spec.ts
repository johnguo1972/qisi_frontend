import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { levelDetail } = vi.hoisted(() => ({ levelDetail: vi.fn() }))

vi.mock('@dcloudio/uni-app', () => ({
  onLoad: (callback: (options: Record<string, string>) => void) => callback({ levelId: 'level-1' }),
}))
vi.mock('@/api/student.ts', () => ({
  studentApi: { levelDetail, submitAnswer: vi.fn(), submitMission: vi.fn(), missionResults: vi.fn(), relatedQuestions: vi.fn() },
}))
vi.mock('@/utils/image-upload', () => ({
  chooseImage: vi.fn(), uploadImage: vi.fn(), chooseAndUpload: vi.fn(), checkCameraSupport: () => ({ supported: true }),
}))
vi.mock('@/utils/katex-renderer', () => ({ renderWithKatex: async (value: string) => value }))
vi.mock('@/utils/media-url', () => ({ getMediaUrl: (value: string) => `/media/${value}` }))
vi.mock('@/utils/question-type', () => ({ getQuestionTypeLabel: () => '判断题' }))

import StudentAnswer from './answer.vue'

describe('student answer page', () => {
  beforeEach(() => {
    levelDetail.mockReset()
    vi.stubGlobal('getCurrentPages', () => [])
    vi.stubGlobal('uni', {
      showToast: vi.fn(), setStorageSync: vi.fn(), getStorageSync: vi.fn(),
      previewImage: vi.fn(), chooseImage: vi.fn(), uploadFile: vi.fn(),
      navigateTo: vi.fn(), redirectTo: vi.fn(),
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders child statements, options, tables and illustrations returned for a mission question', async () => {
    levelDetail.mockResolvedValue({
      data: {
        mission_id: 'mission-1',
        questions: [{
          id: 'question-1', question_type: 'single_choice', stem: '请判断下列说法是否正确。',
          subquestions: [
            { label: '1', stem: '温度升高，分子运动更快。' },
            '字符串形式的小题也应完整显示。',
          ],
          options: [{ label: 'A', content: '选项内容' }],
          tables: [{ rows: [['物理量', '数值'], ['温度', '20℃']] }],
          images: [{ file_path: 'questions/diagram.png', placement: 'stem', display_width: 360 }],
        }],
      },
    })

    const wrapper = mount(StudentAnswer, {
      global: {
        stubs: {
          PhotoUploadEnhanced: true,
          Textarea: true,
          Image: true,
        },
      },
    })
    await flushPromises()
    await flushPromises()

    expect(wrapper.text()).toContain('温度升高，分子运动更快。')
    expect(wrapper.text()).toContain('字符串形式的小题也应完整显示。')
    expect(wrapper.text()).toContain('选项内容')
    expect(wrapper.text()).toContain('物理量')
    expect(wrapper.html()).toContain('/media/questions/diagram.png')
  })
})
