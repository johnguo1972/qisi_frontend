# Task 2 report: cached administrator page role guard

## RED evidence

Before the production change, ran:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q
```

Result: `5 failed, 3 passed`. The four executable Node role-helper contracts failed because `currentSessionRole` and `ensurePageRole` did not exist; the lifecycle contract failed because the admin page did not import or invoke `ensurePageRole`.

## Implementation

- Added `currentSessionRole()` with `active_role` precedence and `role_type` fallback.
- Added `ensurePageRole()` to permit matching roles, relaunch mismatched roles to `routeForRole`, and deny an absent role without navigation.
- Guarded both administrator lifecycle hooks before profile or institution requests; retained the existing `hasLoadedOnShow` initial-load behavior.
- Added executable Node contracts for helper behavior and lifecycle call ordering/load count.

## GREEN evidence

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
# 8 passed

C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q -p no:cacheprovider
# 9 passed

cd uniapp; npm run build:h5
# DONE Build complete.
```

## Commit

Pending at report creation; commit below contains only the explicit Task 2 paths.

## Self-review

- No backend permission or `/admin/institutions` API code changed.
- Valid admin first entry still loads institutions once; the first `onShow` only marks the lifecycle as initialized; a later valid `onShow` reloads.
- The dirty user-owned `.env` file was not staged or changed by this task.

## Concerns

- The H5 build prints existing toolchain update notices and `os - Alias not found` after reporting `DONE Build complete`; it exits successfully.
