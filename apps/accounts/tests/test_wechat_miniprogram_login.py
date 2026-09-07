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
