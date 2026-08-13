# Teacher AI Mode Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independently triggered AI-A, AI-B, and AI-C buttons to the teacher question bank and verify each mode end to end.

**Architecture:** Extend the reusable right action panel with B/C events and replace the page's A-only handler with one typed common handler. Reuse the existing single-mode API and Celery task without backend behavior changes.

**Tech Stack:** Vue 3 / UniApp / TypeScript, Django REST Framework, Celery, pytest.

## Global Constraints

- Modify only `./front`.
- All AI modes remain manual user actions.
- Do not change or commit `.env`.
- Do not route these buttons through the full batch AI pipeline.
- A/B/C map exactly to `ai_answer_a`, `ai_answer_b`, and `ai_answer_c`.

---

### Task 1: A/B/C UI and dispatch behavior

**Files:**
- Modify: `uniapp/src/components/RightActionPanel.vue`
- Modify: `uniapp/src/pages/teacher/question-bank.vue`
- Modify: `tests/test_teacher_ai_explore_frontend.py`

**Interfaces:**
- Consumes: `questionApi.aiProcessMode(questionId, mode)`.
- Produces: `ai-mode-a`, `ai-mode-b`, `ai-mode-c`; `handleAiMode(mode: 'A' | 'B' | 'C')`.

- [ ] Add executable tests that require all three buttons/events and run page handlers for A/B/C, multiple IDs, empty selection, and rejection.
- [ ] Run the focused tests and confirm they fail because B/C events and the common handler are absent.
- [ ] Add the two buttons/events and implement the smallest common typed handler.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit the implementation and tests.

### Task 2: Regression, build, and live A/B/C validation

**Files:**
- Verify: `apps/review/views.py`
- Verify: `apps/review/tasks.py`
- Verify: `apps/common/ai/tests/test_review_compatibility.py`

**Interfaces:**
- Consumes: POST `/review/question/{id}/ai-process-mode/{A|B|C}/`.
- Produces: persisted `ai_answer_a`, `ai_answer_b`, `ai_answer_c`.

- [ ] Run frontend and backend single-mode contract tests.
- [ ] Run `npm run build:h5`.
- [ ] Execute each Celery task synchronously for the specified question using real provider configuration, one mode at a time.
- [ ] Query the question after each call and verify only the requested mode field is populated with matching `mode`, configured model, generated timestamp, and no error.
- [ ] Independently review the branch diff and verification evidence.

