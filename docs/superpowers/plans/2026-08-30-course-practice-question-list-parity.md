# Course Practice Question List Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make the course-practice question list use the same question cards, filters, right-side AI controls, and per-question actions as question-bank while preserving course-node scope and course-specific operations.

**Architecture:** The course question endpoint becomes a paginated, filtered projection of ExamQuestion constrained by the selected CourseQuestionLink tree node. The frontend reuses QuestionDetailCard, RightActionPanel, AiAnswerModal, the question-relation controller, and question APIs; course-practice.vue owns course-node scope and course-specific operations.

**Tech Stack:** Django 5.2, Django REST Framework, PostgreSQL JSON filters, Vue 3 Composition API, UniApp, Vitest, pytest.

**Spec:** docs/superpowers/specs/2026-08-30-course-practice-question-list-design.md

## Global Constraints

- Modify only files under front/.
- A course-practice list request requires tree_node_id; it must not return questions outside that selected node.
- Apply type, difficulty, knowledge point, tag, multi-keyword, and pagination filters after course-node scope; all provided filters use AND semantics.
- Keep ExamQuestion as the sole source of question, AI, tag, knowledge-point, favourite, and relation data.
- From-course removal only soft-deletes CourseQuestionLink; it must not delete ExamQuestion.
- AI actions submit background tasks and refresh their status; no synchronous AI modal is introduced.
- Batch and single-question variant-generation controls remain visible but disabled and must not issue requests.

---

## File Structure

- apps/courses/views.py — constrain and filter course-node questions, then return a question-bank-compatible paginated response.
- apps/courses/tests/test_course_question_list.py — API coverage for scope isolation, combined filters, pagination, and removal semantics.
- uniapp/src/api/courses.ts — typed query parameters and paginated result contract.
- uniapp/src/pages/teacher/course-practice-list.ts — pure query-builder and response-normalizer functions.
- uniapp/src/pages/teacher/course-practice-list.spec.ts — front-end regression tests for node-required requests and filter serialization.
- uniapp/src/components/RightActionPanel.vue — named slot for course-specific right-side actions.
- uniapp/src/components/QuestionDetailCard.vue — named slot for course-only footer actions.
- uniapp/src/components/QuestionDetailCard.spec.ts — component slot contract test.
- uniapp/package.json and uniapp/package-lock.json — development-only Vue component test dependencies.
- uniapp/vitest.config.ts — Vue test environment registration.
- uniapp/src/pages/teacher/course-practice.vue — list integration, filters, cards, modals, AI actions, and course-only controls.

## Task 1: Define and test the filtered course-question API

**Files:**
- Create: apps/courses/tests/test_course_question_list.py
- Modify: apps/courses/views.py
- Modify: apps/study/serializers.py to add any QuestionDetailCard field absent from QuestionListSerializer.

**Interfaces:**
- Consumes: GET /api/v1/courses/<course_id>/questions/?tree_node_id=<uuid>&page=1&page_size=20&question_type=<value>&difficulty=<value>&knowledge_point_id=<id>&tag=<name>&keyword=<text>.
- Produces: {success: true, data: {items: QuestionListSerializer[], total: number, page_no: number, page_size: number}}.
- Rejects a missing, foreign, or inaccessible tree_node_id before content filtering.

- [ ] **Step 1: Write the failing endpoint tests**

~~~
def test_course_question_list_requires_selected_course_node(api_client, course):
    response = api_client.get(f'/api/v1/courses/{course.id}/questions/')
    assert response.status_code == 400


def test_course_question_list_filters_only_current_node(api_client, course, node, questions):
    response = api_client.get(
        f'/api/v1/courses/{course.id}/questions/',
        {
            'tree_node_id': str(node.id),
            'keyword': '速度，变化',
            'knowledge_point_id': '9001',
            'tag': '秋季练习',
            'difficulty': '3.2',
            'page': 1,
            'page_size': 20,
        },
    )
    assert response.status_code == 200
    assert [item['id'] for item in response.data['data']['items']] == [str(questions.matching.id)]
    assert response.data['data']['total'] == 1
    assert str(questions.other_node.id) not in [item['id'] for item in response.data['data']['items']]


def test_course_remove_only_soft_deletes_link(api_client, course, question):
    response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-delete/',
        {'question_ids': [str(question.id)]},
        format='json',
    )
    assert response.status_code == 200
    assert ExamQuestion.objects.filter(id=question.id).exists()
    assert CourseQuestionLink.objects.get(course=course, question=question).is_deleted is True
~~~

- [ ] **Step 2: Run the new tests and verify they fail**

Run: conda run -n ai-tools python -m pytest apps/courses/tests/test_course_question_list.py -q

Expected: the missing-node request currently returns all course questions and the current endpoint returns an array instead of the paginated items envelope.

- [ ] **Step 3: Implement node-bounded question filtering**

~~~
def question_list(request, course_id):
    course = _get_course_or_404(course_id)
    _check_course_access(course, request.user)
    tree_node_id = request.query_params.get('tree_node_id')
    if not tree_node_id:
        raise ValidationError('tree_node_id is required')

    links = CourseQuestionLink.objects.filter(
        course=course, tree_node_id=tree_node_id, is_deleted=False,
    )
    queryset = ExamQuestion.objects.select_related('paper').filter(
        id__in=links.values('question_id'),
    )
    queryset = apply_course_question_filters(queryset, request.query_params)
    return Response({'success': True, 'data': paginate_question_queryset(queryset, request)})
~~~

Implement apply_course_question_filters in apps/courses/views.py. Import the keyword tokenizer from apps.study.question_views instead of recreating it. Reuse the same Q and JSON-array matching semantics for knowledge point, tag, type, difficulty, and keyword. Paginate with the same page and page_size validation as the question-bank endpoint. Use QuestionListSerializer for items so every card sees question id, stem, options, images, knowledge_points_display, tags, answer, analysis, and AI fields. Do not expose CourseQuestionLink.id as the question identity.

- [ ] **Step 4: Run the endpoint tests and verify they pass**

Run: conda run -n ai-tools python -m pytest apps/courses/tests/test_course_question_list.py -q

Expected: all tests pass; response items all belong to the selected node; soft deletion preserves ExamQuestion.

- [ ] **Step 5: Commit the API slice**

~~~
git add apps/courses/views.py apps/study/serializers.py apps/courses/tests/test_course_question_list.py
git commit -m "feat: filter course questions by selected node"
~~~

## Task 2: Add typed course-list query state and test it without UI mocks

**Files:**
- Create: uniapp/src/pages/teacher/course-practice-list.ts
- Create: uniapp/src/pages/teacher/course-practice-list.spec.ts
- Modify: uniapp/src/api/courses.ts

**Interfaces:**
- Consumes: {treeNodeId, page, pageSize, questionType, difficulty, knowledgePointId, tag, keyword}.
- Produces: a query object accepted by courseQuestionApi.list and a normalized {items, total, pageNo, pageSize} result.

- [ ] **Step 1: Write failing pure-function tests**

~~~
import { buildCourseQuestionQuery, normalizeCourseQuestionList } from './course-practice-list'

it('serializes only non-empty filters with the selected node', () => {
  expect(buildCourseQuestionQuery({
    treeNodeId: 'node-1', page: 2, pageSize: 50,
    questionType: 'single_choice', difficulty: '3.2',
    knowledgePointId: '9001', tag: '秋季练习', keyword: '速度 变化',
  })).toEqual({
    tree_node_id: 'node-1', page: 2, page_size: 50,
    question_type: 'single_choice', difficulty: '3.2',
    knowledge_point_id: '9001', tag: '秋季练习', keyword: '速度 变化',
  })
})

it('does not build a request when no course node is selected', () => {
  expect(buildCourseQuestionQuery({ treeNodeId: '', page: 1, pageSize: 20 })).toBeNull()
})
~~~

- [ ] **Step 2: Run the Vitest file and verify it fails**

Run: npm test -- course-practice-list.spec.ts

Expected: FAIL because course-practice-list.ts does not exist.

- [ ] **Step 3: Implement query construction and API typing**

~~~
export function buildCourseQuestionQuery(input: CourseQuestionListInput) {
  if (!input.treeNodeId) return null
  const query: Record<string, string | number> = {
    tree_node_id: input.treeNodeId, page: input.page, page_size: input.pageSize,
  }
  if (input.questionType) query.question_type = input.questionType
  if (input.difficulty) query.difficulty = input.difficulty
  if (input.knowledgePointId) query.knowledge_point_id = input.knowledgePointId
  if (input.tag?.trim()) query.tag = input.tag.trim()
  if (input.keyword?.trim()) query.keyword = input.keyword.trim()
  return query
}

export function normalizeCourseQuestionList(response: any): CourseQuestionListResult {
  const data = response?.data
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: Number(data?.total || 0),
    pageNo: Number(data?.page_no || 1),
    pageSize: Number(data?.page_size || 20),
  }
}
~~~

Define CourseQuestionListInput, CourseQuestionListQuery, and CourseQuestionListResult in this module. Change courseQuestionApi.list to accept CourseQuestionListQuery and serialize it with URLSearchParams, instead of constructing a query string containing only tree_node_id. Normalize only the new paginated response shape; do not retain an array fallback that could hide a backend regression.

- [ ] **Step 4: Run the Vitest file and verify it passes**

Run: npm test -- course-practice-list.spec.ts

Expected: PASS, including pagination normalization and no-node behavior.

- [ ] **Step 5: Commit the query-state slice**

~~~
git add uniapp/src/api/courses.ts uniapp/src/pages/teacher/course-practice-list.ts uniapp/src/pages/teacher/course-practice-list.spec.ts
git commit -m "feat: add course question list filter state"
~~~

## Task 3: Extend shared card and action components for course-only controls

**Files:**
- Modify: uniapp/src/components/QuestionDetailCard.vue
- Modify: uniapp/src/components/RightActionPanel.vue
- Create: uniapp/src/components/QuestionDetailCard.spec.ts

**Interfaces:**
- QuestionDetailCard retains its existing props and emits, and exposes a course-footer-actions named slot after standard footer buttons.
- RightActionPanel retains every question-bank button and exposes a course-actions named slot below AI controls.

- [ ] **Step 1: Write the failing component contract test**

~~~
it('keeps standard actions and renders supplied course footer actions', () => {
  const wrapper = mount(QuestionDetailCard, {
    props: { question, index: 1, showAnswer: false },
    slots: { 'course-footer-actions': '<button data-test="remove-course">从课程移除</button>' },
  })
  expect(wrapper.text()).toContain('关联题')
  expect(wrapper.find('[data-test="remove-course"]').exists()).toBe(true)
})
~~~

Add the exact dev dependencies with `npm install --save-dev @vue/test-utils jsdom`, then make `uniapp/vitest.config.ts` use the same UniApp Vite plugin as the application and a browser-like test environment:

~~~ts
import { defineConfig } from 'vitest/config'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  test: { environment: 'jsdom', include: ['src/**/*.spec.ts'] },
})
~~~

Do not mock QuestionDetailCard.

- [ ] **Step 2: Run the component test and verify it fails**

Run: npm test -- QuestionDetailCard.spec.ts

Expected: FAIL because the named slot is not rendered.

- [ ] **Step 3: Add narrow named-slot extension points**

~~~
<view class="q-footer-right">
  <!-- existing question-bank buttons remain unchanged -->
  <slot name="course-footer-actions" />
</view>
~~~

~~~
<view class="right-panel">
  <!-- existing question-bank buttons remain unchanged -->
  <slot name="course-actions" />
</view>
~~~

Do not put course IDs, course API imports, or course-specific labels inside either shared component.

- [ ] **Step 4: Run component and relation tests**

Run: npm test -- QuestionDetailCard.spec.ts question-bank.relations.spec.ts

Expected: PASS; standard question-bank actions still render and supplied course actions render in the required locations.

- [ ] **Step 5: Commit the shared-control slice**

~~~
git add uniapp/package.json uniapp/package-lock.json uniapp/vitest.config.ts uniapp/src/components/QuestionDetailCard.vue uniapp/src/components/RightActionPanel.vue uniapp/src/components/QuestionDetailCard.spec.ts
git commit -m "feat: allow course actions in shared question controls"
~~~

## Task 4: Replace the course table with the shared question-bank experience

**Files:**
- Modify: uniapp/src/pages/teacher/course-practice.vue

**Interfaces:**
- Consumes CourseQuestionListResult and selected course-node state from Task 2.
- Uses QuestionDetailCard, RightActionPanel, AiAnswerModal, createQuestionRelationsController, questionApi, favourite APIs, and tag APIs.
- Emits course-only mutations through courseQuestionApi.batchDelete and courseQuestionApi.batchMove.

- [ ] **Step 1: Write failing interaction tests for page-controller helpers**

~~~
it('does not request course questions until a directory node is selected', async () => {
  const fetchQuestions = vi.fn()
  await loadCourseQuestions({ treeNodeId: '', fetchQuestions })
  expect(fetchQuestions).not.toHaveBeenCalled()
})

it('submits selected questions to the existing background batch AI API', async () => {
  selectedIds.value = ['q-1', 'q-2']
  await submitBatchAi()
  expect(questionApi.batchAi).toHaveBeenCalledWith(['q-1', 'q-2'])
})

it('does not invoke variant APIs for disabled variant actions', async () => {
  await handleDisabledVariantAction()
  expect(variantApi.generate).not.toHaveBeenCalled()
  expect(variantApi.batchGenerate).not.toHaveBeenCalled()
})
~~~

Extract helpers into course-practice-list.ts if an SFC mount would make the test depend on page mocks. Pass narrowly typed callback dependencies (such as `fetchQuestions`) to the pure helpers so the tests assert real outcomes and side effects without mounting a page or mocking an unrelated component.

- [ ] **Step 2: Run interaction tests and verify they fail**

Run: npm test -- course-practice-list.spec.ts

Expected: FAIL until the page uses node-required query state and explicit disabled variant guards.

- [ ] **Step 3: Replace table markup with shared controls**

~~~
<QuestionDetailCard
  v-for="(question, index) in questions"
  :key="question.id"
  :question="question"
  :index="pageOffset + index + 1"
  :show-answer="Boolean(showAnswerMap[question.id])"
  :selected="selectedIds.includes(question.id)"
  :compact="viewMode === 'compact'"
  @check="toggleSelect"
  @toggle-answer="toggleAnswer(question.id)"
  @ai-answer="mode => openAiAnswer(question, mode)"
  @edit="goEdit"
  @related="handleRelated"
  @edit-tags="openTagEditor"
  @add-favorite="addFavorite"
>
  <template #course-footer-actions>
    <button size="mini" type="warn" @click.stop="handleRemove(question.id)">从课程移除</button>
    <button size="mini" disabled>生成变式题</button>
  </template>
</QuestionDetailCard>
~~~

Add question-bank-equivalent pagination, type/difficulty/knowledge/tag/keyword filter controls, selected-item batch bar, AI answer modal, relation modal, and tag editor. The right panel must render question-bank controls plus a course-actions slot with “布置作业”, “生成作业”, and disabled “批量生成变式题”. Keep move-node and batch removal controls only when at least one current-node question is selected.

Define the displayed index before rendering cards:

~~~ts
const pageOffset = computed(() => (currentPage.value - 1) * pageSize.value)
~~~

- [ ] **Step 4: Wire silent background AI actions and refresh behavior**

~~~
async function submitBatchAi() {
  if (!selectedIds.value.length) return showSelectionRequired()
  await questionApi.batchAi(selectedIds.value)
  uni.showToast({ title: '批量AI任务已提交', icon: 'success' })
}

async function submitAiMode(mode: 'A' | 'B' | 'C') {
  const tasks = await Promise.all(selectedIds.value.map(id => questionApi.aiProcessMode(id, mode)))
  await pollSubmittedTasks(tasks)
  await loadCourseQuestions()
}

async function pollSubmittedTasks(tasks: any[]) {
  const taskIds = tasks.map(item => item?.data?.task_id).filter(Boolean)
  await Promise.all(taskIds.map(taskId => pollAiTaskUntilTerminal(String(taskId))))
}

async function pollAiTaskUntilTerminal(taskId: string) {
  const deadline = Date.now() + 2_100_000
  while (Date.now() < deadline) {
    const response = await questionApi.getTaskStatus(taskId)
    const status = response?.data?.status
    if (['complete', 'partial', 'failed', 'skipped'].includes(status)) return status
    await new Promise(resolve => setTimeout(resolve, 2_000))
  }
  return 'failed'
}
~~~

Use question-bank polling lifecycle rules: block duplicate same-mode submissions, stop polling on page hide/unload, and refresh after complete or partial terminal states. Do not reintroduce the former synchronous AI action.

- [ ] **Step 5: Run frontend tests and H5 build**

Run: npm test -- course-practice-list.spec.ts QuestionDetailCard.spec.ts question-bank.relations.spec.ts

Run: npm run build:h5

Expected: all specified tests pass and H5 build succeeds. If uni is unavailable, run npm ci, rerun both commands, and never commit node_modules or cache directories.

- [ ] **Step 6: Commit page integration**

~~~
git add uniapp/src/pages/teacher/course-practice.vue uniapp/src/pages/teacher/course-practice-list.ts uniapp/src/pages/teacher/course-practice-list.spec.ts
git commit -m "feat: align course practice with question bank controls"
~~~

## Task 5: Run integration regression checks

**Files:**
- Modify only files from Tasks 1–4 if a test demonstrates a defect.

**Interfaces:**
- Verifies the path from course-node selection to filtered question cards, AI operations, and safe course removal.

- [ ] **Step 1: Run focused Django suites**

Run: conda run -n ai-tools python -m pytest apps/courses/tests/test_course_question_list.py apps/courses/tests/test_course_sharing.py apps/study/tests/test_question_scope.py -q

Expected: PASS. Peer teachers with valid shared-course scope can list current-node questions; other-subject teachers cannot access the course.

- [ ] **Step 2: Run the complete backend suite**

Run: conda run -n ai-tools python -m pytest -q

Expected: PASS with the project’s existing skipped-test count. Fix every new failure before proceeding.

- [ ] **Step 3: Perform manual H5 verification**

Run: npm run dev:h5

Verify:
1. Open a shared course and select a node; cards match question-bank details.
2. Filter by keyword, tag, knowledge point, type, and difficulty; all visible IDs belong to the node.
3. Open answers, A/B/C answers, tags, relations, edit, and favourites for one question.
4. Submit batch AI and one mode task; verify background task submission and silent refresh.
5. Remove a question from the course; verify it disappears only from that node and remains searchable in question-bank.
6. Verify both variant controls are disabled and create no task.

- [ ] **Step 4: Commit any regression fix and record evidence**

~~~
git status --short
~~~

If a regression test required a fix, stage only the exact changed source and test files from Tasks 1–4, then commit with: git commit -m "fix: preserve course question list parity". If no regression fix was needed, do not create another commit. Do not stage existing local backups, media archives, .env, build output, test caches, or user-owned untracked files.
