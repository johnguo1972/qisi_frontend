import pytest
from rest_framework.test import APIClient

from apps.accounts import wechat_miniprogram
from apps.accounts.models import UserAccount, WechatIdentity
from apps.accounts.roles import grant_user_role


@pytest.mark.django_db
def test_new_miniprogram_user_logs_in_with_wechat_phone_without_sms(monkeypatch):
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="new-openid", unionid="new-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000001",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "student",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["code"] == 0
    assert response.data["data"]["user"]["active_role"] == "student"
    user = UserAccount.objects.get(mobile="13800000001")
    identity = WechatIdentity.objects.get(user=user)
    assert identity.openid == "new-openid"
    assert user.role_grants.get(role="student").grant_source == "wechat_mp"


@pytest.mark.django_db
def test_existing_phone_account_binds_wechat_identity_and_keeps_teacher_role(
    monkeypatch,
):
    user = UserAccount.objects.create(
        mobile="13800000010",
        role_type="teacher",
        display_name="Existing teacher",
        status="active",
        password="",
    )
    grant_user_role(user, "teacher", grant_source="business")
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="phone-account-openid", unionid="phone-account-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000010",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "teacher",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["user"]["id"] == str(user.id)
    assert WechatIdentity.objects.get(user=user).openid == "phone-account-openid"
    assert UserAccount.objects.count() == 1


@pytest.mark.django_db
def test_existing_multirole_phone_account_can_login_as_student(monkeypatch):
    user = UserAccount.objects.create(
        mobile="13800000011",
        role_type="teacher",
        display_name="Multi role user",
        status="active",
        password="",
    )
    grant_user_role(user, "teacher", grant_source="business")
    grant_user_role(user, "student", grant_source="business")
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="multirole-openid", unionid="multirole-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000011",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "student",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["user"]["active_role"] == "student"
    assert response.data["data"]["user"]["id"] == str(user.id)


@pytest.mark.django_db
def test_existing_phone_account_replaces_old_wechat_identity(monkeypatch):
    user = UserAccount.objects.create(
        mobile="13800000012",
        role_type="student",
        display_name="Changed WeChat user",
        status="active",
        password="",
    )
    grant_user_role(user, "student", grant_source="business")
    old_identity = WechatIdentity.objects.create(
        user=user,
        appid="wx-test",
        openid="old-openid",
        unionid="old-unionid",
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="new-openid", unionid="new-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000012",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "student",
        },
        format="json",
    )

    assert response.status_code == 200
    identity = WechatIdentity.objects.get(user=user)
    assert identity.id == old_identity.id
    assert identity.openid == "new-openid"
    assert identity.unionid == "new-unionid"


@pytest.mark.django_db
def test_trusted_phone_moves_historical_wechat_identity_to_phone_account(monkeypatch):
    phone_user = UserAccount.objects.create(
        mobile="13800000013",
        role_type="student",
        display_name="Phone account",
        status="active",
        password="",
    )
    grant_user_role(phone_user, "student", grant_source="business")
    old_user = UserAccount.objects.create(
        mobile="13800000014",
        role_type="student",
        display_name="Historical account",
        status="active",
        password="",
    )
    grant_user_role(old_user, "student", grant_source="business")
    identity = WechatIdentity.objects.create(
        user=old_user,
        appid="wx-test",
        openid="historical-openid",
        unionid="historical-unionid",
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="historical-openid", unionid="historical-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000013",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "student",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["user"]["id"] == str(phone_user.id)
    assert WechatIdentity.objects.get(pk=identity.pk).user_id == phone_user.id


@pytest.mark.django_db
def test_existing_miniprogram_identity_logs_in_as_the_bound_user(monkeypatch):
    user = UserAccount.objects.create(
        mobile="13800000002",
        role_type="parent",
        display_name="Existing parent",
        status="active",
        password="",
    )
    grant_user_role(user, "parent", grant_source="business")
    WechatIdentity.objects.create(
        user=user, appid="wx-test", openid="known-openid", unionid="known-unionid"
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="known-openid", unionid="known-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000002",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "parent",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["user"]["id"] == str(user.id)
    assert UserAccount.objects.count() == 1


@pytest.mark.django_db
def test_miniprogram_identity_cannot_be_rebound_to_another_phone(monkeypatch):
    user = UserAccount.objects.create(
        mobile="13800000003",
        role_type="student",
        display_name="Bound student",
        status="active",
        password="",
    )
    grant_user_role(user, "student", grant_source="business")
    WechatIdentity.objects.create(
        user=user, appid="wx-test", openid="bound-openid", unionid="bound-unionid"
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_login_code",
        lambda code: wechat_miniprogram.MiniProgramIdentity(
            appid="wx-test", openid="bound-openid", unionid="bound-unionid"
        ),
    )
    monkeypatch.setattr(
        wechat_miniprogram,
        "exchange_miniprogram_phone_code",
        lambda code: "13800000004",
    )

    response = APIClient().post(
        "/api/v1/auth/wechat-phone-login",
        {
            "login_code": "login-once",
            "phone_code": "phone-once",
            "role_type": "student",
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.data["code"] == "WECHAT_IDENTITY_CONFLICT"
    assert WechatIdentity.objects.get().user_id == user.id
