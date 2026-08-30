import { flushPromises, mount } from '@vue/test-utils'
import { h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CoursePractice from './course-practice.vue'

const { courseQuestionList, batchDelete, variantGenerate, variantBatchGenerate } = vi.hoisted(() => ({
  courseQuestionList: vi.fn(),
  batchDelete: vi.fn(),
  variantGenerate: vi.fn(),
  variantBatchGenerate: vi.fn(),
}))

vi.mock('@/api/courses', () => ({
  courseApi: { detail: vi.fn().mockResolvedValue({ data: { name: '测试课程' } }) },
  treeApi: { list: vi.fn().mockResolvedValue({ data: [] }), create: vi.fn(), update: vi.fn(), remove: vi.fn(), move: vi.fn() },
  courseQuestionApi: { list: courseQuestionList, batchDelete, batchMove: vi.fn(), import: vi.fn() },
  materialApi: { list: vi.fn().mockResolvedValue({ data: [] }) },
  variantApi: { generate: variantGenerate, batchGenerate: variantBatchGenerate, getStatus: vi.fn() },
}))

vi.mock('@/api/questions', () => ({
  questionApi: {
    dictKnowledgePoints: vi.fn().mockResolvedValue({ data: [] }),
    batchAi: vi.fn(), aiProcessMode: vi.fn(), getTaskStatus: vi.fn(), getAiJobStatus: vi.fn(), list: vi.fn(),
  },
  aiProcessProbe: vi.fn(), getQuestionTags: vi.fn(), addQuestionTag: vi.fn(), getTagList: vi.fn().mockResolvedValue({ data: [] }), removeQuestionTag: vi.fn(), importJsonPackage: vi.fn(),
}))

vi.mock('@/api/favorites', () => ({ favoriteApi: { add: vi.fn() } }))
vi.mock('@/utils/role-navigation', () => ({ navigateRoleSection: vi.fn() }))
vi.mock('./question-relations', () => ({
  createQuestionRelationsController: () => ({
    state: { visible: false, candidateTotal: 0, candidatePageSize: 50, linkedTotal: 0, linkedPageSize: 50, selectedIds: [] },
    close: vi.fn(), open: vi.fn(), createSelected: vi.fn(), remove: vi.fn(), selectTab: vi.fn(), toggleSelection: vi.fn(), previousCandidatePage: vi.fn(), nextCandidatePage: vi.fn(), previousLinkedPage: vi.fn(), nextLinkedPage: vi.fn(),
  }),
}))

const DirTreeStub = {
  name: 'DirTree',
  emits: ['select'],
  render: () => h('div', { 'data-test': 'directory-tree' }),
}
const QuestionDetailCardStub = {
  name: 'QuestionDetailCard',
  props: ['question'],
  emits: ['check'],
  render() {
    return h('div', { 'data-test': 'question-card' }, [
      this.question.id,
      h('button', { 'data-test': 'select-question', onClick: () => this.$emit('check', this.question.id) }),
      this.$slots['course-footer-actions']?.(),
    ])
  },
}
const RightActionPanelStub = {
  name: 'RightActionPanel',
  emits: ['refresh'],
  render() {
    return h('button', { 'data-test': 'refresh-questions', onClick: () => this.$emit('refresh') }, '刷新')
  },
}
const InputStub = {
  name: 'Input',
  render: () => h('input'),
}
const PickerStub = {
  name: 'Picker',
  render() {
    return h('select', {}, this.$slots.default?.())
  },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(next => { resolve = next })
  return { promise, resolve }
}

async function settle() {
  await flushPromises()
  await nextTick()
}

describe('course-practice page integration', () => {
  beforeEach(() => {
    courseQuestionList.mockReset()
    batchDelete.mockReset()
    variantGenerate.mockReset()
    variantBatchGenerate.mockReset()
    vi.stubGlobal('getCurrentPages', () => [{ options: { id: 'course-1' } }])
    vi.stubGlobal('__uniConfig', { locales: {} })
    vi.stubGlobal('uni', {
      showToast: vi.fn(), showModal: vi.fn(), navigateTo: vi.fn(), redirectTo: vi.fn(), navigateBack: vi.fn(), chooseImage: vi.fn(), chooseFile: vi.fn(), showActionSheet: vi.fn(),
      getStorageSync: vi.fn(), removeStorageSync: vi.fn(), reLaunch: vi.fn(),
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  function mountPage() {
    return mount(CoursePractice, {
      global: {
        stubs: {
          TeacherSidebar: true,
          DirTree: DirTreeStub,
          QuestionDetailCard: QuestionDetailCardStub,
          RightActionPanel: RightActionPanelStub,
          AiAnswerModal: true,
          Input: InputStub,
          Picker: PickerStub,
        },
      },
    })
  }

  it('keeps a late old-node response out of the mounted current node list and blocks loading mutations', async () => {
    const first = deferred<any>()
    const second = deferred<any>()
    const refresh = deferred<any>()
    courseQuestionList
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
      .mockReturnValueOnce(refresh.promise)
    const wrapper = mountPage()
    await settle()
    const tree = wrapper.findComponent(DirTreeStub)

    tree.vm.$emit('select', { id: 1, name: '节点一' })
    await settle()
    tree.vm.$emit('select', { id: 2, name: '节点二' })
    await settle()
    second.resolve({ data: { items: [{ question_id: 'new-question' }], total: 1, page_no: 1, page_size: 20 } })
    await settle()
    first.resolve({ data: { items: [{ question_id: 'old-question' }], total: 1, page_no: 1, page_size: 20 } })
    await settle()

    expect(wrapper.text()).toContain('new-question')
    expect(wrapper.text()).not.toContain('old-question')

    await wrapper.find('[data-test="select-question"]').trigger('click')
    await wrapper.find('[data-test="refresh-questions"]').trigger('click')
    await settle()
    const removeButton = wrapper.find('[data-test="remove-course"]')
    expect(removeButton.attributes('disabled')).toBeDefined()
    await removeButton.trigger('click')
    expect(batchDelete).not.toHaveBeenCalled()
    refresh.resolve({ data: { items: [{ question_id: 'new-question' }], total: 1, page_no: 1, page_size: 20 } })
  })

  it('does not invoke variant APIs when the mounted disabled variant button is clicked', async () => {
    courseQuestionList.mockResolvedValue({ data: { items: [{ question_id: 'q-1' }], total: 1, page_no: 1, page_size: 20 } })
    const wrapper = mountPage()
    await settle()
    wrapper.findComponent(DirTreeStub).vm.$emit('select', { id: 1, name: '节点一' })
    await settle()

    const variantButton = wrapper.find('[data-test="disabled-variant"]')
    expect(variantButton.attributes('disabled')).toBeDefined()
    await variantButton.trigger('click')
    expect(variantGenerate).not.toHaveBeenCalled()
    expect(variantBatchGenerate).not.toHaveBeenCalled()
  })
})
