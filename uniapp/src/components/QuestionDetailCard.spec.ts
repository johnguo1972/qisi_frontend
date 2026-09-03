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
  it('prefers imported formula-ready HTML for the stem and options', async () => {
    const wrapper = mount(QuestionDetailCard, {
      props: {
        question: {
          ...question,
          stem: 'raw [[formula:q001_formula_01]]',
          stem_html: '<span data-test="stem-formula">AB</span>',
          options: [{
            label: 'A',
            content: 'raw [[formula:q001_formula_02]]',
            content_html: '<span data-test="option-formula">CD</span>',
          }],
        },
        index: 1,
        showAnswer: false,
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="stem-formula"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="option-formula"]').exists()).toBe(true)
    expect(wrapper.html()).not.toContain('[[formula:')
  })

  it('rerenders formula HTML when a refreshed question keeps the same id', async () => {
    const wrapper = mount(QuestionDetailCard, {
      props: {
        question: {
          ...question,
          stem: 'raw [[formula:q001_formula_01]]',
        },
        index: 1,
        showAnswer: false,
      },
    })

    expect(wrapper.text()).toContain('[[formula:q001_formula_01]]')

    await wrapper.setProps({
      question: {
        ...question,
        stem: 'raw [[formula:q001_formula_01]]',
        stem_html: '<img data-test="refreshed-formula" src="/media/formula.png" />',
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="refreshed-formula"]').exists()).toBe(true)
    expect(wrapper.html()).not.toContain('[[formula:')
  })

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
