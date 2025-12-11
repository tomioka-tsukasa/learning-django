from django.contrib.auth import get_user_model
from rest_framework import serializers

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
