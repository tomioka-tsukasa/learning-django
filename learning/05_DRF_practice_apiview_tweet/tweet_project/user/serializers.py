from typing import Any

from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .types import LoginValidatedData

User = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "password"]
        extra_kwargs = {
            "password": {
                "write_only": True,
                "required": True,
                "min_length": 8,
                "style": {"input_type" : "password"}
            },
            "email": {
                "required": True,
                "allow_blank": False
            },
            "username": {
                "required": True,
                "min_length": 3,
                "max_length": 150
            },
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )
        return user

    def validate_email(self, value):
        """メールアドレスの重複チェック"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("既に登録されているメールアドレスです。")

class UserLoginSerializer(serializers.Serializer):
    """ログイン用Serializer（Token認証）"""

    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"}
    )

    def validate(self, attrs: Any) -> LoginValidatedData:
        """
        ユーザー認証

        Args:
            attrs: リクエストデータ

        Returns:
            LoginValidatedData: 認証済みユーザーを含むデータ
        """

        username: str = attrs.get("username", "")
        password: str = attrs.get("password", "")

        user = authenticate(username=username, password=password)

        if user is None:
            raise serializers.ValidationError("ユーザー名またはパスワードが正しくありません。")

        if not user.is_active:
            raise serializers.ValidationError('このアカウントは無効化されています。')

        validated_data: LoginValidatedData = {
            "username": username,
            "password": password,
            "user": user
        }

        return validated_data
