import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CourseCard from './CourseCard.vue'

describe('CourseCard', () => {
  it('renders the localized subject for a canonical politics course', () => {
    const wrapper = mount(CourseCard, {
      props: {
        course: {
          id: 'course-politics-1',
          name: '思政专题课',
          description: '时事与法治',
          subject: 'politics',
          grade_level: '高一',
          material_count: 2,
          question_count: 8,
        },
      },
    })

    expect(wrapper.text()).toContain('政治')
    expect(wrapper.find('.card-cover').attributes('style')).toContain('rgb(255, 236, 210)')
  })
})
