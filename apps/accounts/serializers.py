from rest_framework import serializers

from .models import UserAccount
from .roles import VALID_ROLES, get_user_roles


def normalize_teacher_subjects(user) -> list[str]:
    """Return configured teacher subjects, preserving legacy single-subject users."""
    raw_subjects = getattr(user, 'subjects', None)
    if isinstance(raw_subjects, list):
        normalized = []
        for value in raw_subjects:
            subject = str(value or '').strip()
            if subject and subject not in normalized:
                normalized.append(subject)
        if normalized:
            return normalized
    return [user.subject] if user.subject else []


class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20)
    verify_code = serializers.CharField(max_length=6)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'role_type', 'login_name', 'mobile', 'display_name', 'avatar_url', 'status', 'subject', 'subjects', 'stages', 'grade_level']


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


class DeviceSessionSerializer(serializers.Serializer):
    requested_role = serializers.ChoiceField(choices=VALID_ROLES)


class DeviceScanSerializer(serializers.Serializer):
    bridge_code = serializers.CharField(max_length=32)
    login_code = serializers.CharField(max_length=256)


class DevicePhoneSerializer(serializers.Serializer):
    phone_binding_token = serializers.CharField(max_length=128)
    phone_code = serializers.CharField(max_length=256)


class DeviceCompleteSerializer(serializers.Serializer):
    ticket = serializers.CharField(max_length=128)
    requested_role = serializers.ChoiceField(choices=VALID_ROLES)


def serialize_user_session(user, active_role):
    """Serialize account data with session-scoped role compatibility fields."""
    data = ProfileSerializer(user).data
    data.update({
        'subjects': normalize_teacher_subjects(user),
        'roles': get_user_roles(user),
        'active_role': active_role,
        'role_type': active_role,
    })
    return data
