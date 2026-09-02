import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import NicknameEditor from './NicknameEditor.vue'

const { updateProfile } = vi.hoisted(() => ({ updateProfile: vi.fn() }))

vi.mock('@/api/index.ts', () => ({
  authApi: { updateProfile },
}))

describe('NicknameEditor', () => {
  beforeEach(() => {
    updateProfile.mockReset()
    vi.stubGlobal('uni', { showToast: vi.fn() })
  })

  function mountEditor() {
    return mount(NicknameEditor, {
      props: { displayName: '旧昵称' },
      global: {
        stubs: {
          Input: {
            props: ['modelValue'],
            emits: ['update:modelValue'],
            render() {
              return h('input', {
                class: 'nickname-input',
                value: this.modelValue,
                onInput: (event: Event) => this.$emit('update:modelValue', (event.target as HTMLInputElement).value),
              })
            },
          },
        },
      },
    })
  }

  it('submits a trimmed nickname and returns the saved profile to its caller', async () => {
    updateProfile.mockResolvedValue({
      code: 0,
      data: { id: 'user-1', display_name: '王同学', active_role: 'student' },
    })
    const wrapper = mountEditor()

    await wrapper.get('.edit-trigger').trigger('click')
    await wrapper.get('.nickname-input').setValue('  王同学  ')
    await wrapper.get('[data-testid="save-nickname"]').trigger('click')
    await flushPromises()

    expect(updateProfile).toHaveBeenCalledWith({ display_name: '王同学' })
    expect(wrapper.emitted('updated')).toEqual([[{
      id: 'user-1', display_name: '王同学', active_role: 'student',
    }]])
  })

  it('keeps the dialog open and does not call the API when the nickname is blank', async () => {
    const wrapper = mountEditor()

    await wrapper.get('.edit-trigger').trigger('click')
    await wrapper.get('.nickname-input').setValue('   ')
    await wrapper.get('[data-testid="save-nickname"]').trigger('click')

    expect(updateProfile).not.toHaveBeenCalled()
    expect(wrapper.find('.nickname-input').exists()).toBe(true)
  })
})
