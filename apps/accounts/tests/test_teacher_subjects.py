import pytest

from apps.accounts.models import UserAccount
from apps.accounts.serializers import serialize_user_session


@pytest.mark.django_db
def test_legacy_subject_is_exposed_as_single_subject_list():
    user = UserAccount.objects.create(
        role_type="teacher",
        mobile="13900009501",
        display_name="Legacy Teacher",
        subject="physics",
    )

    payload = serialize_user_session(user, "teacher")

    assert payload["subject"] == "physics"
    assert payload["subjects"] == ["physics"]


@pytest.mark.django_db
def test_explicit_subject_list_is_preserved_in_session_payload():
    user = UserAccount.objects.create(
        role_type="teacher",
        mobile="13900009502",
        display_name="Multi Subject Teacher",
        subject="physics",
        subjects=["physics", "math"],
    )

    payload = serialize_user_session(user, "teacher")

    assert payload["subject"] == "physics"
    assert payload["subjects"] == ["physics", "math"]
