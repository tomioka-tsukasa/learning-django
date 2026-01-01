# 認証実装ガイド

AlarmBox API の認証（トークン管理）を実装する手順を解説します。

---

## 目標

**PM・テックリードがローカルで認証を試せる状態にする**

---

## 実装するファイル

| ファイル | 役割 |
|----------|------|
| `core/models/riskeyes_v2/alarmbox.py` | トークン保存用 Model |
| `lib/alarmbox/__init__.py` | パッケージ初期化 |
| `lib/alarmbox/exceptions.py` | 例外定義 |
| `lib/alarmbox/client.py` | API クライアント（トークン更新部分） |
| `lib/alarmbox/token_service.py` | トークン管理サービス |
| `core/management/commands/save_alarmbox_token.py` | 初回トークン登録コマンド |

---

## 実装手順

```
Step 1: Model 作成（トークン保存用テーブル）
    ↓
Step 2: Migration 実行
    ↓
Step 3: 例外クラス作成
    ↓
Step 4: API クライアント作成（refresh_token 部分）
    ↓
Step 5: トークン管理サービス作成
    ↓
Step 6: 管理コマンド作成（初回トークン登録用）
    ↓
Step 7: 動作確認
```

---

## Step 1: Model 作成

### ファイルを作成

```python
# core/models/riskeyes_v2/alarmbox.py

from django.db import models


class AlarmboxToken(models.Model):
    """
    AlarmBox API のトークンを管理するテーブル
    常に 1 レコードのみ存在
    """
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    expired_at = models.DateTimeField()  # access_token の有効期限
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hansha_alarmbox_tokens'

    def save(self, *args, **kwargs):
        # 常に id=1 で保存（1 レコードのみ許可）
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls) -> "AlarmboxToken":
        """唯一のインスタンスを取得（なければ作成）"""
        obj, created = cls.objects.get_or_create(pk=1, defaults={
            'access_token': '',
            'refresh_token': '',
            'expired_at': None,
        })
        return obj
```

### __init__.py に追記

```python
# core/models/riskeyes_v2/__init__.py

from .alarmbox import AlarmboxToken
```

---

## Step 2: Migration 実行

```bash
# Migration ファイルを生成
python manage.py makemigrations core

# DB に反映
python manage.py migrate
```

### 確認

```bash
# テーブルが作成されたか確認（MySQL の場合）
mysql -u root -p -e "DESCRIBE hansha_alarmbox_tokens;"
```

---

## Step 3: 例外クラス作成

```python
# lib/alarmbox/exceptions.py

class AlarmboxAPIError(Exception):
    """AlarmBox API のエラー"""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AlarmboxTokenError(AlarmboxAPIError):
    """トークン関連のエラー"""
    pass


class AlarmboxTokenNotFoundError(AlarmboxTokenError):
    """トークンが未設定"""
    pass


class AlarmboxTokenExpiredError(AlarmboxTokenError):
    """トークンの更新に失敗"""
    pass
```

```python
# lib/alarmbox/__init__.py

from .exceptions import (
    AlarmboxAPIError,
    AlarmboxTokenError,
    AlarmboxTokenNotFoundError,
    AlarmboxTokenExpiredError,
)
```

---

## Step 4: API クライアント作成

認証に必要な部分（トークン更新）だけ先に実装。

まず、型定義ファイルを作成：

```python
# lib/alarmbox/types.py

from typing import TypedDict


# --- リクエスト型 ---

class AuthorizationCodeRequest(TypedDict):
    """初回認証リクエスト（認可コード → トークン取得）"""
    grant_type: str       # "authorization_code"（固定）
    client_id: str
    client_secret: str
    code: str             # 認可コード
    redirect_uri: str


class RefreshTokenRequest(TypedDict):
    """トークン更新リクエスト"""
    grant_type: str       # "refresh_token"（固定）
    client_id: str
    client_secret: str
    refresh_token: str
    redirect_uri: str


# --- レスポンス型 ---

class TokenResponse(TypedDict):
    """トークン取得・更新のレスポンス"""
    access_token: str
    refresh_token: str
    token_type: str       # Bearer（固定）
    expires_in: int       # 有効期間（秒）
    scope: str            # 許可された権限
    redirect_uri: str     # 遷移先の URL
    created_at: int       # トークン生成タイムスタンプ
```

次に、クライアント本体：

```python
# lib/alarmbox/client.py

import json
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
from django.conf import settings

from .types import (
    AuthorizationCodeRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from .exceptions import AlarmboxAPIError

# デフォルトのリダイレクトURI（OOB: Out-of-Band）
DEFAULT_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


class AlarmboxClient:
    """
    AlarmBox API を呼び出すクライアント
    """
    BASE_URL = 'https://api.alarmbox.jp'

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

    @classmethod
    def _post_request(cls, url: str, payload: dict, expected_status: int = 200) -> dict:
        """共通のPOSTリクエスト処理"""
        try:
            response = requests.post(url, data=payload, timeout=30)
        except Timeout:
            raise AlarmboxAPIError('タイムアウト: AlarmBox API に接続できません')
        except ConnectionError:
            raise AlarmboxAPIError('接続エラー: AlarmBox API に接続できません')
        except RequestException as e:
            raise AlarmboxAPIError(f'リクエストエラー: {e}')

        if response.status_code != expected_status:
            raise AlarmboxAPIError(
                message=f'APIエラー: {response.status_code}',
                status_code=response.status_code,
                response_body=response.text
            )

        try:
            return response.json()
        except json.JSONDecodeError:
            raise AlarmboxAPIError(f'JSONパースエラー: {response.text[:200]}')

    @classmethod
    def get_token_by_code(cls, code: str, redirect_uri: str = DEFAULT_REDIRECT_URI) -> TokenResponse:
        """
        認可コードからトークンを取得する（初回認証用）
        POST /oauth/token
        """
        url = f'{cls.BASE_URL}/oauth/token'
        payload: AuthorizationCodeRequest = {
            'grant_type': 'authorization_code',
            'client_id': settings.ALARMBOX_INFO["client_id"],
            'client_secret': settings.ALARMBOX_INFO["client_secret"],
            'code': code,
            'redirect_uri': redirect_uri,
        }
        return cls._post_request(url, payload)

    @classmethod
    def refresh_token(cls, refresh_token: str, redirect_uri: str = DEFAULT_REDIRECT_URI) -> TokenResponse:
        """
        リフレッシュトークンを使って新しいトークンを取得する
        POST /oauth/token
        """
        url = f'{cls.BASE_URL}/oauth/token'
        payload: RefreshTokenRequest = {
            'grant_type': 'refresh_token',
            'client_id': settings.ALARMBOX_INFO["client_id"],
            'client_secret': settings.ALARMBOX_INFO["client_secret"],
            'refresh_token': refresh_token,
            'redirect_uri': redirect_uri,
        }
        return cls._post_request(url, payload)
```

### エラーハンドリング

| 例外 | 状況 |
|------|------|
| `Timeout` | 接続/読み取りタイムアウト（30秒） |
| `ConnectionError` | DNS解決失敗、接続拒否、ネットワーク断 |
| `RequestException` | その他の requests エラー全般 |
| `json.JSONDecodeError` | API が壊れた HTML やエラーページを返した時 |
| `status_code != expected` | API がエラーステータスを返した時（401, 500 など） |

### settings に追加

このプロジェクトでは環境ごとに設定ファイルが分かれている。

```python
# core/config/_base_settings.py（ローカル用ダミー値）
ALARMBOX_INFO = {
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
}

# core/config/devserver.py（Dev 環境）
from core.lib.google_cloud import get_json_secret
ALARMBOX_INFO = get_json_secret("riskeyes-alarmbox-info-dev")

# core/config/production.py（本番環境）
ALARMBOX_INFO = get_json_secret("riskeyes-alarmbox-info-prod")
```

### 使用側（client.py）

```python
from django.conf import settings

settings.ALARMBOX_INFO["client_id"]
settings.ALARMBOX_INFO["client_secret"]
```

---

## Step 5: トークン管理サービス作成

```python
# lib/alarmbox/token_service.py

from datetime import datetime, timedelta

from core.models.riskeyes_v2.alarmbox import AlarmboxToken
from .client import AlarmboxClient
from .exceptions import AlarmboxTokenNotFoundError, AlarmboxTokenExpiredError


class TokenService:
    """
    AlarmBox API のトークンを管理するサービス
    """

    # 期限切れ判定のマージン（5分前から期限切れ扱い）
    EXPIRY_MARGIN = timedelta(minutes=5)

    @classmethod
    def get_valid_access_token(cls) -> str:
        """
        有効な access_token を取得する
        期限切れの場合は自動で更新する

        Returns:
            有効な access_token

        Raises:
            AlarmboxTokenNotFoundError: トークンが未設定
            AlarmboxTokenExpiredError: トークン更新に失敗
        """
        token = AlarmboxToken.get_instance()

        # トークンが未設定の場合
        if not token.access_token or not token.refresh_token:
            raise AlarmboxTokenNotFoundError(
                'トークンが未設定です。save_alarmbox_token コマンドで初回設定を行ってください。'
            )

        # 期限切れチェック
        if cls._is_expired(token.expired_at):
            cls._refresh_token(token)

        return token.access_token

    @classmethod
    def _is_expired(cls, expired_at) -> bool:
        """
        トークンが期限切れかどうか判定
        """
        # expired_at が未設定なら期限切れ扱い
        if expired_at is None:
            return True
        # 現在時刻が (期限 - 5分) を過ぎていたら期限切れ
        return datetime.now() >= (expired_at - cls.EXPIRY_MARGIN)

    @classmethod
    def _refresh_token(cls, token: AlarmboxToken) -> None:
        """
        トークンを更新して DB に保存
        """
        try:
            result = AlarmboxClient.refresh_token(token.refresh_token)
        except Exception as e:
            raise AlarmboxTokenExpiredError(
                f'トークンの更新に失敗しました: {e}'
            )

        # DB を更新
        token.access_token = result['access_token']
        token.refresh_token = result['refresh_token']
        token.expired_at = datetime.now() + timedelta(seconds=result['expires_in'])
        token.save()

    @classmethod
    def save_initial_token(
        cls,
        access_token: str,
        refresh_token: str,
        expires_in: int
    ) -> AlarmboxToken:
        """
        初回認証後のトークンを保存する

        Args:
            access_token: AlarmBox の access_token
            refresh_token: AlarmBox の refresh_token
            expires_in: access_token の有効期限（秒）

        Returns:
            保存した AlarmboxToken インスタンス
        """
        token = AlarmboxToken.get_instance()
        token.access_token = access_token
        token.refresh_token = refresh_token
        token.expired_at = datetime.now() + timedelta(seconds=expires_in)
        token.save()
        return token
```

---

## Step 6: 管理コマンド作成

認可コードを渡すだけで、トークン取得 → DB 保存まで自動で行うコマンドを作成します。

```python
# core/management/commands/save_alarmbox_token.py

from django.core.management.base import BaseCommand

from lib.alarmbox.client import AlarmboxClient
from lib.alarmbox.token_service import TokenService


class Command(BaseCommand):
    """AlarmBox のトークンを DB に保存するコマンド"""

    help = '認可コードからトークンを取得して保存します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--code',
            required=True,
            help='認可コード（ブラウザで取得）',
        )
        parser.add_argument(
            '--redirect_uri',
            default='urn:ietf:wg:oauth:2.0:oob',
            help='リダイレクトURI（デフォルト: urn:ietf:wg:oauth:2.0:oob）',
        )

    def handle(self, *args, **options):
        code = options['code']
        redirect_uri = options['redirect_uri']

        self.stdout.write('認可コードからトークンを取得中...')

        # 1. 認可コードでトークン取得
        result = AlarmboxClient.get_token_by_code(code, redirect_uri)

        # 2. DB に保存
        token = TokenService.save_initial_token(
            access_token=result['access_token'],
            refresh_token=result['refresh_token'],
            expires_in=result['expires_in'],
        )

        self.stdout.write(self.style.SUCCESS('トークンを保存しました'))
        self.stdout.write(f'  access_token: {result["access_token"][:20]}...')
        self.stdout.write(f'  refresh_token: {result["refresh_token"][:20]}...')
        self.stdout.write(f'  expires_in: {result["expires_in"]}秒')
        self.stdout.write(f'  expired_at: {token.expired_at}')
```

---

## Step 7: 動作確認

### 1. 認可コードを取得

ブラウザで以下にアクセス：

```
https://api.alarmbox.jp/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&response_type=code&scope=read+customer%3Adelete+customer%3Acreate+credit_check%3Acreate
```

認可後、画面に認可コードが表示されます。

### 2. トークンを取得 & 保存

```bash
python manage.py save_alarmbox_token --code=CU8wbymHIiKUYy6tsY8dbCbzsZNdEucx70d2ZpBLz3Q
```

実行結果：

```
認可コードからトークンを取得中...
トークンを保存しました
  access_token: l-TGspUX-fPghhcKp...
  refresh_token: JlV8SeYcWwGrsAMh...
  expires_in: 86400秒
  expired_at: 2025-12-20 12:34:56+00:00
```

### 3. トークン取得を確認

Django shell で確認：

```bash
python manage.py shell
```

```python
from lib.alarmbox.token_service import TokenService

# トークンを取得（期限切れなら自動更新）
token = TokenService.get_valid_access_token()
print(token)
```

### 4. トークン更新を確認（任意）

```python
from core.models.riskeyes_v2.alarmbox import AlarmboxToken
from datetime import datetime, timedelta

# 強制的に期限切れにする
token = AlarmboxToken.get_instance()
token.expired_at = datetime.now() - timedelta(hours=1)
token.save()

# 再度取得 → 自動更新されるはず
from lib.alarmbox.token_service import TokenService
new_token = TokenService.get_valid_access_token()
print(new_token)
```

---

## レビュー依頼時のチェックリスト

- [ ] Model が作成されている
- [ ] Migration が成功している
- [ ] 管理コマンドでトークン保存ができる
- [ ] TokenService でトークン取得ができる
- [ ] 期限切れ時に自動更新される
- [ ] 環境変数（CLIENT_ID, CLIENT_SECRET）が設定されている

---

## トラブルシューティング

### トークン更新に失敗する

```
AlarmboxAPIError: トークン更新失敗: 401 ...
```

原因：
- refresh_token が無効（すでに使用済み or 手入力ミス）
- client_secret が間違っている

対処：
- 認可コード取得からやり直す

### トークンが未設定エラー

```
AlarmboxTokenNotFoundError: トークンが未設定です...
```

対処：
- `save_alarmbox_token` コマンドを実行する
