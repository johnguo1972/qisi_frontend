# Task 5 Report

## Status

Complete.

## Implementation

- Added centralized role routing and session persistence in `uniapp/src/utils/roles.ts`.
- Added `RoleSwitcher.vue`, limited to the roles granted by `userInfo.roles`, with fresh access/refresh token and user-session persistence after switching.
- Added the switch-role API and identity-switch entries for admin, teacher, H5 student, and MP drawer surfaces.
- Updated login and app launch navigation to use the server-provided `active_role` through the shared route helper; login displays `该账号未开通此角色` for `ROLE_NOT_GRANTED`.
- Updated institution member management to render one card per user with multiple role badges, use the `机构管理员` label, submit a complete non-empty `roles` array, and conditionally show teacher profile fields.

## Verification

```text
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q --basetemp=.pytest_multi_role_task5_green -p no:cacheprovider
6 passed in 6.18s

npm run build:h5
DONE  Build complete.
```

## Concerns

- Verification is limited to the static frontend contracts and H5 production build required by the task; no live backend/browser identity-switch E2E was run.

## Fix round 1

- Converted the add-member form to a non-empty `roles` multi-select while keeping mobile/name/role controls always visible and showing subject/stages only for teachers.
- Added `institutionApi.addMemberRoles`, which calls the legacy single-role add endpoint in deterministic order and exposes partial completion so the UI can warn and refresh after partial failure.
- Added centralized executable `normalizeRoles`/`normalizeMember` functions and normalized member-list responses before rendering, including legacy `role`-only responses.
- Preserved legacy cached sessions in `App.vue` with `active_role || role_type`, while continuing to prefer `active_role`.

Verification:

```text
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q --basetemp=.pytest_multi_role_task5_fix1_green -p no:cacheprovider
9 passed in 8.71s

npm run build:h5
DONE  Build complete.
```

Concern: multi-role creation is necessarily non-transactional because the unchanged backend add endpoint accepts one role per request; partial completion is surfaced and the member list is refreshed.
