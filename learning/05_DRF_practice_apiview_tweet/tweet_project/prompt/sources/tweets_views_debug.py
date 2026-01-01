from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tweet
from .serializers import TweetSerializer


class TweetListCreateView(APIView):
    """ツイート一覧・作成（デバッグ用：一覧のみ）"""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        tweets = Tweet.objects.all()
        serializer = TweetSerializer(tweets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TweetDetailView(APIView):
    """ツイート詳細（デバッグ用）"""

    permission_classes = [AllowAny]

    def get(self, request: Request, pk: int) -> Response:
        try:
            tweet = Tweet.objects.get(pk=pk)
        except Tweet.DoesNotExist:
            return Response(
                {"error": "ツイートが見つかりません"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = TweetSerializer(tweet)
        return Response(serializer.data, status=status.HTTP_200_OK)
