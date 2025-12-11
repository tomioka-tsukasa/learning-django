import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserRegisterSerializer

logger = logging.getLogger(__name__)

class UserLoginView(APIView):
    pass

class UserRegisterView(APIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny,]

    def post(self, request):
        """
        ユーザー登録

        Request Body:
            - username: ユーザー名（必須、3-150文字）
            - email: メールアドレス（必須）
            - password: パスワード（必須、Django標準バリデーション）
            - password_confirm: パスワード確認（必須）

        Returns:
            201: 登録成功
            400: バリデーションエラー
        """
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            logger(f"New user registered: {user.username}")

            return Response(
                {
                    "message": "ユーザー登録が完了しました。",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                    }
                },
                status=status.HTTP_201_CREATED
            )

        logger.warning(f"User registration failed: {serializer.errors}")
        return Response(
            {
                "message": "入力内容に誤りがあります。",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
