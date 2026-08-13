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

## Review follow-up: executable handler coverage

### RED evidence

The reviewer found that `questionApi` has no `aiProcessProbe` member; the
existing `handleAiExplore()` would therefore throw at click time. The existing
API module instead exports the named `aiProcessProbe(questionId)` function.

The frontend contract was upgraded from source-text matching to a Node-executed
handler contract. It extracts each real handler body from the Vue SFC, binds
recording probe/batch APIs, invokes it, and asserts the observed calls/toasts.
The handler source is base64-transported to Node so Chinese toast labels remain
UTF-8 on Windows.

Before the production fix, the focused test produced the expected RED:

```text
1 failed, 2 passed
FAILED test_ai_explore_uses_named_probe_api_for_each_selected_question
assert None
```

The failing assertion required a named `aiProcessProbe` import from
`@/api/questions`; this is the missing callable dependency that caused the
reviewed runtime defect.

### Follow-up implementation

- Imported the existing named `aiProcessProbe` from `@/api/questions`.
- Changed only explore dispatch to `aiProcessProbe(id)` for every selected id.
- Kept `handleBatchAi()` unchanged.

The executable tests now cover: two selected IDs yield two probe calls and zero
batch calls; empty selection yields zero API calls; and batch AI still performs
one `batchAi(ids, model)` call with zero probe calls.

### GREEN evidence

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py tests/test_manual_ai_ui_contract.py -q
```

```text
.....................                                                    [100%]
21 passed in 5.86s
```

`npm run build:h5` was also re-run in `uniapp/` and ended with `DONE  Build
complete.` (exit code 0). The same chained attempt used an incorrect pytest
working directory and collected zero tests; it was not used as the GREEN
evidence above.

### Follow-up concerns

None. The pre-existing dirty `.env` remains unmodified and excluded.
