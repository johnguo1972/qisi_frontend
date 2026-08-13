# Multi-Role Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow one account to hold admin, teacher, parent, and student roles concurrently, choose an authorized role at login, switch roles without overwriting other sessions, and hold both institution-admin and institution-teacher relationships.

**Architecture:** Store global grants in a normalized `UserRole` table and the current session role in JWT `active_role`. Keep `UserAccount.role_type` as a migration compatibility field only. Store institution roles as separate `InstitutionMember` rows keyed by institution, user, and role, while aggregating them into one member card at the API/UI boundary.

**Tech Stack:** Django 5.2, Django REST Framework, SimpleJWT, PostgreSQL, pytest, Vue 3, TypeScript, UniApp/Vite.

## Global Constraints

- Modify only files under `./front`.
- Preserve existing `.env`, media changes, `appdb_2026-07-31_171516.dump`, `docs/improve.md`, and pytest temporary directories; do not commit them.
- Global roles are exactly `admin`, `teacher`, `parent`, and `student`.
- Institution roles are exactly `admin` and `teacher`; institution admin does not imply global system admin.
- Login and role switching must never write `UserAccount.role_type`.
- JWT `active_role` is authoritative for the current session; role grants are revalidated on every authenticated request.
- Keep response field `role_type` equal to the active session role for frontend compatibility, and add `roles` plus `active_role`.
- Existing single-role accounts must continue to log in without a new interaction.
- Do not change AI, paper parsing, database credentials, or unrelated product behavior.
- Every implementation task follows RED → GREEN → focused regression → commit.

---

### Task 1: Add the global role grant model and migrate existing grants

**Files:**
- Modify: `apps/accounts/models.py`
- Create: `apps/accounts/roles.py`
- Create: `apps/accounts/migrations/0003_userrole.py`
- Create: `apps/accounts/tests/test_roles.py`

**Interfaces:**
- Produces: `VALID_ROLES`, `UserRole`, `get_user_roles(user) -> list[str]`, `has_user_role(user, role) -> bool`, `grant_user_role(user, role) -> UserRole`, and `revoke_user_role(user, role) -> UserRole | None`.
- Migration imports existing `UserAccount.role_type` and active `StudentParentBind` parent/student relationships. Institution and class relationships are imported in Task 3 after its constraint migration.

- [ ] **Step 1: Write failing role-domain tests**

Create tests that assert validation, ordering, idempotent grant, inactive-role restoration, revoke behavior, and model helpers:

```python
def test_one_user_can_hold_all_four_roles(user):
    for role in ("admin", "teacher", "parent", "student"):
        grant_user_role(user, role)
    assert get_user_roles(user) == ["admin", "teacher", "parent", "student"]


def test_grant_restores_inactive_role_without_duplicate(user):
    grant = grant_user_role(user, "teacher")
    revoke_user_role(user, "teacher")
    restored = grant_user_role(user, "teacher")
    assert restored.pk == grant.pk
    assert restored.status == "active"
    assert UserRole.objects.filter(user=user, role="teacher").count() == 1


def test_invalid_role_is_rejected(user):
    with pytest.raises(ValueError, match="invalid role"):
        grant_user_role(user, "owner")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_roles.py -q --basetemp=.pytest_multi_role_task1_red -p no:cacheprovider
```

Expected: collection/import failure because `UserRole` and `apps.accounts.roles` do not exist.

- [ ] **Step 3: Implement the model and focused role service**

Add the normalized model:

```python
class UserRole(models.Model):
    ROLE_CHOICES = [(role, role) for role in ("admin", "teacher", "parent", "student")]
    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="role_grants")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, default="active")
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_role"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uq_user_role_user_role"),
        ]
```

Keep all mutations in `apps/accounts/roles.py`, validate against `VALID_ROLES`, restore inactive rows with `update_or_create`, and return roles in the fixed order `admin`, `teacher`, `parent`, `student`. Add delegating `get_roles()` and `has_role()` methods on `UserAccount`; do not make callers manipulate the related manager directly.

- [ ] **Step 4: Create and inspect the schema/data migration**

Generate the schema migration, then add `RunPython` that creates an active grant for every nonblank current `role_type`, plus `parent`/`student` grants for active `StudentParentBind` rows. Reverse migration deletes only rows created by this migration through a deterministic role import; it must not change `UserAccount.role_type`.

Run:

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations accounts
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py sqlmigrate accounts 0003
```

Expected: one `user_role` table, one `(user_id, role)` unique constraint, and no alteration of `user_account.role_type`.

- [ ] **Step 5: Run GREEN tests and migration checks**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_roles.py -q --basetemp=.pytest_multi_role_task1_green -p no:cacheprovider
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations --check --dry-run
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check
```

Expected: all tests pass, no pending model changes, and no system-check issues.

- [ ] **Step 6: Commit Task 1**

```powershell
git add apps/accounts/models.py apps/accounts/roles.py apps/accounts/migrations/0003_userrole.py apps/accounts/tests/test_roles.py
git commit -m "feat: add multi-role account grants"
```

---

### Task 2: Make login, refresh, authentication, and switching session-role aware

**Files:**
- Modify: `apps/accounts/services.py`
- Modify: `apps/accounts/auth.py`
- Modify: `apps/accounts/serializers.py`
- Modify: `apps/accounts/views.py`
- Modify: `apps/accounts/urls.py`
- Modify: `apps/accounts/management/commands/create_admin.py`
- Create: `apps/accounts/tests/test_role_auth.py`

**Interfaces:**
- Consumes: Task 1 role helpers.
- Produces: `generate_tokens(user, active_role)`, `get_request_role(request)`, login response fields `roles`/`active_role`/compatible `role_type`, and `POST /api/v1/auth/switch-role`.

- [ ] **Step 1: Write failing authentication/security tests**

Cover these exact behaviors:

```python
def test_existing_user_login_does_not_overwrite_legacy_role(api_client, admin_user, sms_code):
    grant_user_role(admin_user, "teacher")
    response = api_client.post("/api/v1/auth/login", {
        "mobile": admin_user.mobile, "verify_code": sms_code, "role_type": "teacher",
    })
    admin_user.refresh_from_db()
    assert response.status_code == 200
    assert admin_user.role_type == "admin"
    assert response.data["data"]["user"]["active_role"] == "teacher"


def test_ungranted_admin_login_is_forbidden(api_client, student_user, sms_code):
    response = api_client.post("/api/v1/auth/login", {
        "mobile": student_user.mobile, "verify_code": sms_code, "role_type": "admin",
    })
    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"


def test_two_tokens_keep_independent_active_roles(api_client, admin_teacher):
    admin_tokens = generate_tokens(admin_teacher, "admin")
    teacher_tokens = generate_tokens(admin_teacher, "teacher")
    assert decode(admin_tokens["access_token"])["active_role"] == "admin"
    assert decode(teacher_tokens["access_token"])["active_role"] == "teacher"
```

Also test switch-role success/failure, refresh preserving the claim, role revoked after token issuance, and an old token without `active_role` falling back to the legacy field only when that grant exists.

- [ ] **Step 2: Run tests and verify RED**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_role_auth.py -q --basetemp=.pytest_multi_role_task2_red -p no:cacheprovider
```

Expected: failures show that login still mutates `role_type`, tokens lack `active_role`, and switch-role is unresolved.

- [ ] **Step 3: Separate account creation from role selection**

Replace the mutating `get_or_create_user()` contract with:

```python
def get_or_create_user(mobile: str, initial_role: str = "student") -> tuple[UserAccount, bool]:
    """Create a new account with one safe initial grant; never change an existing account's roles."""
```

For normal SMS login, only a brand-new account selecting `student` may self-create. Existing accounts must already have the requested role. WeChat binding may create `student` or `parent` accounts because it is the approved binding flow, but it must grant the selected role through `grant_user_role()` rather than overwrite `role_type`. Update `create_admin` to grant `admin` idempotently while retaining the legacy default field for a newly created admin.

- [ ] **Step 4: Put active role into tokens and request context**

Change token generation to require an authorized role:

```python
def generate_tokens(user: UserAccount, active_role: str) -> dict:
    if not has_user_role(user, active_role):
        raise RoleNotGranted(active_role)
    refresh = RefreshToken.for_user(user)
    refresh["active_role"] = active_role
    return {"access_token": str(refresh.access_token), "refresh_token": str(refresh)}
```

In `OptionalJWTAuthentication.authenticate()`, after `super()` returns `(user, validated_token)`, read and validate `active_role`; for a legacy token use `user.role_type` only if the corresponding active grant exists. Set `request.active_role` and set `user.role_type` on that request-loaded instance only for compatibility; never call `save()`.

Expose:

```python
def get_request_role(request) -> str | None:
    return getattr(request, "active_role", None)
```

- [ ] **Step 5: Implement session serialization and switch-role**

Centralize the response view so login, profile, WeChat login/bind, and switch-role agree:

```python
def serialize_user_session(user, active_role):
    data = ProfileSerializer(user).data
    data.update({
        "roles": get_user_roles(user),
        "active_role": active_role,
        "role_type": active_role,
    })
    return data
```

Add `POST /api/v1/auth/switch-role`, accept only a `role` in `VALID_ROLES`, return 400/`INVALID_ROLE` for invalid values, 403/`ROLE_NOT_GRANTED` for an ungranted role, and otherwise return new access/refresh tokens plus the session user view.

Update refresh handling to copy the refresh token's valid `active_role` to the new access token and reject revoked roles.

- [ ] **Step 6: Run Task 2 tests and focused auth regression**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_role_auth.py apps/qrcode/tests.py -q --basetemp=.pytest_multi_role_task2_green -p no:cacheprovider
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check
```

Expected: role-auth and WeChat tests pass; no role-selection path writes an existing user's legacy role.

- [ ] **Step 7: Commit Task 2**

```powershell
git add apps/accounts apps/qrcode/tests.py
git commit -m "feat: bind active roles to login sessions"
```

---

### Task 3: Support concurrent institution-admin and teacher relationships

**Files:**
- Modify: `apps/institutions/models.py`
- Modify: `apps/institutions/serializers.py`
- Modify: `apps/institutions/member_views.py`
- Create: `apps/institutions/migrations/0002_multi_role_memberships.py`
- Modify: `apps/institutions/tests.py`
- Modify: `uniapp/src/api/institutions.ts`

**Interfaces:**
- Consumes: `grant_user_role(user, "teacher")` from Task 1.
- Produces: institution member list items grouped by `user_id` with `roles: list[str]`; add/update operations are transactional and role-specific.

- [ ] **Step 1: Write failing institution multi-role tests**

Add request-level tests for the reported phone-independent scenario:

```python
def test_active_institution_admin_can_also_be_added_as_teacher(self):
    InstitutionMember.objects.create(
        institution=self.institution, user=self.platform_admin, role="admin", status="active",
    )
    response = self.client.post(self.members_url, {
        "mobile": self.platform_admin.mobile,
        "display_name": self.platform_admin.display_name,
        "role": "teacher",
    })
    assert response.status_code == 200
    assert list(InstitutionMember.objects.filter(
        institution=self.institution, user=self.platform_admin, status="active",
    ).values_list("role", flat=True).order_by("role")) == ["admin", "teacher"]
    assert has_user_role(self.platform_admin, "admin")
    assert has_user_role(self.platform_admin, "teacher")
```

Also assert one aggregated list item, duplicate teacher add is idempotent, reactivation works, adding institution admin does not grant global admin, editing selected roles applies a set diff, and removing a member deactivates both rows.

- [ ] **Step 2: Run tests and verify RED**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/institutions/tests.py -q -k "member" --basetemp=.pytest_multi_role_task3_red -p no:cacheprovider
```

Expected: the second relationship is blocked by the old unique constraint or returned without persistence.

- [ ] **Step 3: Change the institution relationship constraint and import relationship roles**

Replace `unique_together = ('institution', 'user')` with an explicit `(institution, user, role)` unique constraint. The migration must:

1. Alter the constraint.
2. Add global `teacher` grants for active institution teachers.
3. Add global `student` grants for active `ClassStudent` rows.

Use historical models through `apps.get_model()` and `update_or_create`; do not grant global admin from institution-admin rows.

- [ ] **Step 4: Make member create/update transactional and aggregate list output**

Use `transaction.atomic()` around member role changes and teacher grant creation. `AddMemberSerializer.create()` must call:

```python
member, _ = InstitutionMember.objects.update_or_create(
    institution=institution,
    user=user,
    role=role,
    defaults={"status": "active"},
)
if role == "teacher":
    grant_user_role(user, "teacher")
```

Do not update an existing user's `role_type`. Group list rows by user and return `roles` in the fixed institution order `admin`, `teacher`. Change update payload to `roles?: Array<'admin' | 'teacher'>`; apply additions/restorations and deactivate omitted roles in one transaction. Preserve `role` in single-role add requests for compatibility.

- [ ] **Step 5: Run GREEN tests and migration checks**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/institutions/tests.py -q --basetemp=.pytest_multi_role_task3_green -p no:cacheprovider
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations --check --dry-run
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check
```

Expected: all institution tests pass and no model drift remains.

- [ ] **Step 6: Commit Task 3**

```powershell
git add apps/institutions uniapp/src/api/institutions.ts
git commit -m "feat: support multiple institution roles"
```

---

### Task 4: Grant derived roles and convert permission checks to session roles

**Files:**
- Modify: `apps/institutions/permissions.py`
- Modify: `apps/institutions/member_views.py`
- Modify: `apps/institutions/request_views.py`
- Modify: `apps/institutions/serializers.py`
- Modify: `apps/institutions/class_views.py`
- Modify: `apps/missions/views.py`
- Modify: `apps/study/permissions.py`
- Modify: `apps/qrcode/views.py`
- Modify: `apps/accounts/apps.py`
- Create: `apps/accounts/signals.py`
- Modify: `apps/institutions/apps.py`
- Create: `apps/institutions/signals.py`
- Modify: `apps/institutions/tests.py`
- Modify: `apps/qrcode/tests.py`
- Create: `tests/test_multi_role_permissions.py`

**Interfaces:**
- Consumes: `get_request_role()`, `has_user_role()`, and `grant_user_role()`.
- Produces: all privileged request checks use the JWT session role; student/parent/teacher grants are applied by approved relationship flows.

- [ ] **Step 1: Add failing permission and auto-grant tests**

Add focused tests proving:

- an admin-active token cannot use teacher-only behavior solely because the account also owns teacher;
- a teacher-active token cannot use platform-admin endpoints;
- institution admin membership does not grant platform admin;
- approving a class join grants `student` without removing other roles;
- direct join-by-code grants `student`;
- active parent binding grants both the parent and student roles;
- database user filters no longer exclude multi-role students because their legacy `role_type` is admin or teacher.

- [ ] **Step 2: Run the focused tests and verify RED**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/institutions/tests.py apps/study/tests apps/qrcode/tests.py apps/missions/tests -q -k "role or permission or join or parent" --basetemp=.pytest_multi_role_task4_red -p no:cacheprovider
```

Expected: failures identify direct `request.user.role_type` and `role_type='student'` assumptions.

- [ ] **Step 3: Replace request-role permission checks**

Use `get_request_role(request)` for the session role. Preserve relationship checks:

```python
class IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and get_request_role(request) == "admin"
            and has_user_role(request.user, "admin")
        )
```

Teacher checks require `active_role == 'teacher'` plus active `InstitutionMember(role='teacher')` or `ClassTeacher`. Student and parent checks require their session role plus the existing class/bind relationship. Do not treat owning several roles as permission to act in all of them during one request.

- [ ] **Step 4: Grant roles at relationship boundaries and fix role-based queries**

Register two narrow `post_save` receivers through each app config's `ready()` method:

```python
@receiver(post_save, sender=ClassStudent)
def grant_student_role_for_active_membership(sender, instance, **kwargs):
    if instance.status == "active":
        grant_user_role(instance.student, "student")


@receiver(post_save, sender=StudentParentBind)
def grant_roles_for_active_parent_bind(sender, instance, **kwargs):
    if instance.bind_status == "active":
        grant_user_role(instance.student_user_id, "student")
        grant_user_role(instance.parent_user_id, "parent")
```

This covers serializer, request-approval, import, shell, and future service creation paths uniformly. Teacher institution add remains handled transactionally by Task 3. Receivers are idempotent because `(user, role)` is unique.

Replace query filters such as `UserAccount.objects.filter(..., role_type='student')` with relationship membership or `role_grants__role='student', role_grants__status='active'`, using `distinct()` where joins can duplicate rows.

- [ ] **Step 5: Run GREEN permission regressions**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/institutions/tests.py apps/study/tests apps/qrcode/tests.py apps/missions/tests -q --basetemp=.pytest_multi_role_task4_green -p no:cacheprovider
```

Expected: all selected suites pass with session role isolation.

- [ ] **Step 6: Audit production role checks**

```powershell
rg -n "request\.user\.role_type|role_type='student'|role_type=\"student\"" apps --glob '*.py' --glob '!**/tests/**' --glob '!**/migrations/**'
```

Expected: no authorization or role-membership query remains; any compatibility serialization reference must be explained in the task report.

- [ ] **Step 7: Commit Task 4**

```powershell
git add apps/institutions apps/missions apps/study apps/qrcode
git commit -m "fix: enforce active role permissions"
```

---

### Task 5: Add multi-role institution editing and in-app identity switching

**Files:**
- Create: `uniapp/src/utils/roles.ts`
- Create: `uniapp/src/components/RoleSwitcher.vue`
- Modify: `uniapp/src/api/index.ts`
- Modify: `uniapp/src/pages/login/index.vue`
- Modify: `uniapp/src/pages/admin/institution-detail.vue`
- Modify: `uniapp/src/pages/admin/home.vue`
- Modify: `uniapp/src/components/TeacherSidebar.vue`
- Modify: `uniapp/src/components/StudentSidebar.vue`
- Modify: `uniapp/src/components/MpDrawer.vue`
- Modify: `uniapp/src/App.vue`
- Create: `tests/test_multi_role_frontend_contract.py`

**Interfaces:**
- Consumes: `roles`, `active_role`, and `POST /auth/switch-role` from Task 2; aggregated institution `roles` from Task 3.
- Produces: shared `switchToRole(role)` and `routeForRole(role)` helpers plus a reusable role picker.

- [ ] **Step 1: Write failing static frontend contracts**

Create tests that assert:

- the login page navigates using `active_role` and never assumes a selected tab was granted;
- `authApi.switchRole(role)` calls `/auth/switch-role`;
- `RoleSwitcher.vue` renders only `userInfo.roles` and stores all returned tokens/session fields;
- admin, teacher, H5 student, and MP drawer surfaces include the switcher;
- institution detail uses `roles` checkboxes, displays both tags, labels `admin` as “机构管理员”, and does not contain “系统管理员” in institution-role controls.

- [ ] **Step 2: Run contract tests and verify RED**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q --basetemp=.pytest_multi_role_task5_red -p no:cacheprovider
```

Expected: failures for missing switch API/component and single-role institution controls.

- [ ] **Step 3: Implement centralized role routing and switching**

In `roles.ts`, define exact routing and storage behavior:

```ts
export type AppRole = 'admin' | 'teacher' | 'parent' | 'student'

export function routeForRole(role: AppRole): string {
  if (role === 'admin') return '/pages/admin/home'
  if (role === 'teacher') return '/pages/teacher/layout'
  let studentRoute = '/pages/student/layout'
  // #ifdef MP-WEIXIN
  studentRoute = '/pages/student/mp-home'
  // #endif
  return studentRoute
}

export function persistSession(data: any): void {
  uni.setStorageSync('accessToken', data.access_token)
  uni.setStorageSync('refreshToken', data.refresh_token)
  uni.setStorageSync('userInfo', data.user)
}
```

`RoleSwitcher.vue` reads `roles` and `active_role`, hides when only one role exists, calls `authApi.switchRole`, persists the response, updates the user store, and `reLaunch`es to `routeForRole()`.

- [ ] **Step 4: Make login use server-authorized session data**

Keep four tabs, but after login navigate by `res.data.user.active_role`. For `ROLE_NOT_GRANTED`, display “该账号未开通此角色”. Do not alter tabs based on an unauthenticated mobile lookup, avoiding account-role enumeration.

Replace duplicated `navigateByRole()` implementations in the login page and `App.vue` with `routeForRole()`.

- [ ] **Step 5: Convert institution member UI to multi-select roles**

Use `roles: string[]` in member cards and edit form. Render one badge per role, with labels “机构管理员” and “教师”. The edit modal has two checkboxes and sends the complete selected roles array. Require at least one selected role while editing; “移除成员” remains the explicit operation for removing all roles. Show teacher subject/stages only when `roles.includes('teacher')`.

- [ ] **Step 6: Run frontend contracts and build**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest tests/test_multi_role_frontend_contract.py -q --basetemp=.pytest_multi_role_task5_green -p no:cacheprovider
Set-Location uniapp
npm run build:h5
```

Expected: contract passes and build prints `DONE Build complete` with exit code 0.

- [ ] **Step 7: Commit Task 5**

```powershell
git add uniapp/src tests/test_multi_role_frontend_contract.py
git commit -m "feat: add multi-role identity switching"
```

---

### Task 6: Apply migrations, repair the requested local account, and run final regression

**Files:**
- No planned source modification; a verified regression failure must stop this task and open a focused RED/GREEN fix against the file that owns the failing behavior.
- Runtime state: local PostgreSQL `appdb`

**Interfaces:**
- Consumes: all Tasks 1-5.
- Produces: migrated local data and data-bearing proof that phone `13316529181` owns admin and teacher roles and both institution relations remain visible.

- [ ] **Step 1: Run full migration checks before applying**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations --check --dry-run
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py migrate --plan
```

Expected: only the reviewed accounts/institutions migrations are pending.

- [ ] **Step 2: Apply local migrations**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py migrate --noinput
```

Expected: both new migrations report `OK`.

- [ ] **Step 3: Repair the explicitly requested local account without hardcoding it in migrations**

Run a Django shell operation inside `transaction.atomic()` that:

1. Loads the account by exact mobile `13316529181`.
2. Confirms it already has global `admin` and an active institution-admin row.
3. Grants global `teacher` idempotently.
4. Creates/restores `InstitutionMember(role='teacher')` for each institution where it has an active admin relationship.
5. Prints only user id, role names, institution ids, and statuses; never prints credentials or tokens.

Abort without mutation if the account is missing or has no active institution-admin relationship.

- [ ] **Step 4: Run backend regression**

```powershell
C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts apps/institutions apps/missions apps/study apps/qrcode tests/test_multi_role_frontend_contract.py -q --basetemp=.pytest_multi_role_final -p no:cacheprovider
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check
C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py migrate --plan
```

Expected: zero failures, no system-check issues, and no pending migrations.

- [ ] **Step 5: Run frontend build and static security audit**

```powershell
Set-Location uniapp
npm run build:h5
Set-Location ..
rg -n "request\.user\.role_type|updating role_type on each login|user\.role_type = role_type" apps --glob '*.py' --glob '!**/tests/**' --glob '!**/migrations/**'
git diff --check
```

Expected: H5 build succeeds; no login mutation or direct current-role authorization remains; diff check is clean.

- [ ] **Step 6: Verify the data-bearing acceptance state**

Use ORM and the institution member list API to prove:

- `13316529181` has active global roles `admin` and `teacher`;
- it has active institution rows `admin` and `teacher` for the target institution;
- the member list returns one user card with `roles == ['admin', 'teacher']`;
- an admin token can access an admin endpoint;
- a teacher token can access the account's teacher institutions;
- neither token changes `UserAccount.role_type` in the database.

Do not claim browser E2E unless a real browser session is run. API/ORM evidence must be reported separately from build evidence.

- [ ] **Step 7: Inspect scope and request final independent review**

```powershell
git status --short
git diff --name-only 06291b7..HEAD
git log --oneline 06291b7..HEAD
```

Confirm all changed paths are under `front`, and `.env`, media, dump, `docs/improve.md`, and pytest temp directories remain uncommitted. Provide the reviewer the design, this plan, commit range, test outputs, migration evidence, and the static audit. Require Critical/Important/Minor findings and a GO/NO-GO verdict.

- [ ] **Step 8: Commit any final test/documentation-only changes**

If Step 4 or Step 5 required no code fix, do not create an empty commit. If test documentation was added, stage only those explicit paths and use:

```powershell
git commit -m "test: verify multi-role account flows"
```
