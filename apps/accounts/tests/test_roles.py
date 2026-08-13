import pytest

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
