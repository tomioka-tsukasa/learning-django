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
| `core/management/commands/refresh_alarmbox_token.py` | トークン更新バッチ |

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
Step 5: トークン管理サービス作成（ロック機構含む）
    ↓
Step 6: 管理コマンド作成（初回トークン登録用）
    ↓
Step 7: バッチコマンド作成（定期トークン更新用）
    ↓
Step 8: 動作確認
```

---

## Step 1: Model 作成

### ファイルを作成

```python
# core/models/riskeyes_v2/alarmbox.py

from django.conf import settings
from django.db import models

from lib.crypt import Crypt


class AlarmboxToken(models.Model):
    """
    AlarmBox API トークン管理用テーブル
    常に 1 レコードのみで運用

    access_token, refresh_token は暗号化して保存される
    """

    # DB には暗号化された値を保存
    access_token = models.CharField(max_length=512)
    refresh_token = models.CharField(max_length=512)
    expired_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hansha_alarmbox_tokens"

    def save(self, *args, **kwargs):
        # 常に id=1 で保存（1 レコードのみ許可）
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls) -> "AlarmboxToken":
        """唯一の 1 レコードのインスタンスを取得"""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                "access_token": "",
                "refresh_token": "",
                "expired_at": None,
            },
        )
        return obj

    # ===== 暗号化/復号 =====

    @staticmethod
    def _get_crypt() -> Crypt:
        """Crypt インスタンスを取得"""
        return Crypt(config=settings.CRYPT)

    @classmethod
    def encrypt(cls, value: str) -> str:
        """文字列を暗号化"""
        if not value:
            return ""
        crypt = cls._get_crypt()
        return crypt.encode(value.encode("utf-8"))

    @classmethod
    def decrypt(cls, value: str) -> str:
        """暗号化された文字列を復号"""
        if not value:
            return ""
        crypt = cls._get_crypt()
        decrypted = crypt.decode(value)
        return decrypted.decode("utf-8") if decrypted else ""

    def get_decrypted_access_token(self) -> str:
        """復号した access_token を取得"""
        return self.decrypt(self.access_token)

    def get_decrypted_refresh_token(self) -> str:
        """復号した refresh_token を取得"""
        return self.decrypt(self.refresh_token)

    def set_encrypted_access_token(self, value: str) -> None:
        """access_token を暗号化して設定"""
        self.access_token = self.encrypt(value)

    def set_encrypted_refresh_token(self, value: str) -> None:
        """refresh_token を暗号化して設定"""
        self.refresh_token = self.encrypt(value)
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
            # Content-Type は requests が自動設定（json= で application/json）
        }

    # ========== 内部メソッド ==========

    @classmethod
    def _request(cls, method: str, url: str, **kwargs) -> requests.Response:
        """HTTP リクエスト実行（例外処理付き）"""
        try:
            return requests.request(method, url, **kwargs)
        except Timeout:
            raise AlarmboxAPIError('タイムアウト: AlarmBox API に接続できません')
        except ConnectionError:
            raise AlarmboxAPIError('接続エラー: AlarmBox API に接続できません')
        except RequestException as e:
            raise AlarmboxAPIError(f'リクエストエラー: {e}')

    @classmethod
    def _handle_response(cls, response: requests.Response, expected_status: int = 200) -> dict:
        """レスポンス処理（ステータスチェック + JSONパース）"""
        if response.status_code != expected_status:
            raise AlarmboxAPIError(
                message=f'APIエラー: {response.status_code}',
                status_code=response.status_code,
                response_body=response.text,
            )
        try:
            return response.json()
        except json.JSONDecodeError:
            raise AlarmboxAPIError(f'JSONパースエラー: {response.text[:200]}')

    @classmethod
    def _post_form(cls, url: str, payload: dict, expected_status: int = 200) -> dict:
        """
        フォーム形式の POST リクエスト（OAuth 用）

        Content-Type: application/x-www-form-urlencoded
        """
        response = cls._request('POST', url, data=payload, timeout=30)
        return cls._handle_response(response, expected_status)

    @classmethod
    def _post_json(cls, url: str, payload: dict, headers: dict, expected_status: int = 200) -> dict:
        """
        JSON 形式の POST リクエスト（REST API 用）

        Content-Type: application/json
        """
        response = cls._request('POST', url, json=payload, headers=headers, timeout=30)
        return cls._handle_response(response, expected_status)

    # ========== 公開メソッド ==========

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
        return cls._post_form(url, payload)

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
        return cls._post_form(url, payload)
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

### ロック機構について

トークン更新時は競合を防ぐためロックを取得する。

- バッチ vs View の競合を防止
- View vs View の競合を防止（バッチ失敗時のフォールバック）

```python
# lib/alarmbox/token_service.py

from datetime import datetime, timedelta

from core.lib.lock import LockManager
from core.models.riskeyes_v2.alarmbox import AlarmboxToken
from lib.alarmbox.client import AlarmboxClient
from lib.alarmbox.exceptions import (
    AlarmboxTokenExpiredError,
    AlarmboxTokenNotFoundError,
)


class TokenService:
    """
    AlarmBox API のトークンを管理するサービス
    """

    # 期限切れ判定のマージン（5分前から期限切れ扱い）
    EXPIRY_MARGIN = timedelta(minutes=5)

    # ロック名（競合防止用）
    LOCK_NAME = "alarmbox-token-refresh"

    @classmethod
    def get_valid_access_token(cls) -> str:
        """
        有効な access_token を取得
        期限切れの場合は自動で更新する

        Returns:
            有効な access_token（復号済み）

        Raise:
            AlarmboxTokenNotFoundError: トークンが未設定
            AlarmboxTokenExpiredError: トークン更新に失敗
        """

        token = AlarmboxToken.get_instance()

        # トークンが未設定の場合
        if not token.access_token or not token.refresh_token:
            raise AlarmboxTokenNotFoundError(
                "トークンが未設定です。save_alarmbox_token コマンドで初回設定を行ってください。"
            )

        if cls._is_expired(token.expired_at):
            cls._refresh_token(token)

        return token.get_decrypted_access_token()

    @classmethod
    def _is_expired(cls, expired_at) -> bool:
        """トークンの期限切れを判定"""

        if expired_at is None:
            return True
        return datetime.now() >= (expired_at - cls.EXPIRY_MARGIN)

    @classmethod
    def _refresh_token(cls, token: AlarmboxToken, force: bool = False) -> None:
        """トークン更新とDB保存（ロック付き）

        Args:
            token: AlarmboxToken インスタンス
            force: True の場合、期限切れチェックをスキップして強制更新
        """

        lock_manager = LockManager(name=cls.LOCK_NAME, parallelism=1)

        try:
            with lock_manager.lock(timeout=30):
                # ロック取得後、再度期限切れチェック（他のプロセスが更新済みの可能性）
                token.refresh_from_db()
                if not force and not cls._is_expired(token.expired_at):
                    return  # 既に更新済み

                # 復号した refresh_token で API 呼び出し
                result = AlarmboxClient.refresh_token(
                    token.get_decrypted_refresh_token()
                )

                # 暗号化して DB 保存
                token.set_encrypted_access_token(result["access_token"])
                token.set_encrypted_refresh_token(result["refresh_token"])
                token.expired_at = datetime.now() + timedelta(
                    seconds=result["expires_in"]
                )
                token.save()

        except Exception as e:
            raise AlarmboxTokenExpiredError(f"トークンの更新に失敗しました: {e}")

    @classmethod
    def save_initial_token(
        cls, access_token: str, refresh_token: str, expires_in: int
    ) -> AlarmboxToken:
        """
        初回認証後のトークンを保存

        Args:
            access_token: AlarmBox の access_token（平文）
            refresh_token: AlarmBox の refresh_token（平文）
            expires_in: access_token の有効期限（秒）

        Returns:
            保存した AlarmboxToken インスタンス
        """

        token = AlarmboxToken.get_instance()
        # 暗号化して保存
        token.set_encrypted_access_token(access_token)
        token.set_encrypted_refresh_token(refresh_token)
        token.expired_at = datetime.now() + timedelta(seconds=expires_in)
        token.save()
        return token
```

### ロック取得後の再チェック

```python
# ロック取得後、再度期限切れチェック（他のプロセスが更新済みの可能性）
token.refresh_from_db()
if not cls._is_expired(token.expired_at):
    return  # 既に更新済み
```

なぜ必要か：

```
ユーザーA: ロック待ち中...
ユーザーB: ロック取得 → トークン更新 → ロック解放
ユーザーA: ロック取得 → 再チェック → 「あ、もう更新されてる」→ 何もしない
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
```

※ セキュリティ上、トークンの中身は出力しない

---

## Step 7: バッチコマンド作成

12時間ごとにトークンを更新するバッチを作成。

```python
# core/management/commands/refresh_alarmbox_token.py

from core.contrib.management.cloud_run_jobs.command import CloudRunJobs
from core.models.riskeyes_v2.alarmbox import AlarmboxToken
from lib.alarmbox.token_service import TokenService


class Command(CloudRunJobs):
    """AlarmBox のトークンを定期更新するバッチ"""

    help = "AlarmBox トークンを更新します"

    # 12時間ごとに実行
    schedule = "0 */12 * * *"

    def run(self, *args, **options):
        token = AlarmboxToken.get_instance()

        if not token.refresh_token:
            self.stdout.write(
                self.style.ERROR(
                    "トークンが未設定です。save_alarmbox_token コマンドで初回設定を行ってください。"
                )
            )
            return

        self.stdout.write("トークンを更新中...")

        # バッチは強制更新（期限切れチェックをスキップ）
        TokenService._refresh_token(token, force=True)

        self.stdout.write(self.style.SUCCESS("トークンを更新しました"))
```

### バッチ vs フォールバック

| 項目 | バッチ | フォールバック（View） |
|------|--------|------------------------|
| タイミング | 12時間ごと | ユーザーリクエスト時（期限切れの場合のみ） |
| 呼び出し元 | CloudRunJobs | TokenService.get_valid_access_token() |
| ロック | CloudRunJobs + TokenService | TokenService |

---

## Step 8: 動作確認

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
