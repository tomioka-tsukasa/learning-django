from typing import TYPE_CHECKING, TypeAlias, TypedDict

from rest_framework.authtoken.models import Token

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

    UserType: TypeAlias = AbstractBaseUser
else:
    UserType = any


class UserRegisterData(TypedDict):
    """ユーザー登録リクエストデータ"""

    username: str
    email: str
    password: str
    password_confirm: str


class UserResponseData(TypedDict):
    """ユーザーレスポンスデータ"""

    id: int
    username: str
    email: str


class LoginRequestData(TypedDict):
    """ログインリクエストデータ（バリデーション前）"""

    username: str
    password: str


class LoginValidatedData(TypedDict):
    """ログインバリデーション後のデータ"""

    username: str
    password: str
    user: UserType


class LoginResponseData(TypedDict):
    """ログインレスポンスデータ"""

    token: str
    user: UserResponseData
