# 信用チェック実装ガイド

AlarmBox API の信用チェック購入・取得・DB 保存・エンドポイントを実装する手順を解説します。

---

## 目標

**CLI から信用チェックを購入し、結果を取得・保存できる状態にする**

---

## 実装するファイル

| ファイル                               | 役割                                        |
| -------------------------------------- | ------------------------------------------- |
| `core/models/riskeyes_v2/alarmbox.py`  | 信用チェック保存用 Model（追記）            |
| `lib/alarmbox/types.py`                | 信用チェック関連の型定義（追記）            |
| `lib/alarmbox/exceptions.py`           | 信用チェック関連の例外（追記）              |
| `lib/alarmbox/client.py`               | 信用チェック API メソッド（追記）           |
| `lib/alarmbox/credit_check_service.py` | 信用チェック購入〜保存のサービス（新規）    |
| `customer/serializers/alarmbox.py`     | リクエスト/レスポンスのシリアライザ（新規） |
| `customer/views/alarmbox.py`           | API エンドポイント（新規）                  |
| `customer/urls.py`                     | URL ルーティング（追記）                    |

---

## 実装手順

```
Step 1: Model 作成（信用チェック保存用テーブル）
    ↓
Step 2: Migration 実行
    ↓
Step 3: 型定義の追加
    ↓
Step 4: 例外クラスの追加
    ↓
Step 5: API クライアントに信用チェックメソッド追加
    ↓
Step 6: 信用チェックサービス作成（購入〜PDF保存〜DB保存）
    ↓
Step 7: Serializer 作成
    ↓
Step 8: View 作成
    ↓
Step 9: URL 追加
    ↓
Step 10: 動作確認
```

---

## Step 1: Model 作成

### 既存ファイルに追記

```python
# core/models/riskeyes_v2/alarmbox.py

from lib.uuid import uuid7  # プロジェクト共通のUUIDv7生成関数

# 既存の AlarmboxToken クラスの下に追加

class HanshaAlarmboxCreditCheck(models.Model):
    """
    AlarmBox 信用チェック結果テーブル
    """

    id = models.UUIDField(primary_key=True, default=uuid7)
    client_id = models.IntegerField(db_index=True)  # 一覧取得で使うためindex
    credit_check_id = models.IntegerField()  # AlarmBox 側の ID
    corporation_number = models.CharField(max_length=13)
    company_name = models.CharField(max_length=255)
    result = models.CharField(max_length=10, null=True)  # ok/hold/ng
    purchased_at = models.DateTimeField()
    expired_at = models.DateTimeField()
    pdf_file_path = models.CharField(max_length=500, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hansha_alarmbox_credit_checks"

    def __str__(self):
        return f"{self.company_name} ({self.credit_check_id})"


class HanshaAlarmboxCreditCheckInfo(models.Model):
    """
    信用チェックのリスク情報テーブル
    """

    alarmbox_credit_check = models.ForeignKey(
        HanshaAlarmboxCreditCheck,
        on_delete=models.CASCADE,
        related_name="infos",
    )
    received_on = models.DateField()
    tag = models.CharField(max_length=100)
    description = models.TextField()
    source = models.CharField(max_length=100, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hansha_alarmbox_credit_check_infos"

    def __str__(self):
        return f"{self.tag}: {self.description[:30]}"
```

### **init**.py に追記

```python
# core/models/riskeyes_v2/__init__.py

from .alarmbox import (
    AlarmboxToken,
    HanshaAlarmboxCreditCheck,
    HanshaAlarmboxCreditCheckInfo,
)
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
mysql -u root -p -e "DESCRIBE hansha_alarmbox_credit_checks;"
mysql -u root -p -e "DESCRIBE hansha_alarmbox_credit_check_infos;"
```

---

## Step 3: 型定義の追加

```python
# lib/alarmbox/types.py

# 既存の型定義の下に追加

# --- 信用チェック リクエスト型 ---

class CreditCheckPurchaseRequest(TypedDict, total=False):
    """信用チェック購入リクエスト"""
    corporation_number: str  # 必須: 13桁の法人番号
    deal: int                # 任意: 取引関係 (1=有, 2=無, 9=その他)
    purchase_reasons: list   # 任意: 購入理由IDの配列
    purchase_reason_comment: str  # 任意: 理由の補足コメント


class CreditCheckGetParams(TypedDict, total=False):
    """信用チェック取得クエリパラメータ"""
    with_pdf: bool


# --- 信用チェック レスポンス型 ---

class CreditCheckTag(TypedDict):
    """信用チェックのタグ情報"""
    name: str
    description: str
    source: str


class CreditCheckInfo(TypedDict):
    """信用チェックの情報履歴"""
    received_date: str  # yyyy-mm-dd
    tags: list[CreditCheckTag]


class CreditCheckResponse(TypedDict, total=False):
    """信用チェック取得レスポンス"""
    credit_check_id: int
    purchase_date: str       # yyyy-mm-dd
    expiration_date: str     # yyyy-mm-dd
    corporation_name: str
    corporation_number: str
    result: str              # ok/hold/ng/null
    expired: bool
    pdf_file_data: str       # Base64エンコードされたPDF
    infos: list[CreditCheckInfo]


class CreditCheckPurchaseResponse(TypedDict):
    """信用チェック購入レスポンス"""
    credit_check: CreditCheckResponse
```

---

## Step 4: 例外クラスの追加

```python
# lib/alarmbox/exceptions.py

# 既存の例外クラスの下に追加

class AlarmboxCreditCheckError(AlarmboxAPIError):
    """信用チェック関連のエラー"""
    pass


class AlarmboxCreditCheckNotFoundError(AlarmboxCreditCheckError):
    """信用チェックが見つからない"""
    pass
```

---

## Step 5: API クライアントに信用チェックメソッド追加

### 5-1. 内部メソッド

`01_authentication.md` で作成した内部メソッドを使用します。

```python
# lib/alarmbox/client.py

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
    """フォーム形式の POST リクエスト（OAuth 用）"""
    response = cls._request('POST', url, data=payload, timeout=30)
    return cls._handle_response(response, expected_status)

@classmethod
def _post_json(cls, url: str, payload: dict, headers: dict, expected_status: int = 200) -> dict:
    """JSON 形式の POST リクエスト（REST API 用）"""
    response = cls._request('POST', url, json=payload, headers=headers, timeout=30)
    return cls._handle_response(response, expected_status)
```

### 5-2. 信用チェックメソッドの追加（公開メソッド）

内部メソッドを使って簡潔に実装します。

```python
# lib/alarmbox/client.py

# 既存の import に追加
from lib.alarmbox.types import (
    AuthorizationCodeRequest,
    RefreshTokenRequest,
    TokenResponse,
    CreditCheckPurchaseRequest,
    CreditCheckGetParams,
    CreditCheckPurchaseResponse,
    CreditCheckResponse,
)
from lib.alarmbox.exceptions import (
    AlarmboxAPIError,
    AlarmboxCreditCheckNotFoundError,
)

# AlarmboxClient クラス内に追加

    # ========== 公開メソッド ==========

    def purchase_credit_check(
        self,
        corporation_number: str,
        deal: int | None = None,
        purchase_reasons: list[int] | None = None,
        purchase_reason_comment: str | None = None,
    ) -> CreditCheckPurchaseResponse:
        """
        信用チェックを購入する
        POST /ps/v1/credit_checks

        Args:
            corporation_number: 13桁の法人番号
            deal: 取引関係 (1=有, 2=無, 9=その他)
            purchase_reasons: 購入理由IDの配列
            purchase_reason_comment: 購入理由コメント

        Returns:
            購入結果（credit_check_id を含む）
        """
        url = f"{self.BASE_URL}/ps/v1/credit_checks"
        payload: CreditCheckPurchaseRequest = {
            "corporation_number": corporation_number,
        }
        if deal is not None:
            payload["deal"] = deal
        if purchase_reasons is not None:
            payload["purchase_reasons"] = purchase_reasons
        if purchase_reason_comment is not None:
            payload["purchase_reason_comment"] = purchase_reason_comment

        return self._post_json(
            url=url,
            payload=payload,
            headers=self.headers,
        )

    def get_credit_check(
        self, credit_check_id: int, with_pdf: bool = False
    ) -> CreditCheckResponse:
        """
        信用チェックの詳細を取得する
        GET /ps/v1/credit_checks/{id}

        Args:
            credit_check_id: 信用チェックID
            with_pdf: PDFデータを含めるか

        Returns:
            信用チェックの詳細
        """
        url = f"{self.BASE_URL}/ps/v1/credit_checks/{credit_check_id}"

        params: CreditCheckGetParams = {}
        if with_pdf:
            params["with_pdf"] = True

        response = self._request("GET", url, headers=self.headers, params=params or None, timeout=60)
        result = self._handle_response(response)
        return result["credit_check"]
```

### 5-3. \_post_form と \_post_json の使い分け

| エンドポイント | メソッド     | 形式            | 理由                    |
| -------------- | ------------ | --------------- | ----------------------- |
| `/oauth/token` | `_post_form` | form-urlencoded | OAuth 2.0 の RFC 仕様   |
| `/ps/v1/*`     | `_post_json` | JSON            | REST API の一般的な仕様 |

**Content-Type は requests が自動設定：**

- `data=payload` → `application/x-www-form-urlencoded`
- `json=payload` → `application/json`

そのため、`self.headers` には `Authorization` のみ設定する：

```python
def __init__(self, access_token: str):
    self.access_token = access_token
    self.headers = {
        "Authorization": f"Bearer {access_token}",
        # Content-Type は不要（requests が自動設定）
    }
```

**使用例：**

```python
# OAuth トークン取得（form形式、ヘッダー不要）
cls._post_form(url, payload)

# 信用チェック購入（JSON形式、Authorization ヘッダーのみ）
self._post_json(url, payload, headers=self.headers)

# 信用チェック詳細取得（GET は _request + _handle_response を直接使用）
params: CreditCheckGetParams = {}
if with_pdf:
    params["with_pdf"] = True
response = self._request("GET", url, headers=self.headers, params=params or None, timeout=60)
result = self._handle_response(response)
```

---

## Step 6: 信用チェックサービス作成

購入 → 詳細取得 → PDF 保存 → DB 保存 の一連フローを実装。

```python
# lib/alarmbox/credit_check_service.py

import base64
import logging
from datetime import datetime
from io import BytesIO

import uuid_utils

from core.models.riskeyes_v2.alarmbox import (
    HanshaAlarmboxCreditCheck,
    HanshaAlarmboxCreditCheckInfo,
)
from lib.alarmbox.client import AlarmboxClient
from lib.alarmbox.token_service import TokenService
from lib.alarmbox.types import CreditCheckResponse
from lib.gcs_client import GCSClient

logger = logging.getLogger(__name__)


class CreditCheckService:
    """
    信用チェックの購入〜保存を行うサービス
    """

    # GCS保存時の機能名
    GCS_FEATURE_NAME = "alarmbox_credit_check"

    @classmethod
    def purchase_and_save(
        cls,
        client_id: int,
        corporation_number: str,
        deal: int | None = None,
        purchase_reasons: list[int] | None = None,
        purchase_reason_comment: str | None = None,
    ) -> HanshaAlarmboxCreditCheck:
        """
        信用チェックを購入し、結果をDBに保存する

        Args:
            client_id: RiskEyes のクライアントID
            corporation_number: 13桁の法人番号
            deal: 取引関係 (1=有, 2=無, 9=その他)
            purchase_reasons: 購入理由IDの配列
            purchase_reason_comment: 購入理由コメント

        Returns:
            保存した HanshaAlarmboxCreditCheck インスタンス
        """
        # 1. 有効なトークンを取得
        access_token = TokenService.get_valid_access_token()
        client = AlarmboxClient(access_token)

        # 2. 信用チェックを購入
        logger.info(f"信用チェック購入開始: {corporation_number}")
        purchase_result = client.purchase_credit_check(
            corporation_number=corporation_number,
            deal=deal,
            purchase_reasons=purchase_reasons,
            purchase_reason_comment=purchase_reason_comment,
        )
        credit_check_id = purchase_result["credit_check"]["credit_check_id"]
        logger.info(f"信用チェック購入完了: credit_check_id={credit_check_id}")

        # 3. 詳細を取得（PDF含む）
        logger.info(f"信用チェック詳細取得開始: credit_check_id={credit_check_id}")
        detail = client.get_credit_check(credit_check_id, with_pdf=True)
        logger.info(f"信用チェック詳細取得完了")

        # 4. PDFをGCSに保存
        pdf_file_path = None
        if detail.get("pdf_file_data"):
            pdf_file_path = cls._save_pdf_to_gcs(
                client_id=client_id,
                credit_check_id=credit_check_id,
                pdf_base64=detail["pdf_file_data"],
            )
            logger.info(f"PDF保存完了: {pdf_file_path}")

        # 5. DBに保存
        credit_check = cls._save_to_db(
            client_id=client_id,
            detail=detail,
            pdf_file_path=pdf_file_path,
        )
        logger.info(f"DB保存完了: id={credit_check.id}")

        return credit_check

    @classmethod
    def _save_pdf_to_gcs(
        cls,
        client_id: int,
        credit_check_id: int,
        pdf_base64: str,
    ) -> str:
        """
        Base64エンコードされたPDFをGCSに保存

        Returns:
            GCSのファイルパス
        """
        # Base64デコード
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_file = BytesIO(pdf_bytes)

        # GCSにアップロード
        gcs_client = GCSClient()
        file_path = gcs_client.upload_file(
            source_file=pdf_file,
            client_id=client_id,
            feature_name=cls.GCS_FEATURE_NAME,
            filename=f"credit_check_{credit_check_id}.pdf",
        )

        return file_path

    @classmethod
    def _save_to_db(
        cls,
        client_id: int,
        detail: CreditCheckResponse,
        pdf_file_path: str | None,
    ) -> HanshaAlarmboxCreditCheck:
        """
        信用チェック結果をDBに保存

        Returns:
            保存した HanshaAlarmboxCreditCheck インスタンス
        """
        # UUIDv7を生成
        uuid = str(uuid_utils.uuid7())

        # メインテーブルに保存
        credit_check = HanshaAlarmboxCreditCheck.objects.create(
            id=uuid,
            client_id=client_id,
            credit_check_id=detail["credit_check_id"],
            corporation_number=detail["corporation_number"],
            company_name=detail["corporation_name"],
            result=detail.get("result"),
            purchased_at=datetime.strptime(detail["purchase_date"], "%Y-%m-%d"),
            expired_at=datetime.strptime(detail["expiration_date"], "%Y-%m-%d"),
            pdf_file_path=pdf_file_path,
        )

        # リスク情報テーブルに保存
        infos_to_create = []
        for info in detail.get("infos", []):
            received_date = datetime.strptime(info["received_date"], "%Y-%m-%d").date()
            for tag in info.get("tags", []):
                infos_to_create.append(
                    HanshaAlarmboxCreditCheckInfo(
                        alarmbox_credit_check=credit_check,
                        received_on=received_date,
                        tag=tag["name"],
                        description=tag["description"],
                        source=tag.get("source"),
                    )
                )

        if infos_to_create:
            HanshaAlarmboxCreditCheckInfo.objects.bulk_create(infos_to_create)

        return credit_check
```

### uuid_utils について

UUIDv7 を生成するために `uuid_utils` パッケージを使用。

```bash
pip install uuid-utils
```

---

## Step 7: Serializer 作成

```python
# customer/serializers/alarmbox.py

from rest_framework import serializers

from core.contrib.rest_framework.validators import CorporateNumberValidator
from core.models.riskeyes_v2.alarmbox import (
    HanshaAlarmboxCreditCheck,
    HanshaAlarmboxCreditCheckInfo,
)


class CreditCheckPurchaseSerializer(serializers.Serializer):
    """信用チェック購入リクエスト"""

    corporation_number = serializers.CharField(
        validators=[CorporateNumberValidator()],
        help_text="13桁の法人番号",
    )
    deal = serializers.IntegerField(
        required=False,
        help_text="取引関係 (1=有, 2=無, 9=その他)",
    )
    purchase_reasons = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="購入理由IDの配列",
    )
    purchase_reason_comment = serializers.CharField(
        required=False,
        max_length=500,
        help_text="理由の補足コメント",
    )

    # validate_corporation_number は不要
    # CorporateNumberValidator が以下を検証:
    # - 型チェック（文字列 or 整数）
    # - 数字のみ
    # - 13桁
    # - チェックディジット


class CreditCheckInfoSerializer(serializers.ModelSerializer):
    """リスク情報レスポンス"""

    class Meta:
        model = HanshaAlarmboxCreditCheckInfo
        fields = ["received_on", "tag", "description", "source"]


class CreditCheckResponseSerializer(serializers.ModelSerializer):
    """信用チェックレスポンス"""

    infos = CreditCheckInfoSerializer(many=True, read_only=True)

    class Meta:
        model = HanshaAlarmboxCreditCheck
        fields = [
            # === 識別情報 ===
            "id",                   # RiskEyes内部ID（UUIDv7）
            "credit_check_id",      # AlarmBox側のID

            # === 企業情報 ===
            "corporation_number",   # 法人番号（13桁）
            "company_name",         # 企業名

            # === 判定結果 ===
            "result",               # ok/hold/ng

            # === 日付 ===
            "purchased_at",         # 購入日
            "expired_at",           # 有効期限
            "created_at",           # DB登録日時

            # === 関連データ ===
            "pdf_file_path",        # PDF保存先（GCS）
            "infos",                # リスク情報一覧（ネスト）

            # === 除外 ===
            # "client_id"           → セキュリティ上、クライアントには返さない
            # "updated_at"          → フロントで不要
        ]


class CreditCheckListSerializer(serializers.ModelSerializer):
    """信用チェック一覧レスポンス（infosなし）"""

    class Meta:
        model = HanshaAlarmboxCreditCheck
        fields = [
            # === 識別情報 ===
            "id",                   # RiskEyes内部ID（UUIDv7）
            "credit_check_id",      # AlarmBox側のID

            # === 企業情報 ===
            "corporation_number",   # 法人番号（13桁）
            "company_name",         # 企業名

            # === 判定結果 ===
            "result",               # ok/hold/ng

            # === 日付 ===
            "purchased_at",         # 購入日
            "expired_at",           # 有効期限
            "created_at",           # DB登録日時

            # === 除外（一覧では不要） ===
            # "pdf_file_path"       → 詳細画面でのみ必要
            # "infos"               → 詳細画面でのみ必要（N+1回避）
            # "client_id"           → セキュリティ上、クライアントには返さない
            # "updated_at"          → フロントで不要
        ]
```

---

## Step 8: View 作成

```python
# customer/views/alarmbox.py

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.contrib.rest_framework.permissions import (
    IsAuthenticatedWithChild,
    PermissionRequired,
    RolePermissions,
)
from core.models.riskeyes_v2.alarmbox import HanshaAlarmboxCreditCheck
from customer.serializers.alarmbox import (
    CreditCheckListSerializer,
    CreditCheckPurchaseSerializer,
    CreditCheckResponseSerializer,
)
from lib.alarmbox.credit_check_service import CreditCheckService
from lib.alarmbox.exceptions import AlarmboxAPIError

logger = logging.getLogger(__name__)


class CreditCheckPurchaseView(APIView):
    """
    信用チェック購入 API

    POST /client-customer/alarmbox/credit-check/purchase
    """

    permission_classes = [IsAuthenticatedWithChild, PermissionRequired]
    required_permissions = RolePermissions.CUSTOMER

    def post(self, request):
        serializer = CreditCheckPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            credit_check = CreditCheckService.purchase_and_save(
                client_id=request.user.id,
                **serializer.validated_data,
            )
        except AlarmboxAPIError as e:
            # AlarmBox API のエラー → 502（外部サービスの問題）
            logger.error(f"AlarmBox APIエラー: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            # GCS/DB などのエラー → 500（内部サーバーエラー）
            logger.error(f"内部エラー: {e}")
            return Response(
                {"error": "サーバー内部でエラーが発生しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_serializer = CreditCheckResponseSerializer(credit_check)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class CreditCheckListView(APIView):
    """
    信用チェック一覧 API

    GET /client-customer/alarmbox/credit-check/list
    """

    permission_classes = [IsAuthenticatedWithChild, PermissionRequired]
    required_permissions = RolePermissions.CUSTOMER

    def get(self, request):
        credit_checks = HanshaAlarmboxCreditCheck.objects.filter(
            client_id=request.user.id,
        ).order_by("-created_at")

        serializer = CreditCheckListSerializer(credit_checks, many=True)
        return Response(serializer.data)


class CreditCheckDetailView(APIView):
    """
    信用チェック詳細 API

    GET /client-customer/alarmbox/credit-check/<id>
    """

    permission_classes = [IsAuthenticatedWithChild, PermissionRequired]
    required_permissions = RolePermissions.CUSTOMER

    def get(self, request, pk):
        try:
            credit_check = HanshaAlarmboxCreditCheck.objects.prefetch_related(
                "infos"
            ).get(
                id=pk,
                client_id=request.user.id,
            )
        except HanshaAlarmboxCreditCheck.DoesNotExist:
            return Response(
                {"error": "信用チェックが見つかりません"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CreditCheckResponseSerializer(credit_check)
        return Response(serializer.data)
```

---

## Step 9: URL 追加

```python
# customer/urls.py

# import に追加
from .views.alarmbox import (
    CreditCheckDetailView,
    CreditCheckListView,
    CreditCheckPurchaseView,
)

# urlpatterns に追加
urlpatterns = [
    # ... 既存のパス ...

    # AlarmBox 信用チェック
    path(
        "/alarmbox/credit-check/purchase",
        CreditCheckPurchaseView.as_view(),
        name="alarmbox-credit-check-purchase",
    ),
    path(
        "/alarmbox/credit-check/list",
        CreditCheckListView.as_view(),
        name="alarmbox-credit-check-list",
    ),
    path(
        "/alarmbox/credit-check/<str:pk>",
        CreditCheckDetailView.as_view(),
        name="alarmbox-credit-check-detail",
    ),
]
```

---

## Step 10: 動作確認

### 1. マイグレーション確認

```bash
python manage.py migrate
```

### 2. Django shell で購入テスト

```bash
python manage.py shell
```

```python
from lib.alarmbox.credit_check_service import CreditCheckService

# テスト用ダミー法人番号で購入
# 0000000000001 → ok（低リスク）
# 0000000000002 → hold（中リスク）
# 0000000000003 → ng（高リスク）

credit_check = CreditCheckService.purchase_and_save(
    client_id=1,  # テスト用クライアントID
    corporation_number="0000000000001",
)

print(f"ID: {credit_check.id}")
print(f"会社名: {credit_check.company_name}")
print(f"結果: {credit_check.result}")
print(f"PDF: {credit_check.pdf_file_path}")
```

### 3. API テスト（curl）

```bash
# 購入
curl -X POST http://localhost:8300/api/v2/client-customer/alarmbox/credit-check/purchase \
  -H "Authorization: Bearer {your_token}" \
  -H "Content-Type: application/json" \
  -d '{"corporation_number": "0000000000001"}'

# 一覧取得
curl http://localhost:8300/api/v2/client-customer/alarmbox/credit-check/list \
  -H "Authorization: Bearer {your_token}"

# 詳細取得
curl http://localhost:8300/api/v2/client-customer/alarmbox/credit-check/{id} \
  -H "Authorization: Bearer {your_token}"
```

---

## レビュー依頼時のチェックリスト

- [ ] Model が作成されている
- [ ] Migration が成功している
- [ ] 信用チェック購入ができる（shell）
- [ ] PDF が GCS に保存される
- [ ] DB に購入情報が保存される
- [ ] リスク情報（infos）が保存される
- [ ] API エンドポイントが動作する
- [ ] 権限チェックが正しく動作する

---

## トラブルシューティング

### トークンエラー

```
AlarmboxTokenNotFoundError: トークンが未設定です...
```

対処:

- `save_alarmbox_token` コマンドでトークンを設定する

### 法人番号エラー

```
AlarmboxAPIError: 信用チェック購入エラー: 400
```

対処:

- 法人番号が 13 桁の数字であることを確認
- テスト環境ではダミー法人番号（0000000000001 等）を使用

### GCS 保存エラー

```
Exception: GCSクライアントの初期化に失敗
```

対処:

- ローカル環境では `STORAGE_EMULATOR_HOST` を設定
- 本番環境では GCP の認証情報を確認

---

## API 仕様

### POST /client-customer/alarmbox/credit-check/purchase

**リクエスト:**

```json
{
  "corporation_number": "1234567890123",
  "deal": 1,
  "purchase_reasons": [4],
  "purchase_reason_comment": "新規取引開始前の調査"
}
```

**レスポンス（201）:**

```json
{
  "id": "01234567-89ab-7def-0123-456789abcdef",
  "credit_check_id": 12345,
  "corporation_number": "1234567890123",
  "company_name": "株式会社テスト",
  "result": "ok",
  "purchased_at": "2025-12-24T00:00:00Z",
  "expired_at": "2026-12-24T00:00:00Z",
  "pdf_file_path": "riskeyes-files/permanent/1/alarmbox_credit_check/credit_check_12345.pdf",
  "infos": [
    {
      "received_on": "2025-12-01",
      "tag": "登記変更",
      "description": "本店移転",
      "source": "登記情報"
    }
  ],
  "created_at": "2025-12-24T10:00:00Z"
}
```

### GET /client-customer/alarmbox/credit-check/list

**レスポンス（200）:**

```json
[
  {
    "id": "01234567-89ab-7def-0123-456789abcdef",
    "credit_check_id": 12345,
    "corporation_number": "1234567890123",
    "company_name": "株式会社テスト",
    "result": "ok",
    "purchased_at": "2025-12-24T00:00:00Z",
    "expired_at": "2026-12-24T00:00:00Z",
    "created_at": "2025-12-24T10:00:00Z"
  }
]
```

### GET /client-customer/alarmbox/credit-check/{id}

**レスポンス（200）:**

```json
{
  "id": "01234567-89ab-7def-0123-456789abcdef",
  "credit_check_id": 12345,
  "corporation_number": "1234567890123",
  "company_name": "株式会社テスト",
  "result": "ok",
  "purchased_at": "2025-12-24T00:00:00Z",
  "expired_at": "2026-12-24T00:00:00Z",
  "pdf_file_path": "riskeyes-files/permanent/1/alarmbox_credit_check/credit_check_12345.pdf",
  "infos": [
    {
      "received_on": "2025-12-01",
      "tag": "登記変更",
      "description": "本店移転",
      "source": "登記情報"
    }
  ],
  "created_at": "2025-12-24T10:00:00Z"
}
```
