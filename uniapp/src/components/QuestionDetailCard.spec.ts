import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QuestionDetailCard from './QuestionDetailCard.vue'
import RightActionPanel from './RightActionPanel.vue'

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

  it('keeps supplied course footer actions in compact mode', () => {
    const wrapper = mount(QuestionDetailCard, {
      props: { question, index: 1, showAnswer: false, compact: true },
      slots: { 'course-footer-actions': '<button data-test="compact-remove-course">从课程移除</button>' },
    })

    expect(wrapper.find('[data-test="compact-remove-course"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('关联题')
  })
})

describe('RightActionPanel', () => {
  it('keeps standard actions and renders supplied course actions', () => {
    const wrapper = mount(RightActionPanel, {
      slots: { 'course-actions': '<button data-test="course-action">课程操作</button>' },
    })

    expect(wrapper.text()).toContain('刷新题目')
    expect(wrapper.find('[data-test="course-action"]').exists()).toBe(true)
  })
})
