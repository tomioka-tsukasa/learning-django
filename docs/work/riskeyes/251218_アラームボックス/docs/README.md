# AlarmBox API 連携 - 引き継ぎドキュメント

## 概要

RISK EYES に AlarmBox API を組み込み、信用チェック機能を追加するタスク。

---

## タスク進捗

| タスク                                | 時間 | 状態   |
| ------------------------------------- | ---- | ------ |
| DB 設計                               | 8h   | 完了   |
| API 検証（自分で API を叩く）         | 4h   | 完了   |
| API 実装（token 発行）                | 8h   | 完了   |
| API 実装（信用チェック）              | 16h  | 未着手 |
| CLI 実装（購入 API への POST, 画面作成） | 12h  | 未着手 |

---

## 要件

### 概要

- RiskEyes サービスにアラームボックス API を使った「信用チェック購入」機能を追加
- 対象画面: `/dashboard/client-customer/detail/{customer_id}`（取引先詳細画面）
- ユーザーが登録した取引先に対して、信用チェックを購入・結果確認ができる

### ユーザーフロー

```
1. ユーザーが取引先詳細画面で「購入」ボタンを押す
2. RISK EYES API → AlarmBox API に信用チェック購入リクエスト
3. 購入情報を DB に保存
4. 画面上で購入した信用チェック情報を確認
```

### API フロー

```
[RISK EYES API → AlarmBox API] : POST /ps/v1/credit_checks 信用チェックを購入
    ↓
    id を取得
    ↓
[RISK EYES API → AlarmBox API] : GET /ps/v1/credit_checks/{id} 信用チェックの取得
    ↓
[RISK EYES API → RISK EYES DB] : 購入情報を保存
```

### テーブル構成

1. **購入履歴テーブル**（別担当）
2. **AlarmBox データ格納テーブル**（今回の担当）

### その他の要件

- テーブル名のプレフィックスは `hansha_`
- `client_id` カラムは必要（外部キー制約は不要。`request.user.id` から取得するため）
- PDF は GCS に保存し、テーブルにはパスのみ格納
- メインテーブルの id は UUIDv7（CHAR(36)）を使用

---

## テーブル定義

### 1. hansha_alarmbox_credit_checks（メインテーブル）

| カラム名           | 型           | NULL | 説明                        |
| ------------------ | ------------ | ---- | --------------------------- |
| id                 | CHAR(36)     | NO   | 主キー（UUIDv7）            |
| client_id          | INT          | NO   | クライアント ID             |
| credit_check_id    | INT          | NO   | AlarmBox 側 信用チェック ID |
| corporation_number | VARCHAR(13)  | NO   | 法人番号（13 桁）           |
| company_name       | VARCHAR(255) | NO   | 企業名                      |
| result             | VARCHAR(10)  | YES  | 判定結果（ok/hold/ng）      |
| purchased_at       | DATETIME     | NO   | 購入日                      |
| expired_at         | DATETIME     | NO   | 有効期限                    |
| pdf_file_path      | VARCHAR(500) | YES  | PDF ファイルの GCS パス     |
| created_at         | DATETIME     | NO   | 作成日時                    |
| updated_at         | DATETIME     | NO   | 更新日時                    |

**result の値:**

- `ok`: 低リスク
- `hold`: 中リスク
- `ng`: 高リスク

### 2. hansha_alarmbox_credit_check_infos（リスク情報テーブル）

| カラム名                 | 型           | NULL | 説明                                  |
| ------------------------ | ------------ | ---- | ------------------------------------- |
| id                       | INT          | NO   | 主キー（AUTO_INCREMENT）              |
| alarmbox_credit_check_id | CHAR(36)     | NO   | FK → hansha_alarmbox_credit_checks.id |
| received_on              | DATE         | NO   | 情報発生日                            |
| tag                      | VARCHAR(100) | NO   | タグ名（例：業績、登記変更）          |
| description              | TEXT         | NO   | 詳細説明                              |
| source                   | VARCHAR(100) | YES  | 情報ソース（例：財務、登記情報）      |
| created_at               | DATETIME     | NO   | 作成日時                              |

### ER 図

```
┌───────────────────────────────────┐
│ hansha_alarmbox_credit_checks     │
├───────────────────────────────────┤
│ id (PK, UUIDv7)                   │
│ client_id                         │
│ credit_check_id                   │
│ corporation_number                │
│ company_name                      │
│ result                            │
│ purchased_at                      │
│ expired_at                        │
│ pdf_file_path                     │
│ created_at                        │
│ updated_at                        │
└───────────┬───────────────────────┘
            │ 1:N
            ▼
┌───────────────────────────────────────┐
│ hansha_alarmbox_credit_check_infos    │
├───────────────────────────────────────┤
│ id (PK)                               │
│ alarmbox_credit_check_id (FK)         │
│ received_on                           │
│ tag                                   │
│ description                           │
│ source                                │
│ created_at                            │
└───────────────────────────────────────┘
```

---

## 処理フロー詳細

### 全体像（購入ボタン → 結果表示まで）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. ユーザーが取引先詳細画面で「購入」ボタンを押す                             │
│     画面: /dashboard/client-customer/detail/{customer_id}                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RISK EYES CLI (フロントエンド)                    │
│                                                                             │
│  POST /client-customer/alarmbox/credit-check/purchase                       │
│  Body: { "corporation_number": "1234567890123" }                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RISK EYES API (バックエンド)                      │
│                                                                             │
│  View → Serializer → Service → Client                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       │                            │                            │
       ▼                            ▼                            ▼
┌─────────────┐              ┌─────────────┐              ┌─────────────┐
│  AlarmBox   │              │     GCS     │              │  RISK EYES  │
│    API      │              │  (Storage)  │              │     DB      │
└─────────────┘              └─────────────┘              └─────────────┘
```

### シーケンス図（概要）

```
 ユーザー       CLI          RISK EYES API       AlarmBox API       GCS           DB
    │           │                 │                   │              │             │
    │ 購入ボタン │                 │                   │              │             │
    ├──────────→│                 │                   │              │             │
    │           │ POST /purchase  │                   │              │             │
    │           ├────────────────→│                   │              │             │
    │           │                 │                   │              │             │
    │           │                 │ 1. トークン取得    │              │             │
    │           │                 ├───────────────────────────────────────────────→│
    │           │                 │←───────────────────────────────────────────────┤
    │           │                 │                   │              │             │
    │           │                 │ 2. POST 購入       │              │             │
    │           │                 ├──────────────────→│              │             │
    │           │                 │  credit_check_id  │              │             │
    │           │                 │←──────────────────┤              │             │
    │           │                 │                   │              │             │
    │           │                 │ 3. GET 詳細+PDF    │              │             │
    │           │                 ├──────────────────→│              │             │
    │           │                 │  詳細データ        │              │             │
    │           │                 │←──────────────────┤              │             │
    │           │                 │                   │              │             │
    │           │                 │ 4. PDF保存         │              │             │
    │           │                 ├─────────────────────────────────→│             │
    │           │                 │  ファイルパス      │              │             │
    │           │                 │←─────────────────────────────────┤             │
    │           │                 │                   │              │             │
    │           │                 │ 5. DB保存          │              │             │
    │           │                 ├───────────────────────────────────────────────→│
    │           │                 │←───────────────────────────────────────────────┤
    │           │                 │                   │              │             │
    │           │ 201 Created     │                   │              │             │
    │           │ { 信用チェック結果 }                  │              │             │
    │           │←────────────────┤                   │              │             │
    │ 結果表示   │                 │                   │              │             │
    │←──────────┤                 │                   │              │             │
```

### シーケンス図（バックエンド内部詳細）

```
                                   RISK EYES API (Backend)
                   +--------------------------------------------------------------+
                   |                                                              |
 CLI               |  View          Serializer      Service        Client        |  AlarmBox    GCS          DB
  |                |   |               |              |              |           |     |         |           |
  | POST /purchase |   |               |              |              |           |     |         |           |
  +--------------------->               |              |              |           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   | validate()    |              |              |           |     |         |           |
  |                |   +-------------->|              |              |           |     |         |           |
  |                |   |    OK         |              |              |           |     |         |           |
  |                |   |<--------------+              |              |           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   | purchase_and_save()          |              |           |     |         |           |
  |                |   +---------------------------->|              |           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   |               |              | get_token()  |           |     |         |           |
  |                |   |               |              +-------------------------------------------------------->|
  |                |   |               |              | access_token |           |     |         |           |
  |                |   |               |              |<--------------------------------------------------------+
  |                |   |               |              |              |           |     |         |           |
  |                |   |               |              | purchase()   |           |     |         |           |
  |                |   |               |              +------------->|           |     |         |           |
  |                |   |               |              |              | POST      |     |         |           |
  |                |   |               |              |              +---------------->|         |           |
  |                |   |               |              |              | credit_id |     |         |           |
  |                |   |               |              |              |<----------------+         |           |
  |                |   |               |              | credit_id    |           |     |         |           |
  |                |   |               |              |<-------------+           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   |               |              | get_detail() |           |     |         |           |
  |                |   |               |              +------------->|           |     |         |           |
  |                |   |               |              |              | GET + PDF |     |         |           |
  |                |   |               |              |              +---------------->|         |           |
  |                |   |               |              |              | response  |     |         |           |
  |                |   |               |              |              |<----------------+         |           |
  |                |   |               |              | detail       |           |     |         |           |
  |                |   |               |              |<-------------+           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   |               |              | upload_pdf() |           |     |         |           |
  |                |   |               |              +----------------------------------------->|           |
  |                |   |               |              | file_path    |           |     |         |           |
  |                |   |               |              |<-----------------------------------------+           |
  |                |   |               |              |              |           |     |         |           |
  |                |   |               |              | save()       |           |     |         |           |
  |                |   |               |              +-------------------------------------------------------->|
  |                |   |               |              | OK           |           |     |         |           |
  |                |   |               |              |<--------------------------------------------------------+
  |                |   |               |              |              |           |     |         |           |
  |                |   | credit_check  |              |              |           |     |         |           |
  |                |   |<----------------------------+              |           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  |                |   | serialize()   |              |              |           |     |         |           |
  |                |   +-------------->|              |              |           |     |         |           |
  |                |   | JSON          |              |              |           |     |         |           |
  |                |   |<--------------+              |              |           |     |         |           |
  |                |   |               |              |              |           |     |         |           |
  | 201 Created    |   |               |              |              |           |     |         |           |
  | { result }     |   |               |              |              |           |     |         |           |
  |<---------------------+               |              |              |           |     |         |           |
```

### コンポーネント責務一覧

| コンポーネント | ファイル | 責務 | 通信相手 |
|---------------|----------|------|----------|
| **View** | `customer/views/alarmbox.py` | リクエスト受付、レスポンス返却 | CLI, Serializer, Service |
| **Serializer** | `customer/serializers/alarmbox.py` | バリデーション、JSON整形 | View |
| **Service** | `lib/alarmbox/credit_check_service.py` | ビジネスロジックの統括 | Client, GCS, DB |
| **Client** | `lib/alarmbox/client.py` | AlarmBox API との HTTP 通信 | AlarmBox API |
| **TokenService** | `lib/alarmbox/token_service.py` | トークン取得・更新 | DB |
| **GCSClient** | `lib/gcs_client.py` | PDF の保存 | GCS |
| **Model** | `core/models/riskeyes_v2/alarmbox.py` | DB への保存・取得 | DB |

### 処理ステップ詳細

| Step | 処理内容 | 通信先 | 説明 |
|------|----------|--------|------|
| 1 | トークン取得 | DB | 期限切れなら自動で refresh |
| 2 | 信用チェック購入 | AlarmBox API | POST で `credit_check_id` を取得 |
| 3 | 詳細取得（PDF含む） | AlarmBox API | GET で詳細データ + Base64 PDF を取得 |
| 4 | PDF を GCS に保存 | GCS | Base64 デコード → アップロード |
| 5 | 購入情報を DB に保存 | DB | メインテーブル + リスク情報テーブル |

### レイヤー構成

```
┌─────────────────────────────────────────────────────────────┐
│  View層（customer/views/alarmbox.py）                        │
│  - リクエスト受付                                            │
│  - 権限チェック                                              │
│  - レスポンス返却                                            │
├─────────────────────────────────────────────────────────────┤
│  Serializer層（customer/serializers/alarmbox.py）            │
│  - 入力バリデーション                                        │
│  - レスポンス整形                                            │
├─────────────────────────────────────────────────────────────┤
│  Service層（lib/alarmbox/credit_check_service.py）           │
│  - ビジネスロジック                                          │
│  - 購入 → 取得 → PDF保存 → DB保存 の一連フロー               │
├─────────────────────────────────────────────────────────────┤
│  Client層（lib/alarmbox/client.py）                          │
│  - AlarmBox API との HTTP 通信                               │
├─────────────────────────────────────────────────────────────┤
│  Model層（core/models/riskeyes_v2/alarmbox.py）              │
│  - DB とのやり取り                                           │
└─────────────────────────────────────────────────────────────┘
```

### API 連携フロー図（簡易版）

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

## 認証手順（OAuth 2.0）

### 概要

AlarmBox API は OAuth 2.0 を採用。アクセストークンを取得して API を呼び出す。

### 認証フロー

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ 1. 認可コード取得 │ → │ 2. トークン取得   │ → │ 3. API呼び出し   │
│   (ブラウザ)     │    │   (curl/API)     │    │   (Bearer)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Step 1: 認可コード取得（ブラウザ）

以下の URL をブラウザで開き、ログイン・許可を行う：

```
https://api.alarmbox.jp/oauth/authorize?client_id={クライアントID}&redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob&response_type=code&scope=read+customer%3Adelete+customer%3Acreate+credit_check%3Acreate
```

→ 画面に**認可コード**が表示される

### Step 2: アクセストークン取得

```bash
curl -X POST https://api.alarmbox.jp/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id={クライアントID}" \
  -d "client_secret={クライアントシークレット}" \
  -d "code={Step1で取得した認可コード}" \
  -d "redirect_uri=urn:ietf:wg:oauth:2.0:oob"
```

**レスポンス例:**

```json
{
  "access_token": "xxxxx",
  "token_type": "Bearer",
  "expires_in": 86400,
  "refresh_token": "yyyyy"
}
```

| フィールド    | 説明                                   |
| ------------- | -------------------------------------- |
| access_token  | API 呼び出しに使うトークン             |
| expires_in    | 有効期限（秒）= 86400 秒 = **24 時間** |
| refresh_token | トークン更新用                         |

### Step 3: API 呼び出し

```bash
curl -X POST 'https://api.alarmbox.jp/ps/v1/credit_checks' \
  -H 'Authorization: Bearer {access_token}' \
  -H 'Content-Type: application/json' \
  -d '{"corporation_number": "1234567890123"}'
```

### 注意点

- **認可コード**は 1 回限り有効（使い回し不可）
- **アクセストークン**は 24 時間で期限切れ
- 期限切れ後は**refresh_token**で再取得、または Step 1 からやり直し

---

## 検証用情報

### テスト用ダミー法人番号

| 法人番号        | 返却される判定結果 |
| --------------- | ------------------ |
| `0000000000001` | `ok`（低リスク）   |
| `0000000000002` | `hold`（中リスク） |
| `0000000000003` | `ng`（高リスク）   |

### クライアント ID（検証用）

```
ZYNFzaZcD621H3XKOftN4EfDJX4noMwYQZSdc004xKA
```

※ クライアントシークレットは別途管理

---

## 関連ドキュメント

### 設計ドキュメント（docs/）

| ファイル                           | 内容                                     |
| ---------------------------------- | ---------------------------------------- |
| `01_alarmbox_api_specification.md` | API 仕様整理（認証、エンドポイント詳細） |
| `02_table_definition.md`           | テーブル定義詳細、設計理由               |
| `03_authentication_design.md`      | 認証設計                                 |
| `04_project_structure.md`          | プロジェクト構造                         |
| `07_layered_architecture.md`       | レイヤードアーキテクチャ解説             |

### 実装ガイド（guide/）

| ファイル                | 内容                                     |
| ----------------------- | ---------------------------------------- |
| `01_authentication.md`  | 認証実装ガイド（トークン管理）           |
| `02_credit_check.md`    | 信用チェック実装ガイド（購入・保存・API）|

## 参考リンク

- [AlarmBox API Getting Start](https://developer.alarmbox.jp/)
- [API リファレンス（Swagger）](https://alarmbox.github.io/alarmbox_api_docs/refs/)
- [OpenAPI 仕様（YAML）](https://alarmbox.github.io/alarmbox_api_docs/refs/openapi.yaml)
