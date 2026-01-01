import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tweet
from .serializers import TweetSerializer

# Create your views here.

logger = logging.getLogger(__name__)


class TweetListCreateView(APIView):
    def get(self, request: Request) -> Response:
        tweets = Tweet.objects.all()
        serializer = TweetSerializer(tweets, many=True)

        logger.info(tweets)
        logger.info(serializer)

        return Response(serializer.data, status=status.HTTP_200_OK)
