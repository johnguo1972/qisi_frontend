from rest_framework import serializers

from .models import UserAccount


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
