import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.models import UserAccount, UserRole, WechatIdentity
from apps.accounts.roles import (
    get_user_roles,
    grant_user_role,
    has_user_role,
    revoke_user_role,
)
from apps.accounts.services import RoleNotGranted, generate_tokens


@pytest.fixture
def sms_code():
    return "123456"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return UserAccount.objects.create(
        role_type="admin",
        mobile="13900009311",
        display_name="Admin",
    )


@pytest.fixture
def teacher_user(db):
    return UserAccount.objects.create(
        role_type="teacher",
        mobile="13900009312",
        display_name="Teacher",
    )


@pytest.fixture
def student_user(db):
    return UserAccount.objects.create(
        role_type="student",
        mobile="13900009313",
        display_name="Student",
    )


@pytest.fixture
def admin_teacher(db):
    user = UserAccount.objects.create(
        role_type="admin",
        mobile="13900009301",
        display_name="Admin Teacher",
    )
    grant_user_role(user, "admin")
    grant_user_role(user, "teacher")
    return user


def _set_sms_code(user, code):
    cache.set(f"sms_code:{user.mobile}", code, timeout=180)


def _authenticate(client, access_token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")


@pytest.mark.django_db
@override_settings(
    TEST_LOGIN_ENABLED=True,
    TEST_LOGIN_PHONE="15800010001",
    TEST_LOGIN_CODE="651234",
)
def test_fixed_test_account_code_creates_and_grants_all_roles(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        {"mobile": "15800010001", "verify_code": "651234", "role_type": "teacher"},
    )

    assert response.status_code == 200
    user = UserAccount.objects.get(mobile="15800010001")
    assert get_user_roles(user) == ["admin", "teacher", "parent", "student"]
    assert response.data["data"]["user"]["active_role"] == "teacher"


@pytest.mark.django_db
@override_settings(
    TEST_LOGIN_ENABLED=True,
    TEST_LOGIN_PHONE="15800010001",
    TEST_LOGIN_CODE="651234",
)
def test_fixed_test_account_rejects_an_incorrect_code(api_client):
    response = api_client.post(
        "/api/v1/auth/login",
        {"mobile": "15800010001", "verify_code": "000000", "role_type": "student"},
    )

    assert response.status_code == 400
    assert response.data["code"] == 4001
    assert not UserAccount.objects.filter(mobile="15800010001").exists()


@pytest.mark.django_db
def test_existing_user_login_does_not_overwrite_legacy_role(
    api_client, admin_user, sms_code
):
    grant_user_role(admin_user, "admin")
    grant_user_role(admin_user, "teacher")
    _set_sms_code(admin_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": admin_user.mobile,
            "verify_code": sms_code,
            "role_type": "teacher",
        },
    )

    admin_user.refresh_from_db()
    assert response.status_code == 200
    assert admin_user.role_type == "admin"
    assert response.data["data"]["user"]["roles"] == ["admin", "teacher"]
    assert response.data["data"]["user"]["active_role"] == "teacher"
    assert response.data["data"]["user"]["role_type"] == "teacher"


@pytest.mark.django_db
def test_ungranted_admin_login_is_forbidden(api_client, student_user, sms_code):
    grant_user_role(student_user, "student")
    _set_sms_code(student_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": student_user.mobile,
            "verify_code": sms_code,
            "role_type": "admin",
        },
    )

    student_user.refresh_from_db()
    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"
    assert student_user.role_type == "student"
    assert not has_user_role(student_user, "admin")


@pytest.mark.django_db
def test_new_sms_account_can_only_self_create_as_student(api_client, sms_code):
    mobile = "13900009302"
    cache.set(f"sms_code:{mobile}", sms_code, timeout=180)

    denied = api_client.post(
        "/api/v1/auth/login",
        {"mobile": mobile, "verify_code": sms_code, "role_type": "teacher"},
    )

    assert denied.status_code == 403
    assert denied.data["code"] == "ROLE_NOT_GRANTED"
    assert not UserAccount.objects.filter(mobile=mobile).exists()

    allowed = api_client.post(
        "/api/v1/auth/login",
        {"mobile": mobile, "verify_code": sms_code, "role_type": "student"},
    )

    assert allowed.status_code == 200
    user = UserAccount.objects.get(mobile=mobile)
    assert user.role_type == "student"
    assert has_user_role(user, "student")


@pytest.mark.django_db
def test_new_sms_account_can_create_as_parent_for_binding(api_client, sms_code):
    mobile = "13900009306"
    cache.set(f"sms_code:{mobile}", sms_code, timeout=180)

    response = api_client.post(
        "/api/v1/auth/login",
        {"mobile": mobile, "verify_code": sms_code, "role_type": "parent"},
    )

    assert response.status_code == 200
    user = UserAccount.objects.get(mobile=mobile)
    assert user.role_type == "parent"
    assert has_user_role(user, "parent")
    assert response.data["data"]["user"]["active_role"] == "parent"


@pytest.mark.django_db
def test_existing_student_can_self_create_parent_role_on_sms_login(api_client, student_user, sms_code):
    grant_user_role(student_user, "student")
    _set_sms_code(student_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": student_user.mobile,
            "verify_code": sms_code,
            "role_type": "parent",
        },
    )

    student_user.refresh_from_db()
    assert response.status_code == 200
    assert student_user.role_type == "student"
    assert get_user_roles(student_user) == ["parent", "student"]
    assert UserRole.objects.filter(
        user=student_user, role="parent", status="active", grant_source="self_login"
    ).exists()
    assert response.data["data"]["user"]["active_role"] == "parent"
    assert response.data["data"]["user"]["roles"] == ["parent", "student"]


@pytest.mark.django_db
def test_existing_teacher_can_self_create_student_role_on_sms_login(api_client, teacher_user, sms_code):
    grant_user_role(teacher_user, "teacher")
    _set_sms_code(teacher_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": teacher_user.mobile,
            "verify_code": sms_code,
            "role_type": "student",
        },
    )

    teacher_user.refresh_from_db()
    assert response.status_code == 200
    assert teacher_user.role_type == "teacher"
    assert get_user_roles(teacher_user) == ["teacher", "student"]
    assert UserRole.objects.filter(
        user=teacher_user, role="student", status="active", grant_source="self_login"
    ).exists()
    assert response.data["data"]["user"]["active_role"] == "student"


@pytest.mark.django_db
def test_existing_teacher_can_self_create_parent_role_on_sms_login(api_client, teacher_user, sms_code):
    grant_user_role(teacher_user, "teacher")
    _set_sms_code(teacher_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": teacher_user.mobile,
            "verify_code": sms_code,
            "role_type": "parent",
        },
    )

    teacher_user.refresh_from_db()
    assert response.status_code == 200
    assert teacher_user.role_type == "teacher"
    assert get_user_roles(teacher_user) == ["teacher", "parent"]
    assert response.data["data"]["user"]["active_role"] == "parent"


@pytest.mark.django_db
def test_revoked_parent_role_is_not_restored_by_sms_login(api_client, student_user, sms_code):
    grant_user_role(student_user, "student")
    grant_user_role(student_user, "parent")
    revoke_user_role(student_user, "parent")
    _set_sms_code(student_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": student_user.mobile,
            "verify_code": sms_code,
            "role_type": "parent",
        },
    )

    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"
    assert not has_user_role(student_user, "parent")


@pytest.mark.django_db
def test_revoked_student_role_is_not_restored_for_teacher_on_sms_login(api_client, teacher_user, sms_code):
    grant_user_role(teacher_user, "teacher")
    grant_user_role(teacher_user, "student")
    revoke_user_role(teacher_user, "student")
    _set_sms_code(teacher_user, sms_code)

    response = api_client.post(
        "/api/v1/auth/login",
        {
            "mobile": teacher_user.mobile,
            "verify_code": sms_code,
            "role_type": "student",
        },
    )

    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"
    assert not has_user_role(teacher_user, "student")


@pytest.mark.django_db
def test_three_granted_roles_switch_without_reauth(api_client, student_user):
    for role in ("student", "parent", "teacher"):
        grant_user_role(student_user, role)

    _authenticate(api_client, generate_tokens(student_user, "student")["access_token"])
    parent_response = api_client.post("/api/v1/auth/switch-role", {"role": "parent"})
    assert parent_response.status_code == 200
    assert parent_response.data["data"]["user"]["roles"] == ["teacher", "parent", "student"]
    assert parent_response.data["data"]["user"]["active_role"] == "parent"

    _authenticate(api_client, parent_response.data["data"]["access_token"])
    teacher_response = api_client.post("/api/v1/auth/switch-role", {"role": "teacher"})
    assert teacher_response.status_code == 200
    assert teacher_response.data["data"]["user"]["active_role"] == "teacher"


@pytest.mark.django_db
def test_two_tokens_keep_independent_active_roles(admin_teacher):
    admin_tokens = generate_tokens(admin_teacher, "admin")
    teacher_tokens = generate_tokens(admin_teacher, "teacher")

    assert AccessToken(admin_tokens["access_token"])["active_role"] == "admin"
    assert RefreshToken(admin_tokens["refresh_token"])["active_role"] == "admin"
    assert AccessToken(teacher_tokens["access_token"])["active_role"] == "teacher"
    assert RefreshToken(teacher_tokens["refresh_token"])["active_role"] == "teacher"


@pytest.mark.django_db
def test_generate_tokens_rejects_an_ungranted_role(student_user):
    grant_user_role(student_user, "student")

    with pytest.raises(RoleNotGranted):
        generate_tokens(student_user, "admin")


@pytest.mark.django_db
def test_switch_role_returns_an_independent_authorized_session(api_client, admin_teacher):
    original = generate_tokens(admin_teacher, "admin")
    _authenticate(api_client, original["access_token"])

    response = api_client.post("/api/v1/auth/switch-role", {"role": "teacher"})

    assert response.status_code == 200
    data = response.data["data"]
    assert data["user"]["active_role"] == "teacher"
    assert AccessToken(data["access_token"])["active_role"] == "teacher"
    assert RefreshToken(data["refresh_token"])["active_role"] == "teacher"
    assert AccessToken(original["access_token"])["active_role"] == "admin"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_code"),
    [
        ({"role": "owner"}, 400, "INVALID_ROLE"),
        ({}, 400, "INVALID_ROLE"),
        ({"role": "parent"}, 403, "ROLE_NOT_GRANTED"),
    ],
)
def test_switch_role_rejects_invalid_and_ungranted_roles(
    api_client, admin_teacher, payload, expected_status, expected_code
):
    tokens = generate_tokens(admin_teacher, "admin")
    _authenticate(api_client, tokens["access_token"])

    response = api_client.post("/api/v1/auth/switch-role", payload)

    assert response.status_code == expected_status
    assert response.data["code"] == expected_code


@pytest.mark.django_db
def test_refresh_preserves_active_role(api_client, admin_teacher):
    tokens = generate_tokens(admin_teacher, "teacher")

    response = api_client.post(
        "/api/v1/auth/refresh", {"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    assert AccessToken(response.data["data"]["access_token"])["active_role"] == "teacher"


@pytest.mark.django_db
def test_refresh_rejects_role_revoked_after_token_issuance(api_client, admin_teacher):
    tokens = generate_tokens(admin_teacher, "teacher")
    revoke_user_role(admin_teacher, "teacher")

    response = api_client.post(
        "/api/v1/auth/refresh", {"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"


@pytest.mark.django_db
def test_authentication_rechecks_role_grant_after_token_issuance(
    api_client, admin_teacher
):
    tokens = generate_tokens(admin_teacher, "teacher")
    revoke_user_role(admin_teacher, "teacher")
    _authenticate(api_client, tokens["access_token"])

    response = api_client.get("/api/v1/auth/profile/me")

    assert response.status_code == 401


@pytest.mark.django_db
def test_legacy_access_token_uses_legacy_role_only_while_grant_exists(
    api_client, teacher_user
):
    grant_user_role(teacher_user, "teacher")
    legacy_access = str(RefreshToken.for_user(teacher_user).access_token)
    _authenticate(api_client, legacy_access)

    allowed = api_client.get("/api/v1/auth/profile/me")

    assert allowed.status_code == 200
    assert allowed.data["data"]["active_role"] == "teacher"

    revoke_user_role(teacher_user, "teacher")
    denied = api_client.get("/api/v1/auth/profile/me")

    assert denied.status_code == 401


@pytest.mark.django_db
@pytest.mark.parametrize("malformed_role", [None, "", "owner"])
def test_access_token_with_present_malformed_role_claim_never_uses_legacy_fallback(
    api_client, teacher_user, malformed_role
):
    grant_user_role(teacher_user, "teacher")
    access = RefreshToken.for_user(teacher_user).access_token
    access["active_role"] = malformed_role
    _authenticate(api_client, str(access))

    response = api_client.get("/api/v1/auth/profile/me")

    assert response.status_code == 401
    assert response.data["detail"].code == "ROLE_NOT_GRANTED"


@pytest.mark.django_db
@pytest.mark.parametrize("malformed_role", [None, "", "owner"])
def test_refresh_token_with_present_malformed_role_claim_never_uses_legacy_fallback(
    api_client, teacher_user, malformed_role
):
    grant_user_role(teacher_user, "teacher")
    refresh = RefreshToken.for_user(teacher_user)
    refresh["active_role"] = malformed_role

    response = api_client.post(
        "/api/v1/auth/refresh", {"refresh_token": str(refresh)}
    )

    assert response.status_code == 403
    assert response.data["code"] == "ROLE_NOT_GRANTED"


@pytest.mark.django_db
def test_profile_uses_each_tokens_active_role_without_persisting_it(
    api_client, admin_teacher
):
    admin_session = generate_tokens(admin_teacher, "admin")
    teacher_session = generate_tokens(admin_teacher, "teacher")

    _authenticate(api_client, admin_session["access_token"])
    admin_response = api_client.get("/api/v1/auth/profile/me")
    _authenticate(api_client, teacher_session["access_token"])
    teacher_response = api_client.get("/api/v1/auth/profile/me")

    admin_teacher.refresh_from_db()
    assert admin_response.data["data"]["active_role"] == "admin"
    assert teacher_response.data["data"]["active_role"] == "teacher"
    assert admin_teacher.role_type == "admin"


@pytest.mark.django_db
def test_create_admin_grants_admin_without_rewriting_existing_legacy_role(
    teacher_user
):
    grant_user_role(teacher_user, "teacher")

    call_command("create_admin", teacher_user.mobile, "Existing Teacher")

    teacher_user.refresh_from_db()
    assert teacher_user.role_type == "teacher"
    assert has_user_role(teacher_user, "teacher")
    assert has_user_role(teacher_user, "admin")


@pytest.mark.django_db
def test_wechat_binding_only_creates_approved_initial_roles(api_client, sms_code):
    mobile = "13900009303"
    cache.set("wechat_pending:bind-parent", {
        "appid": "wx-test",
        "openid": "openid-parent",
        "unionid": "",
    })
    cache.set(f"sms_code:{mobile}", sms_code, timeout=180)

    response = api_client.post(
        "/api/v1/auth/wechat-bind",
        {
            "bind_token": "bind-parent",
            "mobile": mobile,
            "verify_code": sms_code,
            "role_type": "parent",
        },
    )

    assert response.status_code == 200
    user = UserAccount.objects.get(mobile=mobile)
    assert user.role_type == "parent"
    assert has_user_role(user, "parent")
    assert response.data["data"]["user"]["active_role"] == "parent"
    assert WechatIdentity.objects.filter(user=user).exists()

    denied_mobile = "13900009304"
    cache.set("wechat_pending:bind-admin", {
        "appid": "wx-test",
        "openid": "openid-admin",
        "unionid": "",
    })
    cache.set(f"sms_code:{denied_mobile}", sms_code, timeout=180)
    denied = api_client.post(
        "/api/v1/auth/wechat-bind",
        {
            "bind_token": "bind-admin",
            "mobile": denied_mobile,
            "verify_code": sms_code,
            "role_type": "admin",
        },
    )

    assert denied.status_code == 403
    assert denied.data["code"] == "ROLE_NOT_GRANTED"
    assert not UserAccount.objects.filter(mobile=denied_mobile).exists()


@pytest.mark.django_db
def test_existing_wechat_identity_selects_only_a_granted_session_role(
    api_client, admin_teacher, monkeypatch, settings
):
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    WechatIdentity.objects.create(
        user=admin_teacher,
        appid="wx-test",
        openid="openid-existing",
    )

    class WechatResponse:
        def json(self):
            return {"openid": "openid-existing", "session_key": "session-key"}

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: WechatResponse())

    response = api_client.post(
        "/api/v1/auth/wechat-login",
        {"code": "one-time-code", "role_type": "teacher"},
    )

    assert response.status_code == 200
    assert response.data["data"]["user"]["active_role"] == "teacher"
    assert AccessToken(response.data["data"]["access_token"])["active_role"] == "teacher"

    parent_login = api_client.post(
        "/api/v1/auth/wechat-login",
        {"code": "another-code", "role_type": "parent"},
    )

    assert parent_login.status_code == 200
    admin_teacher.refresh_from_db()
    assert has_user_role(admin_teacher, "parent")
    assert parent_login.data["data"]["user"]["active_role"] == "parent"
    assert parent_login.data["data"]["user"]["roles"] == [
        "admin", "teacher", "parent"
    ]


@pytest.mark.django_db
def test_wechat_binding_existing_account_defaults_to_its_legacy_granted_role(
    api_client, sms_code
):
    parent = UserAccount.objects.create(
        role_type="parent",
        mobile="13900009305",
        display_name="Existing Parent",
    )
    grant_user_role(parent, "parent")
    cache.set("wechat_pending:bind-existing-parent", {
        "appid": "wx-test",
        "openid": "openid-existing-parent",
        "unionid": "",
    })
    cache.set(f"sms_code:{parent.mobile}", sms_code, timeout=180)

    response = api_client.post(
        "/api/v1/auth/wechat-bind",
        {
            "bind_token": "bind-existing-parent",
            "mobile": parent.mobile,
            "verify_code": sms_code,
        },
    )

    parent.refresh_from_db()
    assert response.status_code == 200
    assert response.data["data"]["user"]["active_role"] == "parent"
    assert parent.role_type == "parent"


@pytest.mark.django_db
def test_wechat_binding_existing_student_can_open_parent_role(api_client, student_user, sms_code):
    grant_user_role(student_user, "student")
    cache.set("wechat_pending:bind-existing-student", {
        "appid": "wx-test",
        "openid": "openid-existing-student",
        "unionid": "",
    })
    cache.set(f"sms_code:{student_user.mobile}", sms_code, timeout=180)

    response = api_client.post(
        "/api/v1/auth/wechat-bind",
        {
            "bind_token": "bind-existing-student",
            "mobile": student_user.mobile,
            "verify_code": sms_code,
            "role_type": "parent",
        },
    )

    assert response.status_code == 200
    assert has_user_role(student_user, "student")
    assert has_user_role(student_user, "parent")
    assert response.data["data"]["user"]["active_role"] == "parent"
