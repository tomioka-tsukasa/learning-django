# アラームボックスAPI 仕様整理

## 概要

本ドキュメントでは、アラームボックスAPIの「信用チェックの購入」機能を中心に、初心者向けに仕様を整理しています。

---

## 1. 認証方法（OAuth 2.0）

### 概要

アラームボックスAPIは **OAuth 2.0** を採用しています。APIを叩くには「アクセストークン」が必要です。

### 前提条件

- モニタリング・パワーサーチまたはギャランティサービスの契約が必須
- API管理ダッシュボードでアプリケーション登録済み
- クライアントID・クライアントシークレットを取得済み

### 認証フロー（3ステップ）

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. 認可コード取得 │ → │ 2. トークン取得   │ → │ 3. API呼び出し   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ステップ1: 認可コード取得

ブラウザで以下のURLにアクセスし、ログイン・許可を行う

```
GET https://api.alarmbox.jp/oauth/authorize
  ?client_id={アプリケーションID}
  &redirect_uri=urn:ietf:wg:oauth:2.0:oob
  &response_type=code
  &scope=read customer:create survey_report:create
```

| パラメータ | 説明 |
|-----------|------|
| `client_id` | アプリケーションID |
| `redirect_uri` | コールバックURL（ローカル環境では `urn:ietf:wg:oauth:2.0:oob`） |
| `response_type` | `code` 固定 |
| `scope` | 権限スコープ（スペース区切り） |

→ 認可コード（code）が発行される

### ステップ2: アクセストークン取得

```bash
curl -X POST https://api.alarmbox.jp/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id={クライアントID}" \
  -d "client_secret={クライアントシークレット}" \
  -d "code={認可コード}" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

**レスポンス例:**

```json
{
  "access_token": "l-TGspUX-fPghhcKpxWfkyQXbTQnvSejqeTVXlKiKo8",
  "token_type": "Bearer",
  "expires_in": 86400,
  "refresh_token": "JlV8SeYcWwGrsAMh8ylftHQGttitwd2NRibImg3QUes"
}
```

| フィールド | 説明 |
|-----------|------|
| `access_token` | API呼び出しに使うトークン |
| `token_type` | トークンタイプ（Bearer固定） |
| `expires_in` | 有効期限（秒）= 86400秒 = **24時間** |
| `refresh_token` | トークン更新用 |

### ステップ3: API呼び出し

リクエストヘッダーにトークンを設定：

```
Authorization: Bearer {アクセストークン}
```

---

## 2. 信用チェックの購入（POST /ps/v1/credit_checks）

### エンドポイント

```
POST https://api.alarmbox.jp/ps/v1/credit_checks
```

### リクエストヘッダー

```
Authorization: Bearer {アクセストークン}
Content-Type: application/json
```

### リクエストボディ

```json
{
  "corporation_number": "1234567890123",
  "deal": 1,
  "purchase_reasons": [1, 4],
  "purchase_reason_comment": "新規取引開始前の調査"
}
```

| パラメータ | 必須 | 型 | 説明 |
|-----------|------|-----|------|
| `corporation_number` | **必須** | string | 13桁の法人番号 |
| `deal` | 任意 | integer | 取引関係 |
| `purchase_reasons` | 任意 | array | 購入理由IDの配列 |
| `purchase_reason_comment` | 任意 | string | 理由の補足コメント |

**deal（取引関係）の値:**

| 値 | 意味 |
|----|------|
| 1 | 有 |
| 2 | 無 |
| 9 | その他 |

**purchase_reasons（購入理由ID）一覧:**

| ID | 理由 |
|----|------|
| 1 | 取引継続・拡大 |
| 2 | 支払未入金 |
| 3 | 業界不評 |
| 4 | 取引開始検討 |
| 9 | その他 |

### レスポンス（成功時: 200）

```json
{
  "credit_check": {
    "credit_check_id": 12345,
    "purchase_date": "2025-12-18",
    "expiration_date": "2026-12-18",
    "corporation_name": "株式会社テスト",
    "corporation_number": "1234567890123",
    "result": "ok"
  }
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `credit_check_id` | integer | **信用チェックID**（後続の取得APIで使用） |
| `purchase_date` | string | 購入日（yyyy-mm-dd） |
| `expiration_date` | string | 有効期限（yyyy-mm-dd） |
| `corporation_name` | string | 企業名 |
| `corporation_number` | string | 法人番号 |
| `result` | string | 判定結果 |

**result（判定結果）の意味:**

| 値 | 意味 | リスクレベル |
|----|------|-------------|
| `ok` | 低リスク | 安全 |
| `hold` | 中リスク | 要注意 |
| `ng` | 高リスク | 危険 |
| `null` | 判定中/データなし | 未確定 |

---

## 3. 信用チェックの取得（GET /ps/v1/credit_checks/{id}）

### エンドポイント

```
GET https://api.alarmbox.jp/ps/v1/credit_checks/{credit_check_id}
```

### パスパラメータ

| パラメータ | 必須 | 型 | 説明 |
|-----------|------|-----|------|
| `id` | **必須** | integer | 信用チェックID |

### クエリパラメータ

| パラメータ | 必須 | 型 | 説明 |
|-----------|------|-----|------|
| `with_pdf` | 任意 | boolean | PDFデータを含めるか |

### リクエスト例

```bash
# PDFなし
GET https://api.alarmbox.jp/ps/v1/credit_checks/12345

# PDFあり
GET https://api.alarmbox.jp/ps/v1/credit_checks/12345?with_pdf=true
```

### レスポンス（成功時: 200）

```json
{
  "credit_check": {
    "credit_check_id": 12345,
    "purchase_date": "2025-12-18",
    "expiration_date": "2026-12-18",
    "corporation_name": "株式会社テスト",
    "corporation_number": "1234567890123",
    "result": "ok",
    "expired": false,
    "pdf_file_data": "JVBERi0xLjQK...",
    "infos": [
      {
        "received_date": "2025-12-01",
        "tags": [
          {
            "name": "登記変更",
            "description": "本店移転",
            "source": "登記情報"
          }
        ]
      }
    ]
  }
}
```

### レスポンスフィールド詳細

**基本情報:**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `credit_check_id` | integer | 信用チェックID |
| `purchase_date` | string | 購入日（yyyy-mm-dd） |
| `expiration_date` | string | 有効期限（yyyy-mm-dd） |
| `corporation_name` | string | 企業名 |
| `corporation_number` | string | 法人番号 |
| `result` | string | 判定結果（ok/hold/ng） |
| `expired` | boolean | 有効期限切れかどうか |
| `pdf_file_data` | string | PDFのBase64データ（with_pdf=trueの場合のみ） |
| `infos` | array | 企業に関する情報履歴 |

**infos配列の構造:**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `received_date` | string | 情報発生日（yyyy-mm-dd） |
| `tags` | array | タグ情報の配列 |

**tags配列の構造:**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `name` | string | タグ名（例: 登記変更） |
| `description` | string | 詳細説明（例: 本店移転） |
| `source` | string | 情報ソース（例: 登記情報） |

---

## 4. 検証環境でのテスト方法

### テスト用ダミー法人番号

アラームボックスのテストアカウントでは、以下のダミー法人番号を使用することで、異なる判定結果をテストできます。

| 法人番号 | 返却される判定結果 | リスクレベル |
|----------|-------------------|-------------|
| `0000000000001` | `ok` | 低リスク |
| `0000000000002` | `hold` | 中リスク |
| `0000000000003` | `ng` | 高リスク |

### 検証用curlコマンド例

#### 信用チェック購入（低リスクのテストデータ）

```bash
curl -X POST https://api.alarmbox.jp/ps/v1/credit_checks \
  -H "Authorization: Bearer {アクセストークン}" \
  -H "Content-Type: application/json" \
  -d '{
    "corporation_number": "0000000000001"
  }'
```

#### 信用チェック購入（フルパラメータ）

```bash
curl -X POST https://api.alarmbox.jp/ps/v1/credit_checks \
  -H "Authorization: Bearer {アクセストークン}" \
  -H "Content-Type: application/json" \
  -d '{
    "corporation_number": "0000000000001",
    "deal": 1,
    "purchase_reasons": [4],
    "purchase_reason_comment": "新規取引開始前の調査"
  }'
```

#### 信用チェック取得

```bash
curl -X GET "https://api.alarmbox.jp/ps/v1/credit_checks/12345" \
  -H "Authorization: Bearer {アクセストークン}"
```

#### 信用チェック取得（PDF付き）

```bash
curl -X GET "https://api.alarmbox.jp/ps/v1/credit_checks/12345?with_pdf=true" \
  -H "Authorization: Bearer {アクセストークン}"
```

---

## 5. エラーレスポンス

| HTTPステータス | 意味 | 対処法 |
|---------------|------|--------|
| 400 | リクエスト不正（バリデーションエラー） | リクエストパラメータを確認 |
| 401 | 認証エラー（トークン無効/期限切れ） | トークンを再取得 |
| 403 | 権限不足または閲覧期限切れ | 権限・契約状況を確認 |
| 404 | リソースが見つからない | IDを確認 |
| 500 | サーバーエラー | しばらく待ってリトライ |

---

## 6. API連携フロー図

RISK EYESサービスでの連携イメージ：

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  RISK EYES   │     │  AlarmBox    │     │  RISK EYES   │
│    API       │     │    API       │     │     DB       │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ 1. POST /ps/v1/credit_checks            │
       │ ─────────────────→ │                    │
       │                    │                    │
       │ 2. credit_check_id │                    │
       │ ←───────────────── │                    │
       │                    │                    │
       │ 3. GET /ps/v1/credit_checks/{id}        │
       │ ─────────────────→ │                    │
       │                    │                    │
       │ 4. 詳細データ       │                    │
       │ ←───────────────── │                    │
       │                    │                    │
       │ 5. 購入情報を保存                        │
       │ ──────────────────────────────────────→ │
       │                    │                    │
```

---

## 参考リンク

- [アラームボックス API Getting Start](https://developer.alarmbox.jp/)
- [API リファレンス（Swagger）](https://alarmbox.github.io/alarmbox_api_docs/refs/)
