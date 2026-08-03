# Manual Question AI Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make question probing and A/B/C answer generation run only after an explicit user click, while safely retiring queued automatic tasks.

**Architecture:** Remove both automatic dispatch sources and retain the legacy Celery task only as a no-op tombstone. Keep the existing full and single-mode review tasks, add a probe-only service/task/API, and expose all five manual actions through one reusable UniApp modal component used by every teacher question-management page.

**Tech Stack:** Django 5.2, Django REST Framework, Celery, pytest/pytest-django, Vue 3, UniApp, TypeScript, Vite.

## Global Constraints

- Modify code only under ./front.
- New, imported, parsed, saved, edited, or confirmed questions must not automatically call question-probe or A/B/C models.
- Keep five explicit UI actions: 一键全部 AI 处理, AI 探查, A 模式, B 模式, C 模式.
- A/B/C single-mode actions must never implicitly run probe AI.
- Keep Qwen/DeepSeek routing, prompts, credentials, and the 300-second timeout unchanged.
- Keep DeepSeek verification in the explicit full pipeline.
- Preserve existing AI results; do not clear Redis/Celery queues.
- Preserve unrelated .env, media, dump, and documentation working-tree changes.

---

### Task 1: Remove automatic AI dispatch sources

**Files:**
- Modify: apps/study/receivers.py
- Modify: apps/study/photo_views.py
- Create: apps/study/tests/test_manual_ai_triggers.py

**Interfaces:**
- Consumes: Django ExamQuestion post_save and photo_create_question.
- Produces: question persistence and photo recognition with no single_generate_ai_answers.delay call.

- [ ] **Step 1: Write failing tests**

~~~python
@pytest.mark.django_db
def test_saving_auto_parsed_question_does_not_dispatch_ai():
    paper = ExamPaper.objects.create(title="手工 AI 测试", subject="math")
    with patch(
        "apps.common.batch_tasks.single_generate_ai_answers.delay"
    ) as delay:
        ExamQuestion.objects.create(
            paper=paper, question_no="1", question_type="short_answer",
            stem="题干", parse_status="auto_parsed",
        )
    delay.assert_not_called()


@pytest.mark.django_db
def test_photo_create_returns_manual_message_without_dispatch(success_photo_request):
    with patch(
        "apps.common.batch_tasks.single_generate_ai_answers.delay"
    ) as delay:
        response = _plain_view_handler(photo_views.photo_create_question)(
            success_photo_request
        )
    assert response.status_code == 200
    assert response.data["message"] == "识别成功，可手工进行 AI 处理"
    assert response.data["data"]["ai_generation_status"] == "not_started"
    delay.assert_not_called()
~~~

Define success_photo_request in this test module with SimpleNamespace, a real temporary image under settings.MEDIA_ROOT, a real ExamPaper, and patched vision_parser_component_factory returning deterministic parsed data. Patch only OSS/image parsing boundaries; allow ExamQuestion and related rows to persist to the test database.

- [ ] **Step 2: Verify RED**

Run: python -m pytest apps/study/tests/test_manual_ai_triggers.py -q

Expected: tests fail because save/photo-create currently dispatch the legacy task.

- [ ] **Step 3: Implement minimal removal**

Remove only the ExamQuestion receiver and AI-task import from receivers.py; keep backfill_mission_progress_on_join. Remove the task import and delay call from photo_views.py. Return message 识别成功，可手工进行 AI 处理 and ai_generation_status not_started.

- [ ] **Step 4: Verify GREEN**

Run: python -m pytest apps/study/tests/test_manual_ai_triggers.py apps/study/tests/test_photo_ai.py -q

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

~~~powershell
git add apps/study/receivers.py apps/study/photo_views.py apps/study/tests/test_manual_ai_triggers.py
git commit -m "fix: disable automatic question AI dispatch"
~~~

### Task 2: Retire legacy jobs and skip missing manual targets

**Files:**
- Modify: apps/common/batch_tasks.py
- Modify: apps/review/tasks.py
- Modify: apps/common/ai/tests/test_review_compatibility.py

**Interfaces:**
- Consumes: queued task name apps.common.batch_tasks.single_generate_ai_answers.
- Produces: {status: skipped, question_id: str, reason: str} without AI calls.

- [ ] **Step 1: Write failing boundary tests**

~~~python
def test_legacy_automatic_task_is_a_noop():
    with patch.object(batch_tasks, "create_ai_review_service") as factory:
        result = batch_tasks.single_generate_ai_answers.run("old-id")
    assert result == {
        "status": "skipped",
        "question_id": "old-id",
        "reason": "automatic_generation_disabled",
    }
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("task_name", "args"),
    [
        ("single_ai_process_question", ("missing",)),
        ("single_mode_ai_process_question", ("missing", "A")),
    ],
)
def test_manual_task_skips_missing_before_client(task_name, args):
    with (
        patch.object(
            tasks.ExamQuestion.objects, "get",
            side_effect=tasks.ExamQuestion.DoesNotExist,
        ),
        patch.object(tasks, "create_ai_review_service") as factory,
        patch.object(tasks.cache, "set"),
    ):
        result = getattr(tasks, task_name).run(*args)
    assert result["status"] == "skipped"
    assert result["reason"] == "question_not_found"
    factory.assert_not_called()
~~~

- [ ] **Step 2: Verify RED**

Run: python -m pytest apps/common/ai/tests/test_review_compatibility.py -k "legacy_automatic or skips_missing" -q

Expected: legacy task invokes the facade and review tasks create it before lookup.

- [ ] **Step 3: Implement tombstone and lookup-first guards**

Make single_generate_ai_answers return automatic_generation_disabled immediately. In review tasks, query ExamQuestion before create_ai_review_service. Add a private helper returning skipped/question_not_found. Log only question ID and status. Keep temporary AI failures on their current error path.

- [ ] **Step 4: Verify GREEN**

Run: python -m pytest apps/common/ai/tests/test_review_compatibility.py -q

Expected: compatibility suite passes.

- [ ] **Step 5: Commit**

~~~powershell
git add apps/common/batch_tasks.py apps/review/tasks.py apps/common/ai/tests/test_review_compatibility.py
git commit -m "fix: retire automatic AI jobs safely"
~~~

### Task 3: Add probe-only service, task, and API

**Files:**
- Modify: apps/common/ai_service.py
- Modify: apps/review/tasks.py
- Modify: apps/review/views.py
- Modify: apps/review/urls.py
- Modify: apps/common/ai/tests/test_review_compatibility.py

**Interfaces:**
- Produces: AIReviewService.process_question_probe(question_id, model=None) returning probe, knowledge, errors.
- Produces: single_probe_ai_process_question(question_id, model=None).
- Produces: POST /api/v1/review/question/<id>/ai-process-probe/.

- [ ] **Step 1: Write failing service test**

~~~python
@pytest.mark.django_db
def test_probe_pipeline_saves_properties_without_answers():
    question = _make_question()
    facade = _real_facade_with_components()
    with patch.object(facade, "_get_question_image_urls", return_value=[]):
        results = facade.process_question_probe(str(question.id))
        facade.save_results_to_question(str(question.id), results)
    question.refresh_from_db()
    assert set(results) == {"probe", "knowledge", "errors"}
    assert question.ai_probe_result["subject"] == "math"
    assert question.ai_knowledge_enrichment["difficulty"] == "L3"
    assert question.ai_answer_a is None
    assert question.ai_answer_b is None
    assert question.ai_answer_c is None
~~~

- [ ] **Step 2: Verify RED**

Run: python -m pytest apps/common/ai/tests/test_review_compatibility.py::test_probe_pipeline_saves_properties_without_answers -q

Expected: process_question_probe is missing.

- [ ] **Step 3: Implement minimal service method**

~~~python
def process_question_probe(self, question_id, model=None):
    question = ExamQuestion.objects.get(id=question_id)
    image_urls = self._get_question_image_urls(question)
    probe = self.probe_and_norm(question, image_urls, model=model)
    knowledge = self.analyze_knowledge_points(
        question,
        probe.get("normalized_text", question.stem or ""),
        subject_hint=probe.get("subject", ""),
        model=model,
    )
    return {"probe": probe, "knowledge": knowledge, "errors": {}}
~~~

Handle AIRequestError per component using the full-pipeline partial-result convention. Do not invoke vision, A/B/C solvers, or verifier.

- [ ] **Step 4: Write failing task/API tests**

~~~python
@pytest.mark.django_db
def test_probe_endpoint_dispatches_only_probe_task():
    question = _make_question()
    queued = MagicMock(id="probe-task")
    with patch(
        "apps.review.tasks.single_probe_ai_process_question.delay",
        return_value=queued,
    ) as delay:
        response = APIClient().post(
            f"/api/v1/review/question/{question.id}/ai-process-probe/",
            {}, format="json",
        )
    assert response.status_code == 200
    delay.assert_called_once_with(str(question.id), model=None)


@pytest.mark.django_db
def test_probe_task_persists_only_probe_fields():
    question = _make_question()
    facade = _real_facade_with_components()
    with (
        patch("apps.review.tasks.create_ai_review_service", return_value=facade),
        patch.object(tasks.cache, "set"),
    ):
        result = tasks.single_probe_ai_process_question.run(str(question.id))
    assert result == {
        "status": "complete",
        "question_id": str(question.id),
        "mode": "probe",
    }
~~~

- [ ] **Step 5: Verify RED**

Run: python -m pytest apps/common/ai/tests/test_review_compatibility.py -k "probe_pipeline or probe_endpoint or probe_task" -q

Expected: task, route, and view are missing.

- [ ] **Step 6: Implement task, view, and URL**

The task must lookup first, update single_ai_progress:<task_id>, call process_question_probe, persist through save_results_to_question, close in finally, and return mode probe. The view validates question/model using AIProcessRequestSerializer and dispatches only single_probe_ai_process_question.delay.

- [ ] **Step 7: Verify GREEN**

Run: python -m pytest apps/common/ai/tests/test_review_compatibility.py -q

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

~~~powershell
git add apps/common/ai_service.py apps/review/tasks.py apps/review/views.py apps/review/urls.py apps/common/ai/tests/test_review_compatibility.py
git commit -m "feat: add manual question probe endpoint"
~~~

### Task 4: Build reusable five-action UniApp controls

**Files:**
- Modify: uniapp/src/api/questions.ts
- Create: uniapp/src/components/QuestionAIControls.vue
- Create: tests/test_manual_ai_ui_contract.py

**Interfaces:**
- Produces: aiProcessProbe(questionId).
- Produces: QuestionAIControls with visible/questionId props and close/completed events.

- [ ] **Step 1: Write failing UI contract tests**

~~~python
def test_controls_expose_five_explicit_actions():
    source = Path(
        "uniapp/src/components/QuestionAIControls.vue"
    ).read_text("utf-8")
    for label in (
        "一键全部 AI 处理", "AI 探查", "A 模式", "B 模式", "C 模式"
    ):
        assert label in source


def test_probe_api_uses_dedicated_endpoint():
    source = Path("uniapp/src/api/questions.ts").read_text("utf-8")
    assert "aiProcessProbe" in source
    assert "/ai-process-probe/" in source
~~~

- [ ] **Step 2: Verify RED**

Run: python -m pytest tests/test_manual_ai_ui_contract.py -q

Expected: API function and component are missing.

- [ ] **Step 3: Add API and component**

Use this public contract:

~~~typescript
const props = defineProps<{
  visible: boolean
  questionId: string | number | null
}>()
const emit = defineEmits<{
  close: []
  completed: [{ action: 'all' | 'probe' | 'A' | 'B' | 'C' }]
}>()
~~~

Exact mapping: all to aiProcessQuestion, probe to aiProcessProbe, A/B/C to aiProcessSingleMode. No lifecycle hook submits AI. Only click handlers submit. Poll getAiTaskStatus; stop on complete/partial/failed/skipped; clear timers on close/unmount; emit completed before consumer refresh.

- [ ] **Step 4: Verify tests and build**

Run:

~~~powershell
python -m pytest tests/test_manual_ai_ui_contract.py -q
Set-Location uniapp
npm run build:h5
~~~

Expected: tests pass and build exits 0.

- [ ] **Step 5: Commit**

~~~powershell
git add uniapp/src/api/questions.ts uniapp/src/components/QuestionAIControls.vue tests/test_manual_ai_ui_contract.py
git commit -m "feat: add manual question AI controls"
~~~

### Task 5: Use common controls on teacher question pages

**Files:**
- Modify: uniapp/src/pages/teacher/review-list.vue
- Modify: uniapp/src/pages/teacher/audit.vue
- Modify: uniapp/src/pages/teacher/bank.vue
- Modify: uniapp/src/pages/teacher/new-question.vue
- Modify: uniapp/src/pages/teacher/course-practice.vue
- Modify: tests/test_manual_ai_ui_contract.py

**Interfaces:**
- Consumes: QuestionAIControls from Task 4.
- Produces: a shared five-action modal opened only by explicit AI处理 clicks.

- [ ] **Step 1: Add failing consumer test**

~~~python
@pytest.mark.parametrize("page", [
    "review-list.vue", "audit.vue", "bank.vue",
    "new-question.vue", "course-practice.vue",
])
def test_teacher_page_uses_shared_manual_controls(page):
    source = Path("uniapp/src/pages/teacher", page).read_text("utf-8")
    assert "QuestionAIControls" in source
~~~

- [ ] **Step 2: Verify RED**

Run: python -m pytest tests/test_manual_ai_ui_contract.py -q

Expected: page consumer cases fail.

- [ ] **Step 3: Replace duplicated dispatch/polling**

Each AI处理 button sets selectedAiQuestionId and showAiControls. Render one QuestionAIControls per page. Close it on close and call the page's current reload function on completed. Remove page-local AI timers and direct full/mode/status imports when unused. Keep batch processing only behind its existing explicit click.

- [ ] **Step 4: Verify tests and build**

Run:

~~~powershell
python -m pytest tests/test_manual_ai_ui_contract.py -q
Set-Location uniapp
npm run build:h5
~~~

Expected: tests pass and build exits 0.

- [ ] **Step 5: Commit**

~~~powershell
git add uniapp/src/pages/teacher/review-list.vue uniapp/src/pages/teacher/audit.vue uniapp/src/pages/teacher/bank.vue uniapp/src/pages/teacher/new-question.vue uniapp/src/pages/teacher/course-practice.vue tests/test_manual_ai_ui_contract.py
git commit -m "refactor: reuse manual AI controls on teacher pages"
~~~

### Task 6: Regression verification and documentation sync

**Files:**
- Modify: docs/ai_process(0801）.md

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: verified manual-only behavior and current workflow documentation.

- [ ] **Step 1: Update documentation**

Document the five manual actions, exact routes/task boundaries, zero calls on create/save, and the disabled legacy-task tombstone.

- [ ] **Step 2: Run focused tests**

Run:

~~~powershell
python -m pytest apps/study/tests/test_manual_ai_triggers.py apps/study/tests/test_photo_ai.py apps/common/ai/tests/test_review_compatibility.py tests/test_manual_ai_ui_contract.py -q
~~~

Expected: 0 failures.

- [ ] **Step 3: Run backend regression and checks**

Run:

~~~powershell
python -m pytest apps/common/ai/tests apps/review/tests.py tests/test_ai_pipeline.py -q
python manage.py check
~~~

Expected: all tests pass and Django reports no issues.

- [ ] **Step 4: Run frontend production build**

Run:

~~~powershell
Set-Location uniapp
npm run build:h5
~~~

Expected: build exits 0. If the known @dcloudio/types/module-resolution environment issue occurs, report it separately and do not claim frontend build verification.

- [ ] **Step 5: Verify scope**

Run:

~~~powershell
git status --short
git diff --name-only HEAD~4..HEAD
~~~

Expected: all implementation paths are inside front; unrelated pre-existing files remain untouched.

- [ ] **Step 6: Commit documentation**

~~~powershell
git add "docs/ai_process(0801）.md"
git commit -m "docs: document manual question AI workflow"
~~~
