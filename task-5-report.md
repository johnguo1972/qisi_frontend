# Task 5 report - audit manual, photo and course ingestion sources

## Delivered

- Manual creation normalizes submitted question types, records a `manual_create`
  batch against its selected paper, and finalizes post-start errors as failed.
- Photo recognition normalizes recognized types and records a `photo_create`
  batch against the resolved or newly created paper.
- Course question linking writes a course-scoped `course_link_import` batch
  using the actual `CourseQuestionLink.get_or_create` count. Repeated links
  therefore produce a visible successful zero-count batch.
- Course material imports normalize their submitted type and record a
  `course_material_import` batch linked to course and paper. The pre-existing
  paper creation used the non-existent `grade_level` field; it now uses
  `ExamPaper.grade`, allowing this endpoint to complete.
- The existing direct photo view test now uses a persisted user, matching the
  ingestion batch foreign-key contract.

## Added coverage

`apps/study/tests/test_question_ingestion_sources.py` verifies manual success
and failure lifecycle, photo success, course-scoped linking, repeated zero
linking, course-material audit state, paper/course associations, and type
normalization.

## Verification

- `ai-tools -m pytest` over source/history/JSON/photo/course suites with a
  short worktree `--basetemp`: **45 passed**.
- `manage.py check`: no issues.
- `manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: clean.

## Risks

- Audit finalization is deliberately outside a database transaction so failed
  operations remain visible. A downstream error can still leave pre-existing
  partial source rows, preserving endpoint behavior instead of introducing an
  unrelated rollback policy.
- No frontend work or historical backfill was performed.
