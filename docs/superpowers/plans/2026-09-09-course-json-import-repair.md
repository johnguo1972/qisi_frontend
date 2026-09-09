# Course JSON Import Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make course JSON imports allocate resilient question IDs, always retain course context, and report actionable import results.

**Architecture:** The ID generator will lock the per-subject counter, reconcile it with existing IDs sharing its prefix, then reserve one unused ID in the same transaction. Course practice will use a dedicated client API that requires a course ID; the existing course route will return course/link metadata. The UI will show final counts and sanitized diagnostic samples returned by the importer.

**Tech Stack:** Django, Django REST Framework, pytest-django, Vue 3 / UniApp TypeScript.

**Spec:** User-confirmed repair requirements from 2026-09-09.

## Global Constraints

- Keep generic question-bank JSON import usable without a course context.
- Course-practice JSON import must refuse to start without its route course ID.
- Do not return raw exception traces, filesystem paths, credentials, or uploaded content in error samples.
- Preserve the existing `QuestionIngestionBatch` audit model and course-scoped history filtering.

---

### Task 1: Resilient question system-ID allocation

**Files:**
- Modify: `apps/common/codegen.py`
- Create: `apps/common/tests/test_codegen.py`

**Interfaces:**
- Produces: `generate_question_system_id(subject: str) -> str`
- Depends on: `ExamQuestion.system_id`, `QuestionIDCounter.next_seq`

- [ ] **Step 1: Write failing tests** for a stale counter below the maximum used prefixed ID, a rollback after reservation, and sequential reservations that model concurrent callers.
- [ ] **Step 2: Run the tests and verify the stale-counter test fails** because the existing 100-attempt loop raises.
- [ ] **Step 3: Implement counter reconciliation** under `select_for_update`, set `next_seq` to at least the maximum matching hexadecimal ID plus one, then reserve the next unused ID.
- [ ] **Step 4: Run the codegen tests** and verify all three cases pass.

### Task 2: Course import contract and audit result

**Files:**
- Modify: `apps/courses/views.py`
- Modify: `apps/study/json_import_views.py`
- Modify: `apps/study/ingestion_views.py`
- Modify: `apps/courses/tests/test_course_question_list.py`
- Modify: `apps/study/tests/test_question_ingestion_history.py`

**Interfaces:**
- Produces: course JSON response fields `course_id`, `tree_node_id`, `linked_count`, `total_read`, `imported`, `skipped_existing`, `skipped_in_package`, `failed`, `error_details`.
- Consumes: `Course`, `CourseTree`, `CourseQuestionLink`, `QuestionIngestionBatch`.

- [ ] **Step 1: Write failing endpoint tests** showing the course import response contains the explicit course/link fields and course history excludes bank-only batches.
- [ ] **Step 2: Run targeted tests and verify response-contract expectations fail.**
- [ ] **Step 3: Add explicit course context validation and normalized response fields**, preserving generic question-bank imports and sanitizing failed-question error samples.
- [ ] **Step 4: Run targeted course and ingestion-history tests** and verify they pass.

### Task 3: Dedicated course client and visible import result

**Files:**
- Modify: `uniapp/src/api/questions.ts`
- Modify: `uniapp/src/pages/teacher/course-practice.vue`
- Add/modify tests only if an established frontend test harness is present.

**Interfaces:**
- Produces: `importCourseJsonPackage(file, { courseId, treeNodeId? })` which rejects a missing course ID before any generic upload fallback.
- Consumes: course response fields from Task 2.

- [ ] **Step 1: Write a failing lightweight TypeScript test if the repository has a runnable frontend test harness; otherwise record the typecheck/build verification command.**
- [ ] **Step 2: Implement the dedicated course-only upload API** and have course practice call it after validating route state.
- [ ] **Step 3: Present a result dialog/toast summary** containing read/new/deduplicated/failed/linked counts and a bounded list of sanitized error messages.
- [ ] **Step 4: Run H5 build and verify the compiled page uses the dedicated course API.**

### Task 4: Operational recovery readiness

**Files:**
- Create: `apps/papers/management/commands/reconcile_question_id_counter.py`
- Create: `apps/papers/tests/test_reconcile_question_id_counter.py`

**Interfaces:**
- Produces: `python manage.py reconcile_question_id_counter --subject P [--apply]`.
- Consumes: the shared ID reconciliation helper from Task 1.

- [ ] **Step 1: Write a failing command test** for reporting and applying an out-of-date physical-science counter.
- [ ] **Step 2: Implement a dry-run-by-default management command** and an explicit `--apply` mutation path.
- [ ] **Step 3: Run command tests and targeted import tests.**
- [ ] **Step 4: After release approval, run `--subject P --apply` on production and ask the user to select/re-upload the original package in Course Practice**, because the failed temporary ZIP is intentionally cleaned after import.
