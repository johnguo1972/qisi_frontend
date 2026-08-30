import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QuestionDetailCard from './QuestionDetailCard.vue'

const question = {
  id: 'question-1',
  question_no: '1',
  question_type: 'single_choice',
  difficulty: 2,
  stem: '测试题干',
  options: [],
  subquestions: [],
  tags: [],
  knowledge_points_display: [],
}

describe('QuestionDetailCard', () => {
  it('keeps standard actions and renders supplied course footer actions', () => {
    const wrapper = mount(QuestionDetailCard, {
      props: { question, index: 1, showAnswer: false },
      slots: { 'course-footer-actions': '<button data-test="remove-course">从课程移除</button>' },
    })

    expect(wrapper.text()).toContain('关联题')
    expect(wrapper.find('[data-test="remove-course"]').exists()).toBe(true)
  })
})
