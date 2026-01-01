# AlarmBox API 連携 実装ガイド

バックエンド初心者向けに、Django での実装方法を基礎から解説します。

---

## 目次

1. [全体像を理解する](#1-全体像を理解する)
2. [実装の流れ](#2-実装の流れ)
3. [Step 1: Model を作成する](#step-1-model-を作成する)
4. [Step 2: Migration を実行する](#step-2-migration-を実行する)
5. [Step 3: AlarmBox API クライアントを作成する](#step-3-alarmbox-api-クライアントを作成する)
6. [Step 4: トークン管理サービスを作成する](#step-4-トークン管理サービスを作成する)
7. [Step 5: Serializer を作成する](#step-5-serializer-を作成する)
8. [Step 6: View を作成する](#step-6-view-を作成する)
9. [Step 7: URL ルーティングを設定する](#step-7-url-ルーティングを設定する)
10. [用語解説](#用語解説)

---

## 1. 全体像を理解する

### やりたいこと

```
RiskEyes CLI（フロント）
    ↓ 購入ボタンを押す
RiskEyes API（バックエンド）← 今回実装するところ
    ↓ AlarmBox API を呼び出す
AlarmBox API
    ↓ 信用チェック結果を返す
RiskEyes API
    ↓ 結果を DB に保存
RiskEyes CLI
    ↓ 結果を表示
```

### 実装するもの

| 種類       | 役割                                           | ファイル         |
| ---------- | ---------------------------------------------- | ---------------- |
| Model      | DB テーブルの定義                              | `models.py`      |
| Serializer | データ変換・バリデーション                     | `serializers.py` |
| Service    | ビジネスロジック（API 呼び出し、トークン管理） | `services/`      |
| View       | HTTP リクエストを受け取り、レスポンスを返す    | `views.py`       |
| URL        | エンドポイントの定義                           | `urls.py`        |

### 実装するディレクトリ構造

```
riskeyes-v2-api/
├── core/
│   ├── models/
│   │   └── riskeyes_v2/
│   │       └── alarmbox.py          # Model（トークン、信用チェック結果）
│   └── management/
│       └── commands/
│           └── save_alarmbox_token.py  # 初回トークン登録コマンド
│
├── lib/
│   └── alarmbox/                    # AlarmBox API 連携
│       ├── __init__.py
│       ├── client.py                # API クライアント（認証込み）
│       ├── token_service.py         # トークン管理サービス
│       ├── exceptions.py            # 例外定義
│       └── types.py                 # 型定義（必要なら）
│
└── customer/
    ├── serializers/
    │   └── alarmbox.py              # Serializer
    ├── views/
    │   └── alarmbox.py              # View
    └── urls.py                      # URL 追記
```

### 各ディレクトリの役割

| ディレクトリ                | 役割                    | 今回追加するもの                        |
| --------------------------- | ----------------------- | --------------------------------------- |
| `core/models/`              | 全アプリ共通の Model    | トークン管理、信用チェック結果の Model  |
| `core/management/commands/` | Django 管理コマンド     | 初回トークン登録コマンド                |
| `lib/`                      | 外部 API クライアント   | AlarmBox API クライアント、トークン管理 |
| `customer/serializers/`     | 取引先機能の Serializer | 信用チェック購入のバリデーション        |
| `customer/views/`           | 取引先機能の View       | 信用チェック購入 API                    |
| `customer/urls.py`          | 取引先機能の URL        | エンドポイント追加                      |

### 呼び出しの流れ

```
customer/views/alarmbox.py        # View（リクエスト受付）
    ↓
customer/serializers/alarmbox.py  # Serializer（バリデーション）
    ↓
lib/alarmbox/client.py            # API クライアント（AlarmBox 呼び出し）
    ↓
lib/alarmbox/token_service.py     # トークン管理（自動更新）
    ↓
core/models/.../alarmbox.py       # Model（トークン・結果の DB 操作）
```

---

## 2. 実装の流れ

```
Step 1: Model を作成（DB テーブル定義）
    ↓
Step 2: Migration を実行（DB に反映）
    ↓
Step 3: AlarmBox API クライアントを作成
    ↓
Step 4: トークン管理サービスを作成
    ↓
Step 5: Serializer を作成（バリデーション・データ変換）
    ↓
Step 6: View を作成（信用チェック購入 API）
    ↓
Step 7: URL ルーティングを設定
```

---

## Step 1: Model を作成する

### Model とは？

DB のテーブル構造を Python のクラスで定義するもの。
Django が自動的に SQL に変換してくれます。

### 作成するテーブル

今回は 3 つの Model を作成します：

1. **AlarmboxToken** - トークン管理（1 レコード固定）
2. **AlarmboxCreditCheck** - 信用チェック結果（メイン）
3. **AlarmboxCreditCheckInfo** - リスク情報（詳細）

### コード例

```python
# core/models/riskeyes_v2/alarmbox.py

from django.db import models
import uuid

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
    def get_instance(cls):
        """唯一のインスタンスを取得"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class AlarmboxCreditCheck(models.Model):
    """
    信用チェック結果を保存するメインテーブル
    """
    RESULT_CHOICES = [
        ('ok', '低リスク'),
        ('hold', '中リスク'),
        ('ng', '高リスク'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.IntegerField()  # 外部キー（client テーブル）
    credit_check_id = models.IntegerField()  # AlarmBox 側の ID
    corporate_number = models.CharField(max_length=13)  # 法人番号
    company_name = models.CharField(max_length=255)
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, null=True)
    purchased_at = models.DateTimeField()
    expired_at = models.DateTimeField()
    pdf_file_path = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hansha_alarmbox_credit_checks'


class AlarmboxCreditCheckInfo(models.Model):
    """
    信用チェックのリスク情報（詳細）
    AlarmboxCreditCheck と 1:N の関係
    """
    alarmbox_credit_check = models.ForeignKey(
        AlarmboxCreditCheck,
        on_delete=models.CASCADE,
        related_name='infos'
    )
    received_on = models.DateField()
    tag = models.CharField(max_length=100)
    description = models.TextField()
    source = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hansha_alarmbox_credit_check_infos'
```

### 解説

| コード                             | 意味                           |
| ---------------------------------- | ------------------------------ |
| `models.CharField(max_length=255)` | 文字列型（最大 255 文字）      |
| `models.DateTimeField()`           | 日時型                         |
| `models.IntegerField()`            | 整数型                         |
| `models.TextField()`               | 長いテキスト型                 |
| `auto_now=True`                    | 更新時に自動で現在時刻をセット |
| `auto_now_add=True`                | 作成時に自動で現在時刻をセット |
| `models.ForeignKey()`              | 外部キー（他テーブルへの参照） |
| `on_delete=models.CASCADE`         | 親が削除されたら子も削除       |

---

## Step 2: Migration を実行する

### Migration とは？

Model の変更を DB に反映するための仕組み。
Model を書いただけでは DB は変わらない。Migration を実行して初めて反映される。

### コマンド

```bash
# 1. Migration ファイルを生成
python manage.py makemigrations

# 2. Migration を実行（DB に反映）
python manage.py migrate
```

### 実行結果（例）

```
$ python manage.py makemigrations
Migrations for 'app_name':
  app_name/migrations/0001_initial.py
    - Create model AlarmboxToken
    - Create model AlarmboxCreditCheck
    - Create model AlarmboxCreditCheckInfo

$ python manage.py migrate
Operations to perform:
  Apply all migrations: ...
Running migrations:
  Applying app_name.0001_initial... OK
```

---

## Step 3: AlarmBox API クライアントを作成する

### API クライアントとは？

外部 API（AlarmBox）を呼び出すためのクラス。
HTTP リクエストの詳細を隠蔽し、使いやすいメソッドを提供する。

### コード例

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


class CreditCheckPurchaseResponse(TypedDict):
    """信用チェック購入のレスポンス"""
    id: int


class CreditCheckDetailResponse(TypedDict):
    """信用チェック詳細のレスポンス"""
    id: int
    result: str
    purchased_at: str
    expired_at: str
    infos: list
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
    CreditCheckPurchaseResponse,
    CreditCheckDetailResponse,
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

    def purchase_credit_check(self, corporate_number: str) -> CreditCheckPurchaseResponse:
        """
        信用チェックを購入する
        POST /ps/v1/credit_checks
        """
        url = f'{self.BASE_URL}/ps/v1/credit_checks'
        payload = {'corporate_number': corporate_number}

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        except Timeout:
            raise AlarmboxAPIError('タイムアウト: AlarmBox API に接続できません')
        except ConnectionError:
            raise AlarmboxAPIError('接続エラー: AlarmBox API に接続できません')
        except RequestException as e:
            raise AlarmboxAPIError(f'リクエストエラー: {e}')

        if response.status_code != 201:
            raise AlarmboxAPIError(
                message=f'購入失敗: {response.status_code}',
                status_code=response.status_code,
                response_body=response.text
            )

        try:
            return response.json()
        except json.JSONDecodeError:
            raise AlarmboxAPIError(f'JSONパースエラー: {response.text[:200]}')

    def get_credit_check(self, credit_check_id: int) -> CreditCheckDetailResponse:
        """
        信用チェックの詳細を取得する
        GET /ps/v1/credit_checks/{id}
        """
        url = f'{self.BASE_URL}/ps/v1/credit_checks/{credit_check_id}'

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
        except Timeout:
            raise AlarmboxAPIError('タイムアウト: AlarmBox API に接続できません')
        except ConnectionError:
            raise AlarmboxAPIError('接続エラー: AlarmBox API に接続できません')
        except RequestException as e:
            raise AlarmboxAPIError(f'リクエストエラー: {e}')

        if response.status_code != 200:
            raise AlarmboxAPIError(
                message=f'取得失敗: {response.status_code}',
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

### 解説

| メソッド                  | 用途                                                 |
| ------------------------- | ---------------------------------------------------- |
| `_post_request()`         | 共通の POST リクエスト処理（エラーハンドリング込み） |
| `purchase_credit_check()` | 信用チェックを購入（POST）                           |
| `get_credit_check()`      | 信用チェック詳細を取得（GET）                        |
| `get_token_by_code()`     | 認可コードからトークン取得（初回認証）               |
| `refresh_token()`         | トークンを更新（POST）                               |

### エラーハンドリング

| 例外                      | 状況                                              |
| ------------------------- | ------------------------------------------------- |
| `Timeout`                 | 接続/読み取りタイムアウト（30 秒）                |
| `ConnectionError`         | DNS 解決失敗、接続拒否、ネットワーク断            |
| `RequestException`        | その他の requests エラー全般                      |
| `json.JSONDecodeError`    | API が壊れた HTML やエラーページを返した時        |
| `status_code != expected` | API がエラーステータスを返した時（401, 500 など） |

---

## Step 4: トークン管理サービスを作成する

### このサービスの役割

- トークンの取得
- 期限切れチェック
- 自動更新

### コード例

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
        """
        token = AlarmboxToken.get_instance()

        # トークンが未設定の場合
        if not token.access_token or not token.refresh_token:
            raise AlarmboxTokenNotFoundError('トークンが未設定です。初回認証を行ってください。')

        # 期限切れチェック（5分の余裕を持たせる）
        if cls._is_expired(token.expired_at):
            cls._refresh_token(token)

        return token.access_token

    @classmethod
    def _is_expired(cls, expired_at: datetime) -> bool:
        """
        トークンが期限切れかどうか判定
        5分前から「期限切れ」とみなす（安全マージン）
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
            # AlarmBox API でトークン更新
            result = AlarmboxClient.refresh_token(token.refresh_token)
        except Exception as e:
            raise AlarmboxTokenExpiredError(f'トークンの更新に失敗しました: {e}')

        # DB を更新
        token.access_token = result['access_token']
        token.refresh_token = result['refresh_token']
        token.expired_at = datetime.now() + timedelta(seconds=result['expires_in'])
        token.save()

    @classmethod
    def save_initial_token(cls, access_token: str, refresh_token: str, expires_in: int) -> AlarmboxToken:
        """
        初回認証後のトークンを保存する
        """
        token = AlarmboxToken.get_instance()
        token.access_token = access_token
        token.refresh_token = refresh_token
        token.expired_at = datetime.now() + timedelta(seconds=expires_in)
        token.save()
        return token
```

### 解説

| メソッド                   | 用途                                   |
| -------------------------- | -------------------------------------- |
| `get_valid_access_token()` | 有効なトークンを取得（自動更新込み）   |
| `_is_expired()`            | 期限切れ判定（5 分前から期限切れ扱い） |
| `_refresh_token()`         | トークン更新 & DB 保存                 |
| `save_initial_token()`     | 初回トークン保存                       |

### なぜ 5 分前から期限切れとするか？

```
API 呼び出し開始 → 処理中に期限切れ → エラー！

これを防ぐために余裕を持たせる
```

---

## Step 5: Serializer を作成する

### Serializer とは？

**データの変換・検証を担当するクラス**

```
リクエスト JSON → Python オブジェクト（デシリアライズ）
Python オブジェクト → レスポンス JSON（シリアライズ）
```

Django REST Framework の標準的な構成要素です。

### なぜ必要？

View に直接バリデーションを書くと：

- View が肥大化する
- 同じバリデーションを複数箇所に書くことになる
- テストしにくい

Serializer に分離すると：

- View が薄くなる
- 再利用できる
- テストしやすい

### コード例

```python
# customer/serializers/alarmbox.py

from rest_framework import serializers


class CreditCheckPurchaseSerializer(serializers.Serializer):
    """
    信用チェック購入リクエストのバリデーション
    """
    client_id = serializers.IntegerField(
        required=True,
        help_text='取引先ID'
    )
    corporate_number = serializers.CharField(
        required=True,
        max_length=13,
        min_length=13,
        help_text='法人番号（13桁）'
    )
    company_name = serializers.CharField(
        required=True,
        max_length=255,
        help_text='企業名'
    )

    def validate_corporate_number(self, value):
        """法人番号のカスタムバリデーション"""
        if not value.isdigit():
            raise serializers.ValidationError('法人番号は数字のみです')
        return value


class CreditCheckResponseSerializer(serializers.Serializer):
    """
    信用チェック購入レスポンスの整形
    """
    id = serializers.UUIDField()
    result = serializers.CharField()
    corporate_number = serializers.CharField()
    company_name = serializers.CharField()
    purchased_at = serializers.DateTimeField()
    expired_at = serializers.DateTimeField()


class CreditCheckInfoSerializer(serializers.Serializer):
    """
    リスク情報のシリアライザ
    """
    received_on = serializers.DateField()
    tag = serializers.CharField()
    description = serializers.CharField()
    source = serializers.CharField(allow_null=True)


class CreditCheckDetailSerializer(serializers.Serializer):
    """
    信用チェック詳細（リスク情報含む）
    """
    id = serializers.UUIDField()
    result = serializers.CharField()
    corporate_number = serializers.CharField()
    company_name = serializers.CharField()
    purchased_at = serializers.DateTimeField()
    expired_at = serializers.DateTimeField()
    infos = CreditCheckInfoSerializer(many=True)
```

### 解説

| クラス                          | 用途                         |
| ------------------------------- | ---------------------------- |
| `CreditCheckPurchaseSerializer` | リクエストのバリデーション   |
| `CreditCheckResponseSerializer` | レスポンスの整形             |
| `CreditCheckInfoSerializer`     | リスク情報の整形             |
| `CreditCheckDetailSerializer`   | 詳細情報（infos 含む）の整形 |

### フィールドの種類

| フィールド                    | 用途   |
| ----------------------------- | ------ |
| `serializers.IntegerField()`  | 整数   |
| `serializers.CharField()`     | 文字列 |
| `serializers.UUIDField()`     | UUID   |
| `serializers.DateTimeField()` | 日時   |
| `serializers.DateField()`     | 日付   |

### バリデーションオプション

| オプション        | 意味        |
| ----------------- | ----------- |
| `required=True`   | 必須        |
| `max_length=255`  | 最大文字数  |
| `min_length=13`   | 最小文字数  |
| `allow_null=True` | null を許可 |

### カスタムバリデーション

`validate_<フィールド名>` メソッドで独自のバリデーションを追加できる：

```python
def validate_corporate_number(self, value):
    if not value.isdigit():
        raise serializers.ValidationError('法人番号は数字のみです')
    return value
```

---

## Step 6: View を作成する

### View とは？

HTTP リクエストを受け取り、処理して、レスポンスを返すもの。
フロント（CLI）とバックエンドの接点。

### コード例（Serializer を使う版）

```python
# customer/views/alarmbox.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.models.riskeyes_v2.alarmbox import AlarmboxCreditCheck, AlarmboxCreditCheckInfo
from customer.serializers.alarmbox import (
    CreditCheckPurchaseSerializer,
    CreditCheckResponseSerializer,
)
from lib.alarmbox.token_service import TokenService
from lib.alarmbox.client import AlarmboxClient, AlarmboxAPIError


class CreditCheckPurchaseView(APIView):
    """
    信用チェック購入 API
    POST /api/alarmbox/credit-checks/
    """

    def post(self, request):
        # 1. Serializer でバリデーション
        serializer = CreditCheckPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. バリデーション済みデータを取得
        data = serializer.validated_data
        client_id = data['client_id']
        corporate_number = data['corporate_number']
        company_name = data['company_name']

        try:
            # 3. 有効なトークンを取得
            access_token = TokenService.get_valid_access_token()

            # 4. AlarmBox API クライアントを作成
            client = AlarmboxClient(access_token)

            # 5. 信用チェックを購入
            purchase_result = client.purchase_credit_check(corporate_number)
            credit_check_id = purchase_result['id']

            # 6. 信用チェック詳細を取得
            detail = client.get_credit_check(credit_check_id)

            # 7. DB に保存
            credit_check = AlarmboxCreditCheck.objects.create(
                client_id=client_id,
                credit_check_id=credit_check_id,
                corporate_number=corporate_number,
                company_name=company_name,
                result=detail.get('result'),
                purchased_at=detail.get('purchased_at'),
                expired_at=detail.get('expired_at'),
            )

            # 8. リスク情報を保存
            for info in detail.get('infos', []):
                AlarmboxCreditCheckInfo.objects.create(
                    alarmbox_credit_check=credit_check,
                    received_on=info.get('received_on'),
                    tag=info.get('tag'),
                    description=info.get('description'),
                    source=info.get('source'),
                )

            # 9. レスポンスを Serializer で整形して返す
            response_serializer = CreditCheckResponseSerializer(credit_check)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        except AlarmboxAPIError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            return Response(
                {'error': f'予期しないエラー: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
```

### Serializer を使うメリット

**Before（Serializer なし）:**

```python
client_id = request.data.get('client_id')
corporate_number = request.data.get('corporate_number')

if not all([client_id, corporate_number, company_name]):
    return Response({'error': '必須パラメータが不足'}, ...)
```

**After（Serializer あり）:**

```python
serializer = CreditCheckPurchaseSerializer(data=request.data)
if not serializer.is_valid():
    return Response(serializer.errors, ...)  # エラー詳細が自動で返る

data = serializer.validated_data  # 型変換済みのデータ
```

### 処理の流れ

```
1. Serializer でバリデーション
    ↓
2. バリデーション済みデータ取得
    ↓
3. 有効なトークンを取得（自動更新込み）
    ↓
4. AlarmBox API クライアント作成
    ↓
5. 信用チェック購入（POST /ps/v1/credit_checks）
    ↓
6. 詳細取得（GET /ps/v1/credit_checks/{id}）
    ↓
7. メインテーブルに保存
    ↓
8. リスク情報テーブルに保存
    ↓
9. レスポンス Serializer で整形して返却
```

---

## Step 7: URL ルーティングを設定する

### URL ルーティングとは？

「この URL にアクセスしたら、この View を呼び出す」という対応付け。

### コード例

```python
# customer/urls.py（既存ファイルに追記）

from django.urls import path
from .views.alarmbox import CreditCheckPurchaseView

# 既存の urlpatterns に追加
urlpatterns = [
    # ... 既存のパス ...
    path('/alarmbox/credit-checks', CreditCheckPurchaseView.as_view(), name='alarmbox-credit-check-purchase'),
]
```

### 結果

```
POST /api/customer/alarmbox/credit-checks
→ CreditCheckPurchaseView.post() が呼ばれる
```

---

## 用語解説

### Django 用語

| 用語             | 意味                                         |
| ---------------- | -------------------------------------------- |
| Model            | DB テーブルの Python クラス表現              |
| Migration        | Model の変更を DB に反映する仕組み           |
| View             | HTTP リクエストを処理するクラス/関数         |
| URL ルーティング | URL と View の対応付け                       |
| ORM              | SQL を書かずに Python で DB 操作できる仕組み |

### HTTP ステータスコード

| コード | 意味                  | 使う場面         |
| ------ | --------------------- | ---------------- |
| 200    | OK                    | 取得成功         |
| 201    | Created               | 作成成功         |
| 400    | Bad Request           | リクエストが不正 |
| 401    | Unauthorized          | 認証エラー       |
| 500    | Internal Server Error | サーバーエラー   |
| 502    | Bad Gateway           | 外部 API エラー  |

### 設計パターン

| パターン      | 説明                                     |
| ------------- | ---------------------------------------- |
| Service 層    | ビジネスロジックを View から分離         |
| Client クラス | 外部 API 呼び出しを抽象化                |
| Repository    | DB アクセスを抽象化（今回は ORM で代用） |

---

## 次のステップ

1. 既存の RiskEyes API のコード構造を確認
2. 命名規則やディレクトリ構造を合わせる
3. 各 Step を順番に実装
4. テストを書く

---

## 補足：設定ファイル

このプロジェクトでは、環境ごとに設定ファイルが分かれている：

```
core/config/
├── _base_settings.py    # ベース設定（ローカル用ダミー値）
├── local.py             # ローカル開発
├── devserver.py         # Dev サーバー
├── staging.py           # Staging
├── production.py        # 本番
└── test.py              # テスト
```

### AlarmBox 設定の追加

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

payload = {
    'client_id': settings.ALARMBOX_INFO["client_id"],
    'client_secret': settings.ALARMBOX_INFO["client_secret"],
    ...
}
```

### GCP Secret Manager

本番/Dev/Staging 環境では GCP Secret Manager から機密情報を取得する。
`core/lib/google_cloud.py` に `get_json_secret()` メソッドがある。

```python
# GCP Secret Manager に登録する JSON
{
    "client_id": "ZYNFzaZcD621H3XKOftN4EfDJX4noMwYQZSdc004xKA",
    "client_secret": "q_Qr14VQml1b4vPw7dWeDK_tsotcUGV7Ri5i7TLFBUE"
}
```
