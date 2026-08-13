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
