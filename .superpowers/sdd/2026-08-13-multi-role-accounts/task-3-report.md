# Task 3 Report

Status: complete

Implemented:

- Institution memberships are unique by institution, user, and role.
- The migration grants active institution teachers the global teacher role and active class students the global student role; institution admins are not promoted to global admins.
- Member add and restore are role-specific and idempotent, with teacher grants in the same transaction.
- Member lists aggregate relationships by user and return roles in admin, teacher order.
- Member updates apply the complete roles set as a transactional set diff; removal deactivates every institution role for that user.
- Existing UserAccount.role_type values are not updated.
- UniApp institution API types now expose aggregated roles and roles-based updates; Task 5 UI was not changed.

Verification:

- RED: `pytest apps/institutions/tests.py -q -k "member"` produced 7 expected failures against the old single-role behavior.
- GREEN: `pytest apps/institutions/tests.py -q` -> 30 passed.
- `manage.py makemigrations --check --dry-run` -> No changes detected.
- `manage.py check` -> no issues.

Concerns:

- The existing institution detail UI still submits the legacy single `role` update shape; Task 5 is responsible for switching it to the new `roles` payload.
- The user-owned `.env` modification remains uncommitted and untouched.

## Fix round 1

- Duplicate-mobile validation now occurs before institution-role writes, so a
  failed member update leaves relationships and profile fields unchanged.
- Member filters determine which users are selected, while every returned
  `roles` value is rebuilt from the user's complete active institution roles in
  fixed `admin`, `teacher` order. Removed relationships never appear in roles.
- Update responses prefer an active relationship row instead of lexical status
  ordering, keeping the compatibility `role` and `status` fields aligned with
  active roles.
- A real MigrationExecutor rollback test proves that reversing institutions
  0002 restores the former one-role-per-user constraint and preserves imported
  global teacher/student grants.

Approved rollback semantics: global role grants are intentionally not revoked
on reverse. Their source can overlap with other institutions, classes, or later
business grants, and migration 0002 has no per-relationship provenance that
would make deletion safe. Constraint reversal is automatic; grant reversal is
therefore intentionally irreversible.
