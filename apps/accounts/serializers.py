from rest_framework import serializers

from .models import UserAccount


class LoginSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20)
    verify_code = serializers.CharField(max_length=6)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'role_type', 'login_name', 'mobile', 'display_name', 'avatar_url', 'status', 'subject', 'stages']


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()
