# Teacher AI Explore Role Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make teacher “AI探索” submit probe-only tasks and prevent cached non-admin pages from calling administrator institution APIs.

**Architecture:** Keep backend administrator authorization strict. Correct the teacher page at its action source, and add a reusable frontend session-role guard used before administrator page lifecycle requests.

**Tech Stack:** UniApp Vue 3, TypeScript, Vitest/Node-compatible frontend contract tests, pytest, Vite H5 build.

## Global Constraints

- Modify only files under `front/`.
- “AI探索” runs probe-only processing for explicitly selected questions.
- “批量AI” retains the existing complete AI pipeline.
- Do not weaken `/admin/institutions` backend permissions.
- Active role uses `active_role` with legacy `role_type` fallback.
- Preserve the user's existing `.env`, media, dump, and `docs/improve.md` changes.

---

### Task 1: Correct teacher AI explore dispatch

**Files:**
- Modify: `uniapp/src/pages/teacher/question-bank.vue`
- Test: `tests/test_teacher_ai_explore_frontend.py`

**Interfaces:**
- Consumes: `questionApi.aiProcessProbe(questionId)` and `questionApi.batchAi(questionIds, model)`.
- Produces: `handleAiExplore()` that submits only probe jobs; unchanged `handleBatchAi()` complete processing.

- [ ] **Step 1: Write the failing contract test**

Create a test that reads `question-bank.vue`, extracts the two handlers, and asserts:

```python
assert "questionApi.aiProcessProbe" in explore_handler
assert "handleBatchAi" not in explore_handler
assert "questionApi.batchAi" in batch_handler
```

Also assert the explore handler rejects an empty selection and uses all selected IDs.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py -q -p no:cacheprovider
```

Expected: failure because `handleAiExplore()` delegates to `handleBatchAi()`.

- [ ] **Step 3: Implement the minimal probe-only handler**

Change `handleAiExplore()` to:

```ts
async function handleAiExplore() {
  if (!selectedQuestionIds.value.length) {
    uni.showToast({ title: '请先选择题目', icon: 'none' })
    return
  }
  try {
    await Promise.all(selectedQuestionIds.value.map(id => questionApi.aiProcessProbe(id)))
    uni.showToast({ title: 'AI探索任务已提交', icon: 'success' })
  } catch {
    uni.showToast({ title: 'AI探索提交失败', icon: 'none' })
  }
}
```

Do not modify `handleBatchAi()`.

- [ ] **Step 4: Run the test and verify GREEN**

Run the command from Step 2. Expected: pass.

---

### Task 2: Guard cached administrator pages by active role

**Files:**
- Modify: `uniapp/src/utils/roles.ts`
- Modify: `uniapp/src/pages/admin/home.vue`
- Test: `tests/test_teacher_ai_explore_frontend.py`

**Interfaces:**
- Produces: `currentSessionRole(): AppRole | undefined` reading `active_role || role_type`.
- Produces: `ensurePageRole(expectedRole: AppRole): boolean`, returning true only for the expected role; otherwise `uni.reLaunch({url: routeForRole(currentRole)})` and returning false.
- Consumes: the guard in administrator `onMounted` and `onShow` before `getProfile()` or `loadInstitutions()`.

- [ ] **Step 1: Add failing role-guard tests**

Assert the utility prefers `active_role`, falls back to `role_type`, and admin page lifecycle code returns before institution loading when `ensurePageRole('admin')` is false. Assert the administrator API URL remains unchanged and no backend permission file is modified.

- [ ] **Step 2: Run the focused test and verify RED**

Run the Task 1 test command. Expected: failure because the guard does not exist.

- [ ] **Step 3: Implement role helpers and lifecycle guards**

Add to `roles.ts`:

```ts
export function currentSessionRole(): AppRole | undefined {
  const user = uni.getStorageSync('userInfo') || {}
  return (user.active_role || user.role_type) as AppRole | undefined
}

export function ensurePageRole(expectedRole: AppRole): boolean {
  const currentRole = currentSessionRole()
  if (currentRole === expectedRole) return true
  if (currentRole) uni.reLaunch({ url: routeForRole(currentRole) })
  return false
}
```

In admin `onMounted` and `onShow`, call `ensurePageRole('admin')` first and return if false. Preserve the existing one-initial-load behavior so `onMounted` and first `onShow` do not duplicate requests.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 1 test command. Expected: all pass.

---

### Task 3: Regression, build, review, and commit

**Files:**
- Test: `tests/test_teacher_ai_explore_frontend.py`
- Verify: all modified frontend files

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: verified main-worktree fix ready for local use.

- [ ] **Step 1: Run relevant regression tests**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_teacher_ai_explore_frontend.py tests/test_multi_role_frontend_contract.py apps/common/ai/tests/test_review_compatibility.py -q -p no:cacheprovider
```

Expected: zero failures.

- [ ] **Step 2: Run H5 production build**

```powershell
Set-Location uniapp
npm run build:h5
Set-Location ..
```

Expected: `DONE Build complete.`

- [ ] **Step 3: Inspect scope and diff hygiene**

```powershell
git diff --check
git status --short
git diff --name-only
```

Expected: source changes only in the planned `front/` files; user-owned dirty paths remain unstaged.

- [ ] **Step 4: Request independent review**

Reviewer must verify the two root causes are closed, administrator backend permission is unchanged, and no lifecycle duplicate request remains. Critical/Important findings block completion.

- [ ] **Step 5: Commit explicit paths only**

```powershell
git add tests/test_teacher_ai_explore_frontend.py uniapp/src/pages/teacher/question-bank.vue uniapp/src/pages/admin/home.vue uniapp/src/utils/roles.ts
git commit -m "fix: correct teacher AI explore flow"
```
