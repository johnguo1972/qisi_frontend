# Final fix report: teacher AI explore and administrator role guard

## Root cause

`initializeAdminHome()` loaded the institution list after preparing the profile. A subsequent `onShow` awaited that initializer and then called `loadInstitutions()` again. Because the initializer's first list request had already completed and cleared its single-flight promise, the second call became a separate serial request.

The prior tests invoked initializer and loader functions directly but no longer executed the real `onMounted`/`onShow` bodies in order, so this regression was not observable. The stale-response guard also covered successful responses only; a rejected request from an obsolete administrator session still displayed a toast and changed `loading`.

## RED evidence

Before the production change:

```powershell
$env:DB_NAME='teacher_ai_guard_finalfix'
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
```

Result: `3 failed, 13 passed`.

- A later `onShow` produced 3 total list requests instead of 2 (one initial plus one refresh).
- Three concurrent later `onShow` calls produced 3 total requests instead of 2.
- A rejected list request after switching to teacher emitted an administrator failure toast and changed `loading`.

## Minimal implementation

- `initializeAdminHome()` now only prepares and persists the current profile/session state.
- `onMounted` and later `onShow` each perform one guarded institution-list load after initialization.
- Existing `institutionsLoadPromise` still coalesces concurrent refreshes.
- The list request captures its session snapshot once. Its rejected stale-session branch neither emits a toast nor changes page loading state; the promise is still released in `finally`.
- Added an executable rejected-probe contract proving `AI探索提交失败` is shown when a probe request rejects.

## GREEN evidence

```powershell
$env:DB_NAME='teacher_ai_guard_finalfix'
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
# 16 passed

C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py tests/test_multi_role_frontend_contract.py apps/common/ai/tests/test_review_compatibility.py -q -p no:cacheprovider
# 51 passed

cd uniapp
npm run build:h5
# DONE Build complete. (exit 0)
```

## Scope and concerns

- No backend permission, endpoint, or `.env` change is included.
- Token-and-role snapshots deliberately remain unchanged. A theoretical exact ABA transition (token and role both change away and then back to identical values during one request) is not detectable without a shared storage-generation mechanism; adding that global mechanism was outside this minimal final fix.
- H5 build retains the existing non-fatal `os - Alias not found` message after `DONE Build complete.`
