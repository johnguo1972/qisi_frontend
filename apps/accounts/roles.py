from django.db.models import Case, IntegerField, Value, When

from apps.accounts.models import UserRole


VALID_ROLES = ("admin", "teacher", "parent", "student")


def _validate_role(role):
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")


def get_user_roles(user):
    order = Case(
        *[When(role=role, then=Value(index)) for index, role in enumerate(VALID_ROLES)],
        output_field=IntegerField(),
    )
    return list(
        UserRole.objects.filter(user=user, status="active")
        .order_by(order)
        .values_list("role", flat=True)
    )


def has_user_role(user, role):
    _validate_role(role)
    return UserRole.objects.filter(user=user, role=role, status="active").exists()


def grant_user_role(user, role):
    _validate_role(role)
    grant, _ = UserRole.objects.update_or_create(
        user=user,
        role=role,
        defaults={"status": "active"},
    )
    return grant


def revoke_user_role(user, role):
    _validate_role(role)
    grant = UserRole.objects.filter(user=user, role=role, status="active").first()
    if grant is None:
        return None

    grant.status = "inactive"
    grant.save(update_fields=["status", "updated_at"])
    return grant
