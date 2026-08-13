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

## Fix round 1: review NO-GO remediation

### Root cause and RED evidence

The original guard ran only at lifecycle entry. A pending `getProfile()` could persist a changed active role before the later institution request, and concurrent `onShow` calls each invoked the loader independently. `currentSessionRole()` also trusted arbitrary stored strings, so an invalid role was routed through the student fallback.

Added executable Node lifecycle scenarios, then ran:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
```

RED: `3 failed, 8 passed`: invalid `operator` role relaunched to the student route; delayed profile role change produced two institution requests; concurrent valid admin `onShow` calls produced three requests (initial plus two reloads).

### Implementation

- Whitelisted the four supported stored roles; other values are treated as absent.
- Added shared `initializeAdminHome()` so mounted and subsequent show paths await the same profile/load initialization.
- Made `loadInstitutions()` single-flight and guarded it both on entry and immediately before `institutionApi.list()`.
- Rechecked the active role after profile persistence and before the initial institution request.

### GREEN evidence

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
# 10 passed

C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q -p no:cacheprovider
# 9 passed

cd uniapp; npm run build:h5
# DONE Build complete.
```

### Self-review

- Delayed Promise tests execute extracted lifecycle and loader bodies, including profile persistence and concurrent requests; they assert zero institution calls after a role change and one shared reload for concurrent valid calls.
- No backend permission or endpoint path changed.

## Fix round 2: stale async response remediation

### RED evidence

Added executable delayed-Promise contracts. Before this change they failed as expected: a stale profile response restored `admin` and triggered one list call after the stored session had changed to teacher; an in-flight list response wrote stale items after a teacher switch; a rejected profile left `initializationPromise` settled and blocked the second attempt.

### Implementation

- Added token-and-role session snapshots around profile and institution requests.
- Drops stale profile/list responses before store or UI writes, and rechecks the administrator role before using a list response.
- Clears `initializationPromise` in `finally`, while keeping concurrent callers attached to the same in-flight promise.

### GREEN evidence

The regular pytest process was blocked by an existing locked Django test database (`test_appdb`), so the same executable contracts were run directly without pytest collection:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -c "import runpy; tests=runpy.run_path('tests/test_teacher_ai_explore_frontend.py'); [tests[name]() for name in tests if name.startswith('test_')]; print('13 direct contracts passed')"
# 13 direct contracts passed

C:\Users\johng\miniconda3\envs\ai-tools\python.exe -c "import runpy; tests=runpy.run_path('tests/test_multi_role_frontend_contract.py'); [tests[name]() for name in tests if name.startswith('test_')]; print('9 direct multi-role contracts passed')"
# 9 direct multi-role contracts passed

cd uniapp; npm run build:h5
# DONE Build complete.
```
