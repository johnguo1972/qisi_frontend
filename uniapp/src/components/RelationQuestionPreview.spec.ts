import { h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/utils/katex-renderer', () => ({
  renderWithKatex: vi.fn(async (value: string) => `<span class="rendered-formula">${value}</span>`),
}))

import RelationQuestionPreview from './RelationQuestionPreview.vue'

describe('RelationQuestionPreview', () => {
  it('renders formula-ready stem and options with module names and numeric difficulty', async () => {
    const wrapper = mount(RelationQuestionPreview, {
      props: {
        item: {
          id: 'candidate-1',
          question_no: '8',
          stem_preview: '若 $x^2=4$，下列说法正确的是（ ）',
          difficulty: 3.2,
          knowledge_points_display: [{ id: 'kp-1', name: '一元二次方程' }],
          common_knowledge_point_names: ['一元二次方程'],
          option_previews: [
            { label: 'A', content: '$x=2$' },
            { label: 'B', content: '$x=-2$' },
          ],
        },
      },
      global: {
        stubs: {
          'rich-text': {
            props: ['nodes'],
            setup(props) {
              return () => h('div', { class: 'rich-text', innerHTML: props.nodes })
            },
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('8：')
    expect(wrapper.html()).toContain('rendered-formula')
    expect(wrapper.text()).toContain('A.')
    expect(wrapper.text()).toContain('B.')
    expect(wrapper.text()).toContain('共同知识点：一元二次方程')
    expect(wrapper.text()).toContain('难度系数：3.2')
  })
})
