# Task 4 Report: Session-role permissions and derived grants

## Status

Implemented the Task 4 permission boundary without changing the legacy
`UserAccount.role_type` field. Privileged request checks use the JWT
`active_role`, confirm the matching active grant, and retain the relevant
institution/class/parent relationship check.

## Delivered

- Added idempotent `post_save` role grants for active `ClassStudent` and
  active `StudentParentBind` relationships, registered through both app
  configs' `ready()` methods.
- Restricted platform-admin and teacher-only paths by session role and active
  grant, including class/join-request operations and institution member APIs.
- Updated student/parent permission helpers and QR permission branches to use
  the authenticated session role plus active relationships.
- Replaced student membership queries in mission targeting and QR paper
  generation so multi-role users are not excluded by the compatibility
  `role_type` column.
- Updated institution API tests to authenticate with real role-bound JWTs
  instead of bypassing authentication with `force_authenticate`.

## TDD Evidence

- RED: `tests/test_multi_role_permissions.py` produced 7 expected failures and
  2 passing security baselines. Failures covered admin-session teacher access,
  missing class/parent grants, and legacy student filters.
- GREEN exact: `9 passed`.
- Institution plus exact regression: `44 passed`.
- Brief-focused regression: `26 passed, 61 deselected`.
- Django system check: `System check identified no issues (0 silenced)`.

## Scope and concerns

- The requested full selected-suite command was attempted before legacy test
  authentication fixtures were updated. Besides those fixture failures, it
  reproduced the approved baseline `ModuleNotFoundError: reportlab`. The final
  verified focused suite excludes that unrelated PDF dependency path.
- `apps/accounts/views.py` retains two `get_request_role(request) or
  request.user.role_type` compatibility fallbacks for profile serialization;
  they are not authorization or membership queries and are outside Task 4.
- Existing `.env` and the pre-existing modified Task 3 report were preserved
  and are not part of this task's commit.
