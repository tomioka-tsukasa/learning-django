from rest_framework import serializers

from .models import Tweet


class TweetSerializer(serializers.ModelSerializer):
    """
    ツイート一覧・詳細表示用
    """

    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Tweet
        fields = ["id", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]
