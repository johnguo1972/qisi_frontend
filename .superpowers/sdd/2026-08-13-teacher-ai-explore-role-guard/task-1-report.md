# Task 1 Report: Correct teacher AI explore dispatch

## RED evidence

Added `tests/test_teacher_ai_explore_frontend.py`, which extracts both
`handleAiExplore()` and `handleBatchAi()` from `question-bank.vue` and checks
the observable dispatch/toast contracts.

Focused command:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q
```

Observed RED before production changes:

```text
AssertionError
assert 'handleBatchAi(' not in explore_body
```

This identifies the original one-line delegation as the failing behavior.

## Implementation summary

Changed only `handleAiExplore()` so it rejects an empty selection, submits one
`questionApi.aiProcessProbe(id)` call per selected id, and displays the
required success/failure toasts. `handleBatchAi()` was left unchanged and
retains its existing `questionApi.batchAi(selectedQuestionIds.value, model)`
call.

## GREEN evidence

Focused and relevant frontend contract command after the change:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py tests/test_manual_ai_ui_contract.py -q
```

Output:

```text
...................                                                      [100%]
19 passed in 5.70s
```

Relevant frontend build:

```powershell
cd uniapp; npm run build:h5
```

Output ended with `DONE  Build complete.` and exit code 0.

## Self-review

- The new contract fails if probe dispatch is replaced with batch dispatch,
  if selection validation/toasts are removed, or if the unchanged batch
  handler stops calling `batchAi` with the selected ids and model.
- `git diff --check` completed without whitespace errors.
- The pre-existing dirty `.env` was preserved and excluded from the commit.

## Commit

`fix(teacher): use probe AI for explore action`

## Concerns

- Focused and relevant frontend contracts plus the UniApp H5 compilation
  succeeded; no remaining task-specific concern.
