from rest_framework import serializers

from .models import UserAccount
from .roles import VALID_ROLES, get_user_roles


class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20)
    verify_code = serializers.CharField(max_length=6)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'role_type', 'login_name', 'mobile', 'display_name', 'avatar_url', 'status', 'subject', 'stages', 'grade_level']


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for updating user profile fields."""
    display_name = serializers.CharField(max_length=64, required=False)
    grade_level = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    avatar_url = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class WechatWebSessionSerializer(serializers.Serializer):
    """The H5 client may select a role, but never supplies an OAuth identity."""

    requested_role = serializers.ChoiceField(choices=VALID_ROLES)
    phone_authorization_confirmed = serializers.BooleanField()

    def validate_phone_authorization_confirmed(self, value):
        if value is not True:
            raise serializers.ValidationError("phone_authorization_confirmation_required")
        return value


class WebBindingSessionSerializer(serializers.Serializer):
    """The MP client may identify a web session, but may not submit a phone."""

    web_session_id = serializers.CharField(max_length=128)


class WebBindingCompleteSerializer(serializers.Serializer):
    """The H5 client consumes an opaque, browser-bound completion ticket."""

    ticket = serializers.CharField(max_length=128)
    requested_role = serializers.CharField(max_length=20, required=False)


class WebBindingPhoneSerializer(serializers.Serializer):
    """A Mini Program supplies only WeChat's one-time phone authorization code."""

    bridge_code = serializers.CharField(max_length=32)
    phone_code = serializers.CharField(max_length=256)


def serialize_user_session(user, active_role):
    """Serialize account data with session-scoped role compatibility fields."""
    data = ProfileSerializer(user).data
    data.update({
        'roles': get_user_roles(user),
        'active_role': active_role,
        'role_type': active_role,
    })
    return data
