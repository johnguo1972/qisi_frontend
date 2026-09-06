# Task 6 report - fingerprint backfill command

## Correction

The prior `eb11b5fe` submission incorrectly changed frontend course-card files.
Corrective commit `35f7d926` reverts only those three paths before this Task 6
implementation. This task changes no frontend files.

## Delivered

- Added `backfill_question_fingerprints` with mutually exclusive `--dry-run`
  and `--apply` modes, plus `--cleanup-stale-reservations-hours=N`.
- Questions are scanned in stable `created_at`, `id` order with ordered,
  prefetched options and images. The command calls the shared content-v1
  fingerprint builder rather than reproducing its hashing logic.
- Dry runs report candidates without creating, updating, or deleting registry
  records. Apply creates one active registry record per content fingerprint,
  retains all duplicate historical questions, and selects the earliest
  question as canonical.
- Cleanup only considers old `reserving` rows with no canonical question;
  active rows and linked reservations are never removed.

## TDD and verification

- RED: `apps/study/tests/test_backfill_question_fingerprints.py` failed 3/3
  with Django's `Unknown command: 'backfill_question_fingerprints'` error.
- GREEN: the focused command suite passed 3/3 after implementation.
- Final focused suite:
  `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/study/tests/test_backfill_question_fingerprints.py apps/parser/tests/test_question_identity.py apps/study/tests/test_json_import_dedup.py -q --basetemp .pt6final`
  - 31 passed.
- `C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check`
  - no issues.
- `git diff --check`
  - clean.

## Risks

- Historical records with a missing image file are skipped rather than given
  a partial fingerprint; the command reports them as errors for a later,
  source-aware repair.
- The management command is safe for normal single-process execution. It does
  not add a concurrent writer retry around registry creation, so concurrent
  backfill processes should not be run together.
