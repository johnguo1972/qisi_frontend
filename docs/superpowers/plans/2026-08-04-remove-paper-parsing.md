# Remove Paper Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the full-paper, single-page, and single-question parsing feature so no UI, API, Beat schedule, Celery worker, or queued message can trigger it, while preserving existing question data and shared non-parsing capabilities.

**Architecture:** Remove the feature from its outermost triggers inward: quarantine queued legacy messages, remove backend routes and dispatchers, unregister Celery tasks and Beat recovery, then delete pipeline-only services. Keep parser-owned data models because the rest of the product uses them, and keep `convert_service` plus image cropping because course import and review reuse them.

**Tech Stack:** Django 5, Django REST Framework, Celery, Redis/Kombu, PostgreSQL, Vue 3/UniApp, pytest.

## Global Constraints

- Modify only files under `./front`.
- Do not commit `.env`, media, dump files, pytest temp directories, or the existing untracked `docs/improve.md`.
- Delete `parse_paper_task`, `reparse_page_task`, `reparse_question_task`, and `periodic_stale_task_check`; do not replace them with tombstone tasks.
- Preserve `ExamPaper`, `ParseTask`, `ExamPage`, `ExamQuestion`, `QuestionOption`, `QuestionImage`, `AIParseResult`, their migrations, and existing database rows.
- Preserve JSON/ZIP import, manual question creation, photo question creation, course material conversion, review image recropping, manual AI probe/A/B/C/full processing, and DeepSeek verification.
- Quarantine only the three removed task names from Redis; preserve every other queued message and its order.
- AI calls and browser E2E are not considered verified unless they are actually run with data-bearing evidence.

---

### Task 1: Add removal contracts and quarantine queued parsing jobs

**Files:**
- Create: `tests/test_paper_parsing_removed.py`
- Runtime state: Redis broker configured by `CELERY_BROKER_URL`
- Runtime state: existing `ParseTask` rows

**Interfaces:**
- Consumes: current task names and URLs documented in the approved design.
- Produces: failing contracts that name every removed trigger; active Redis queue with zero matching parsing messages; historical active parse rows marked cancelled.

- [ ] **Step 1: Write the failing backend and frontend removal contracts**

Create `tests/test_paper_parsing_removed.py` with constants and focused assertions:

```python
from pathlib import Path

import pytest
from django.urls import Resolver404, resolve

ROOT = Path(__file__).resolve().parents[1]
TASK_NAMES = (
    "apps.parser.tasks.parse_paper_task",
    "apps.parser.tasks.reparse_page_task",
    "apps.parser.tasks.reparse_question_task",
)


@pytest.mark.parametrize("url", [
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/parse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/stop-parse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/reparse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/progress/",
    "/api/v1/questions/import-batches",
])
def test_removed_paper_parsing_urls_do_not_resolve(url):
    with pytest.raises(Resolver404):
        resolve(url)


def test_removed_tasks_and_beat_are_absent_from_production_sources():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "apps").rglob("*.py")
        if "tests" not in path.parts and path.name != "models.py"
    )
    for task_name in TASK_NAMES:
        assert task_name not in sources
        assert task_name.rsplit(".", 1)[-1] not in sources
    settings_source = (ROOT / "config/settings.py").read_text(encoding="utf-8")
    assert "periodic_stale_task_check" not in settings_source


def test_teacher_import_ui_and_api_are_removed():
    assert not (ROOT / "uniapp/src/pages/teacher/import.vue").exists()
    api_source = (ROOT / "uniapp/src/api/questions.ts").read_text(encoding="utf-8")
    for name in ("importFile", "importBatches", "importBatchDetail", "stopParse", "reparsePaper", "getParseProgress"):
        assert name not in api_source
```

- [ ] **Step 2: Run the contracts and verify RED**

Run:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_paper_parsing_removed.py -q --basetemp=.pytest_remove_parse_red -p no:cacheprovider
```

Expected: failures identify the still-registered URLs, tasks, Beat entry, and UniApp page/API.

- [ ] **Step 3: Inventory and atomically quarantine only removed Redis messages**

Run a Django shell script that parses each Kombu JSON envelope, rebuilds `celery` in the same order, and moves matching messages to a 24-hour quarantine key:

```python
REMOVED = {
    "apps.parser.tasks.parse_paper_task",
    "apps.parser.tasks.reparse_page_task",
    "apps.parser.tasks.reparse_question_task",
}
# Use one Redis Lua EVAL: LRANGE active queue, DEL active queue,
# RPUSH matching envelopes to celery:quarantine:paper-parsing:20260804,
# RPUSH all other envelopes back to celery, then EXPIRE quarantine 86400.
```

Before mutation print only task-name counts. After mutation assert:

```python
assert all(active_counts.get(name, 0) == 0 for name in REMOVED)
assert sum(active_counts.values()) == redis_client.llen("celery")
```

Do not print task arguments, credentials, or message bodies.

- [ ] **Step 4: Cancel historical active parsing rows without deleting history**

Run through Django ORM:

```python
from django.utils import timezone
from apps.common import status as const
from apps.papers.models import ParseTask

ParseTask.objects.filter(
    task_type__in=("full_parse", "page_reparse", "question_reparse"),
    status__in=(const.TASK_PENDING, const.TASK_RUNNING),
).update(
    status=const.TASK_CANCELLED,
    error_message="试卷解析功能已停用",
    finished_at=timezone.now(),
)
```

Print only the updated row count.

---

### Task 2: Remove Celery parsing tasks and pipeline-only services

**Files:**
- Delete: `apps/parser/tasks.py`
- Delete: `apps/parser/question_types.py`
- Delete: `apps/parser/prompts/`
- Delete: `apps/parser/schemas/`
- Delete: `apps/parser/services/formula_service.py`
- Delete: `apps/parser/services/merge_service.py`
- Delete: `apps/parser/services/position_service.py`
- Delete: `apps/parser/services/postprocess_service.py`
- Delete: `apps/parser/services/question_parse_service.py`
- Delete: `apps/parser/services/schema_service.py`
- Delete: `apps/parser/services/word_preprocess_service.py`
- Modify: `apps/parser/services/save_service.py`
- Modify: `apps/common/ai/failure_safety.py`
- Modify: `config/settings.py`
- Modify/Delete: `apps/parser/tests.py`
- Modify/Delete: `apps/parser/tests/test_safe_ai_failures.py`
- Test: `tests/test_paper_parsing_removed.py`

**Interfaces:**
- Consumes: Task 1 contracts and cleaned queue.
- Produces: no registered parsing tasks or Beat recovery; retained `word_to_pdf`, `pdf_to_images`, and `crop_question_image` APIs.

- [ ] **Step 1: Delete task registration and Beat recovery**

Delete `apps/parser/tasks.py`. Remove the `stale-task-check` entry from `CELERY_BEAT_SCHEDULE`; if it is the only entry, retain an empty dictionary:

```python
CELERY_BEAT_SCHEDULE = {}
```

Remove the three parser-only safe-failure definitions from `apps/common/ai/failure_safety.py` while keeping photo/common AI failures unchanged.

- [ ] **Step 2: Delete pipeline-only modules**

Delete the files/directories listed above only after a production-source search confirms they have no callers outside the removed task pipeline. Keep:

```text
apps/parser/models.py
apps/parser/migrations/
apps/parser/services/convert_service.py
apps/parser/services/save_service.py
apps/parser/services/__init__.py
```

In `save_service.py`, remove `save_questions()` and imports used only by it, but keep `crop_question_image(source_path, bbox, output_path)` unchanged for `apps.review.services.image_recrop_service`.

- [ ] **Step 3: Remove obsolete parser-pipeline tests but preserve shared photo safety tests**

Delete service/task tests for JSON repair, schema validation, formula validation, merge, postprocess, positioning, question parsing, full parse, page reparse, and question reparse. Preserve the photo adapter safety case by moving it to `apps/common/ai/tests/test_photo_adapter_safety.py` if its production adapter still exists.

- [ ] **Step 4: Run the task-removal contract**

Run the Task 1 pytest command. Expected: task/Beat assertions pass; URL and frontend assertions may still fail until Tasks 3 and 4.

- [ ] **Step 5: Commit**

```powershell
git add apps/parser apps/common/ai/failure_safety.py config/settings.py apps/common/ai/tests tests/test_paper_parsing_removed.py
git commit -m "refactor: remove paper parsing task engine"
```

---

### Task 3: Remove backend HTTP and HTMX parsing entry points

**Files:**
- Modify: `apps/papers/views.py`
- Modify: `apps/papers/urls.py`
- Modify: `apps/papers/tests.py`
- Delete: `apps/study/import_views.py`
- Modify: `apps/study/urls.py`
- Modify: `apps/study/serializers.py`
- Modify: `apps/review/htmx_urls.py`
- Delete: `tests/integration/test_papers.py`
- Test: `tests/test_paper_parsing_removed.py`

**Interfaces:**
- Consumes: no parser Celery tasks from Task 2.
- Produces: no HTTP/HTMX dispatch route; existing paper delete, paper list/detail review, JSON import, and question review remain callable.

- [ ] **Step 1: Reduce papers API to retained data operations**

In `apps/papers/views.py`, remove `upload_paper`, `start_parse`, `stop_parse`, `reparse_paper`, `paper_parse_progress`, task/Celery imports, and the running-parse guard in `delete_paper`. Keep authenticated soft deletion and historical task cancellation.

In `apps/papers/urls.py`, retain only:

```python
urlpatterns = [
    path('<uuid:paper_id>/', views.delete_paper, name='delete-paper'),
]
```

- [ ] **Step 2: Remove Word/PDF import-batch API**

Delete `apps/study/import_views.py`. Remove `import-batches`, `import-batches/<uuid:batch_id>`, and `papers` routes/imports from `apps/study/urls.py`. Remove `ImportBatchSerializer` and `PaperListSerializer` from `apps/study/serializers.py`; keep all question and JSON-import serializers.

- [ ] **Step 3: Remove HTMX parsing actions while retaining read-only review**

From `apps/review/htmx_urls.py`, remove `upload_modal_htmx`, `upload_paper_htmx`, `paper_progress_htmx`, `paper_reparse_htmx`, `question_reparse_htmx`, `question_reparse_progress_htmx`, their routes, and all task/status imports used only by them.

Change `paper_detail_htmx` to render only `paper` and `pages`:

```python
return render(request, 'papers/detail.html', {
    'paper': paper,
    'pages': ExamPage.objects.filter(paper=paper).order_by('page_no'),
})
```

The repository currently has no tracked HTMX template files, so no template deletion is required. Keep paper list/edit/delete, review list, question edit, image recrop/delete, and preview endpoints.

- [ ] **Step 4: Replace obsolete API tests with removal/preservation assertions**

Delete parsing upload/start tests. Add assertions that the removed URLs raise `Resolver404`, while paper deletion and JSON import routes still resolve.

- [ ] **Step 5: Run backend focused tests**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_paper_parsing_removed.py apps/papers/tests.py apps/study/tests/test_photo_ai.py -q --basetemp=.pytest_remove_parse_backend -p no:cacheprovider
```

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/papers apps/study apps/review tests
git commit -m "refactor: remove paper parsing endpoints"
```

---

### Task 4: Remove UniApp parsing page, API helpers, and E2E coverage

**Files:**
- Delete: `uniapp/src/pages/teacher/import.vue`
- Modify: `uniapp/src/api/questions.ts`
- Delete: `tests/e2e/test_upload_paper.spec.ts`
- Modify: `tests/e2e/test_teacher_workbench.spec.ts`
- Test: `tests/test_paper_parsing_removed.py`

**Interfaces:**
- Consumes: removed backend routes from Task 3.
- Produces: no user-visible paper parsing action and no frontend request to a removed API.

- [ ] **Step 1: Delete the teacher parsing page and API helpers**

Delete `import.vue`. From `questions.ts`, remove `importFile`, `importBatches`, `importBatchDetail`, `stopParse`, `reparsePaper`, `getParseProgress`, and `deletePaper`. The current source audit confirms `deletePaper` is called only by the page being deleted.

- [ ] **Step 2: Remove any residual navigation entry**

Assert that `pages.json`, `TeacherSidebar.vue`, and `AddMenuModal.vue` contain no `pages/teacher/import` entry. The current checkout already has no registered route or menu item, so do not modify those files. Do not alter JSON/ZIP import or course-material import navigation.

- [ ] **Step 3: Remove obsolete browser tests and update workbench expectations**

Delete `test_upload_paper.spec.ts`. Remove the “上传试卷” click/assertion from `test_teacher_workbench.spec.ts`; keep unrelated teacher navigation checks.

- [ ] **Step 4: Run the full removal contract and H5 build**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_paper_parsing_removed.py -q --basetemp=.pytest_remove_parse_ui -p no:cacheprovider
Set-Location uniapp
npm run build:h5
```

Expected: contract passes and build prints `DONE Build complete` with exit code 0.

- [ ] **Step 5: Commit**

```powershell
git add uniapp tests/e2e tests/test_paper_parsing_removed.py
git commit -m "refactor: remove paper parsing UI"
```

---

### Task 5: Update documentation and run final regression

**Files:**
- Modify: `README.md`
- Modify: `docs/ai_process(0801）.md`
- Test: existing backend and frontend suites

**Interfaces:**
- Consumes: completed removal from Tasks 1-4.
- Produces: accurate documentation and final evidence for merge/delivery.

- [ ] **Step 1: Remove active-feature documentation claims**

Update README and AI process documentation to state that Word/PDF paper parsing, page reparse, and question reparse were removed on 2026-08-04. Preserve documentation for JSON/ZIP import, photo question creation, course material conversion, and manual AI controls.

- [ ] **Step 2: Run static production audit**

```powershell
rg -n --glob '*.py' --glob '*.ts' --glob '*.vue' --glob '!**/tests/**' --glob '!tests/**' 'parse_paper_task|reparse_page_task|reparse_question_task|periodic_stale_task_check|import-batches|reparsePaper|getParseProgress' apps config uniapp/src
```

Expected: no production matches. Documentation/history directories are intentionally excluded.

- [ ] **Step 3: Run preserved-feature regression**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_paper_parsing_removed.py apps/study/tests/test_photo_ai.py apps/study/tests/test_manual_ai_triggers.py apps/common/ai/tests apps/review/tests.py tests/test_ai_pipeline.py -q --basetemp=.pytest_remove_parse_regression -p no:cacheprovider
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check
```

Expected: zero failures and Django reports no issues.

- [ ] **Step 4: Verify migrations and frontend**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations --check --dry-run
Set-Location uniapp
npm run build:h5
```

Expected: no model changes, no new migrations, and H5 build succeeds.

- [ ] **Step 5: Verify queue and workspace scope**

Recount Redis active messages by task name and assert all three removed task counts are zero. Then run:

```powershell
git diff --check
git status --short
git diff --name-only aaa1ff4..HEAD
```

Confirm every changed path is under `front`, and `.env`, media, dump, pytest temp directories, and `docs/improve.md` are uncommitted.

- [ ] **Step 6: Commit documentation**

```powershell
git add README.md 'docs/ai_process(0801）.md'
git commit -m "docs: retire paper parsing workflow"
```

- [ ] **Step 7: Request independent review before integration**

Provide the reviewer the approved design, this plan, the exact commit range `aaa1ff4..HEAD`, test outputs, static audit, and queue counts. Require a Critical/Important/Minor verdict and do not claim browser or real-AI E2E coverage.
