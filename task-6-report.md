# Task 6 report - course list and course cards

## Delivered

- Kept the existing Task 6 course-list page and reusable course-card implementation intact.
- Added canonical `politics` support to `CourseCard`: the card now shows the Chinese subject label, its own gradient cover, and a subject icon instead of exposing the backend code and falling back to the default cover.
- Added a component regression test for that API-to-UI mapping.

## Architecture note

`course-list.vue` is rendered inside `teacher/layout.vue`, which owns the single shared `TeacherSidebar` with `activeItem="course-list"`. The course page intentionally does not render a second sidebar.

## TDD evidence

- RED: the new card test failed because `politics` rendered as the raw backend value and used the default cover.
- GREEN: after the minimal mapping change, the focused component test passed.

## Verification

- `uniapp/node_modules/.bin/vitest.cmd run --config vitest.config.ts CourseCard.spec.ts`: 1 passed.
- `uniapp/node_modules/.bin/vitest.cmd run --config vitest.config.ts`: 51 passed across 11 files.
- `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/courses/tests/test_models.py -q --basetemp .pytest-t6`: 7 passed.
- `git diff --check`: clean.

## Risks

- This is component/API-contract coverage, not a browser or mini-program-device E2E run.
- The local Node runtime is v22.17.0; dependency installation reports warnings that two transitive CLI packages request v22.22.2 or newer, although the focused and complete Vitest suites passed.
