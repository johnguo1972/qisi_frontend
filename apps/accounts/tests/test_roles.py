import importlib
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import UserAccount, UserRole
from apps.accounts.roles import (
    get_user_roles,
    grant_user_role,
    has_user_role,
    revoke_user_role,
)


@pytest.fixture
def user(db):
    return UserAccount.objects.create(
        role_type="student",
        mobile="13900009999",
        display_name="Role Test User",
    )


def test_one_user_can_hold_all_four_roles_in_fixed_order(user):
    for role in ("student", "parent", "teacher", "admin"):
        grant_user_role(user, role)

    assert get_user_roles(user) == ["admin", "teacher", "parent", "student"]


def test_granting_an_active_role_is_idempotent(user):
    grant = grant_user_role(user, "teacher")

    repeated_grant = grant_user_role(user, "teacher")

    assert repeated_grant.pk == grant.pk
    assert UserRole.objects.filter(user=user, role="teacher").count() == 1


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


def test_revoke_marks_active_grant_inactive_and_ignores_missing_role(user):
    grant_user_role(user, "parent")

    revoked = revoke_user_role(user, "parent")

    assert revoked.status == "inactive"
    assert not has_user_role(user, "parent")
    assert revoke_user_role(user, "parent") is None


def test_user_role_helpers_delegate_to_role_service(user):
    grant_user_role(user, "student")

    assert user.get_roles() == ["student"]
    assert user.has_role("student")
    assert not user.has_role("teacher")


@pytest.mark.django_db(transaction=True)
def test_0003_imports_only_valid_normalized_legacy_roles_and_active_bindings():
    executor = MigrationExecutor(connection)
    executor.migrate([("accounts", "0002_wechatidentity")])
    legacy_apps = executor.loader.project_state(
        [("accounts", "0002_wechatidentity")]
    ).apps
    LegacyUser = legacy_apps.get_model("accounts", "UserAccount")
    LegacyBind = legacy_apps.get_model("accounts", "StudentParentBind")

    legacy_teacher = LegacyUser.objects.create(
        role_type="teacher", mobile="13900009101", display_name="Legacy Teacher"
    )
    normalized_student = LegacyUser.objects.create(
        role_type=" student ", mobile="13900009102", display_name="Normalized Student"
    )
    invalid_legacy_user = LegacyUser.objects.create(
        role_type="owner", mobile="13900009103", display_name="Invalid Legacy Role"
    )
    blank_legacy_user = LegacyUser.objects.create(
        role_type="   ", mobile="13900009104", display_name="Blank Legacy Role"
    )
    parent = LegacyUser.objects.create(
        role_type="owner", mobile="13900009105", display_name="Bound Parent"
    )
    student = LegacyUser.objects.create(
        role_type="owner", mobile="13900009106", display_name="Bound Student"
    )
    inactive_parent = LegacyUser.objects.create(
        role_type="owner", mobile="13900009107", display_name="Inactive Parent"
    )
    inactive_student = LegacyUser.objects.create(
        role_type="owner", mobile="13900009108", display_name="Inactive Student"
    )
    LegacyBind.objects.create(
        parent_user_id=parent,
        student_user_id=student,
        relation_type="guardian",
        bind_status="active",
    )
    LegacyBind.objects.create(
        parent_user_id=inactive_parent,
        student_user_id=inactive_student,
        relation_type="guardian",
        bind_status="pending",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("accounts", "0003_userrole")])
    migrated_apps = executor.loader.project_state(
        [("accounts", "0003_userrole")]
    ).apps
    MigratedUserRole = migrated_apps.get_model("accounts", "UserRole")

    assert set(
        MigratedUserRole.objects.values_list("user_id", "role", "grant_source")
    ) == {
        (legacy_teacher.pk, "teacher", "migration_0003"),
        (normalized_student.pk, "student", "migration_0003"),
        (parent.pk, "parent", "migration_0003"),
        (student.pk, "student", "migration_0003"),
    }
    assert not MigratedUserRole.objects.filter(user_id=invalid_legacy_user.pk).exists()
    assert not MigratedUserRole.objects.filter(user_id=blank_legacy_user.pk).exists()
    assert not MigratedUserRole.objects.filter(user_id=inactive_parent.pk).exists()
    assert not MigratedUserRole.objects.filter(user_id=inactive_student.pk).exists()

    current_teacher = UserAccount.objects.get(pk=legacy_teacher.pk)
    revoke_user_role(current_teacher, "teacher")
    business_regrant = grant_user_role(current_teacher, "teacher")
    assert business_regrant.grant_source == "business"

    migration_module = importlib.import_module("apps.accounts.migrations.0003_userrole")
    migration_module.remove_imported_role_grants(migrated_apps, None)

    assert MigratedUserRole.objects.filter(
        user_id=legacy_teacher.pk,
        role="teacher",
        grant_source="business",
    ).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("restore_inactive_grant", [False, True])
def test_concurrent_grants_are_idempotent_for_first_grant_and_restoration(
    restore_inactive_grant,
):
    user = UserAccount.objects.create(
        role_type="student",
        mobile="13900009200" if restore_inactive_grant else "13900009201",
        display_name="Concurrent Role User",
    )
    if restore_inactive_grant:
        grant_user_role(user, "teacher")
        revoke_user_role(user, "teacher")

    barrier = threading.Barrier(2)

    def concurrent_grant():
        close_old_connections()
        try:
            concurrent_user = UserAccount.objects.get(pk=user.pk)
            barrier.wait(timeout=5)
            return grant_user_role(concurrent_user, "teacher").pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        grant_ids = list(executor.map(lambda _: concurrent_grant(), range(2)))

    assert grant_ids[0] == grant_ids[1]
    assert UserRole.objects.filter(user=user, role="teacher").count() == 1
    assert UserRole.objects.get(user=user, role="teacher").status == "active"
