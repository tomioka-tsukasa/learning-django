# AlarmBox API 連携 実装ガイド

---

## 1. 全体像

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

### ディレクトリ構造

```
riskeyes-v2-api/
├── core/
│   ├── models/riskeyes_v2/
│   │   └── alarmbox.py              # Model（トークン、信用チェック結果）
│   └── management/commands/
│       ├── save_alarmbox_token.py   # 初回トークン登録
│       └── refresh_alarmbox_token.py # トークン更新バッチ
│
├── lib/alarmbox/                    # AlarmBox API 連携
│   ├── client.py                    # API クライアント
│   ├── token_service.py             # トークン管理サービス
│   ├── exceptions.py                # 例外定義
│   └── types.py                     # 型定義
│
└── customer/
    ├── serializers/alarmbox.py      # Serializer
    ├── views/alarmbox.py            # View
    └── urls.py                      # URL 追記
```

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
Step 1: テーブル定義（Model 作成 → マイグレーション）
    ↓
Step 2: AlarmBox API クライアント
    ↓
Step 3: トークン管理サービス
    ↓
Step 4: 信用チェック API（View, Serializer）
    ↓
Step 5: URL ルーティング
```

---

## 3. テーブル定義

### 作成するテーブル

| テーブル | 役割 |
| -------- | ---- |
| `hansha_alarmbox_tokens` | トークン管理（1 レコード固定） |
| `hansha_alarmbox_credit_checks` | 信用チェック結果（メイン） |
| `hansha_alarmbox_credit_check_infos` | リスク情報（詳細） |

### hansha_alarmbox_tokens

トークンは暗号化して保存する（`lib/crypt.py` を使用）。

| カラム | 型 | 説明 |
| ------ | -- | ---- |
| id | INT | PK（常に 1） |
| access_token | VARCHAR(512) | 暗号化された値 |
| refresh_token | VARCHAR(512) | 暗号化された値 |
| expired_at | DATETIME | access_token の有効期限 |
| updated_at | DATETIME | 更新日時 |

**1 レコード制約:**

- アプリ層: `get_or_create(pk=1)`
- DB 層: `CHECK (id = 1)`

### hansha_alarmbox_credit_checks / hansha_alarmbox_credit_check_infos

詳細は `docs/02_table_definition.md` を参照。

---

## 4. AlarmBox API クライアント

`lib/alarmbox/client.py`

AlarmBox API への HTTP リクエストを抽象化するクライアント。
認証（トークン取得・更新）と信用チェック（購入・取得）の 2 種類の API を提供する。

認証 API はクラスメソッドとして実装（トークン不要）、信用チェック API はインスタンスメソッドとして実装（トークン必要）。
エラーハンドリング（タイムアウト、接続エラー、API エラー）は共通化されている。

### 提供するメソッド

| メソッド | 用途 |
| -------- | ---- |
| `get_token_by_code()` | 認可コードからトークン取得（初回認証） |
| `refresh_token()` | トークン更新 |
| `purchase_credit_check()` | 信用チェック購入 |
| `get_credit_check()` | 信用チェック詳細取得 |

### 設定

環境ごとに `ALARMBOX_INFO` を設定:

| 環境 | 設定方法 |
| ---- | -------- |
| ローカル | `_base_settings.py` に直書き |
| Dev/本番 | GCP Secret Manager |

---

## 5. トークン管理サービス

`lib/alarmbox/token_service.py`

AlarmBox API のトークンを管理するサービス。
View やバッチから呼び出され、有効なトークンの取得・更新・保存を担当する。

主な責務:
- **トークン取得**: DB から暗号化されたトークンを取得し、復号して返す
- **期限切れチェック**: 有効期限の 5 分前から「期限切れ」と判定（API 呼び出し中の失効を防ぐ）
- **自動更新**: 期限切れ時に AlarmBox API でトークンを更新し、暗号化して DB に保存
- **競合防止**: 複数プロセスが同時に更新しないようロックを取得

### 提供するメソッド

| メソッド | 用途 |
| -------- | ---- |
| `get_valid_access_token()` | 有効なトークンを取得（期限切れなら自動更新） |
| `save_initial_token()` | 初回トークン保存 |
| `_refresh_token()` | トークン更新（ロック付き） |

### トークン運用

```
【メイン】バッチが 12 時間ごとにトークン強制更新
    ↓
DB に常に新鮮なトークンが保存されている
    ↓
ユーザーリクエスト時は DB から取得するだけ（高速）

【フォールバック】バッチ失敗時
    ↓
ユーザーリクエスト時に期限切れを検知
    ↓
その場でトークン更新（少し遅いが動作する）
```

### ロック機構

トークン更新時は競合を防ぐためロックを取得。

```python
with lock_manager.lock(timeout=30):
    # この中は同時に 1 プロセスしか実行されない
    token.refresh_from_db()
    result = AlarmboxClient.refresh_token(...)
    token.save()
```

### 暗号化

トークンは `lib/crypt.py` で暗号化して DB 保存。

```python
# 保存時
token.set_encrypted_access_token(value)

# 取得時
token.get_decrypted_access_token()
```

---

## 6. 信用チェック API

RiskEyes CLI から呼び出される信用チェック購入 API。
ユーザーが取引先詳細画面で「購入」ボタンを押すと、このエンドポイントが呼ばれる。

内部では AlarmBox API を 2 回呼び出す:
1. **購入 API** (`POST /ps/v1/credit_checks`) - 信用チェックを購入し、ID を取得
2. **詳細 API** (`GET /ps/v1/credit_checks/{id}`) - 購入した信用チェックの詳細（判定結果、リスク情報）を取得

取得した結果は DB に保存し、CLI にレスポンスとして返却する。

### エンドポイント

```
POST /api/customer/alarmbox/credit-checks
```

### 処理の流れ

```
1. Serializer でバリデーション
    ↓
2. TokenService でトークン取得
    ↓
3. AlarmboxClient で購入 API 呼び出し
    ↓
4. AlarmboxClient で詳細 API 呼び出し
    ↓
5. DB に保存（メイン + リスク情報）
    ↓
6. レスポンス返却
```

### 関連ファイル

| ファイル | 役割 |
| -------- | ---- |
| `customer/views/alarmbox.py` | リクエスト受付、処理フロー |
| `customer/serializers/alarmbox.py` | バリデーション、レスポンス整形 |

---

## 7. URL ルーティング

`customer/urls.py` に追記:

```python
path('/alarmbox/credit-checks', CreditCheckPurchaseView.as_view(), name='alarmbox-credit-check-purchase'),
```

---

## 補足

### 初回セットアップ

1. ブラウザで認可コードを取得
2. `python manage.py save_alarmbox_token --code={認可コード}`

### バッチ運用

- コマンド: `python manage.py refresh_alarmbox_token`
- スケジュール: `0 */12 * * *`（12 時間ごと）
- CloudRunJobs で自動実行

詳細は `lib/alarmbox/README.md` を参照。
