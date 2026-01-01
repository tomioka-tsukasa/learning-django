# RiskEyes API プロジェクト構造

## 全体構造

```
riskeyes-v2-api/
├── core/                    # 共通機能・モデル
├── lib/                     # 共通ライブラリ（外部APIクライアント等）
├── customer/                # 取引先機能
├── company_register/        # 法人登記機能
├── authorization/           # 認証機能
├── risk_alert/              # リスクアラート機能
├── bill/                    # 請求機能
└── ...                      # その他機能
```

---

## core/ - 共通機能

全アプリで使う Model や設定を管理。

```
core/
├── models/                  # DB モデル（全機能共通）
│   ├── riskeyes_v1/         # v1 系テーブル
│   ├── riskeyes_v2/         # v2 系テーブル
│   └── hansha_*.py          # 個別モデルファイル
├── migrations/              # マイグレーションファイル
├── management/              # Django 管理コマンド
│   └── commands/            # カスタムコマンド
├── services/                # 共通サービス
├── lib/                     # 共通ユーティリティ
├── constants/               # 定数定義
├── config/                  # 設定
└── contrib/                 # Django 拡張（permissions 等）
```

### ポイント

- **Model は core に集約** - 各機能ディレクトリには Model がない
- `riskeyes_v1/` と `riskeyes_v2/` でバージョン分け
- テーブル名のプレフィックスは `hansha_`

---

## lib/ - 共通ライブラリ

外部 API クライアントや汎用ユーティリティ。

```
lib/
├── company_search/          # 企業検索 API クライアント
│   ├── __init__.py
│   ├── service.py           # メインのサービスクラス
│   ├── exceptions.py        # 例外定義
│   └── types.py             # 型定義
├── gcs_client.py            # GCS クライアント
├── crypt.py                 # 暗号化ユーティリティ
├── excel/                   # Excel 操作
├── csv/                     # CSV 操作
└── ...
```

### ポイント

- **外部 API クライアントはここ** - AlarmBox クライアントもここに配置
- 機能横断で使うユーティリティを配置

---

## customer/ - 取引先機能

今回の AlarmBox 連携を追加する場所。

```
customer/
├── __init__.py
├── urls.py                  # URL ルーティング
├── serializers/             # シリアライザ（機能別にファイル分割）
│   ├── detail.py            # 取引先詳細
│   ├── list.py              # 取引先一覧
│   ├── search.py            # 検索
│   └── ...
├── views/                   # ビュー（機能別にファイル分割）
│   ├── detail.py            # 取引先詳細
│   ├── list.py              # 取引先一覧
│   ├── search.py            # 検索
│   └── ...
├── tests/                   # テスト
├── management/              # Django コマンド
└── lib/                     # customer 固有のユーティリティ
```

### ポイント

- **serializers/ と views/ はファイル分割** - ディレクトリではなくファイルで分ける
- **services/ ディレクトリがない** - ビジネスロジックは View か Model に書く慣習？
- URL は `urls.py` に集約

---

## company_register/ - 法人登記機能（参考）

services/ を持つ例。

```
company_register/
├── serializers/
├── views/
├── services/                # 機能固有のサービス
│   └── pdf_processor.py
└── ...
```

---

## 命名規則

### ファイル名

| 種類 | 命名例 |
|------|--------|
| Serializer | `detail.py`, `list.py`, `search.py` |
| View | `detail.py`, `list.py`, `search.py` |
| Model | `hansha_v2_*.py` |

### クラス名

| 種類 | 命名例 |
|------|--------|
| Serializer | `HanshaClientCustomerSerializer` |
| View | `HanshaClientCustomerCreateView` |
| Model | `HanshaClientCustomer` |

---

## URL 構造

`customer/urls.py` より抜粋：

```python
urlpatterns = [
    path("/list", HanshaClientCustomerListView.as_view()),
    path("/detail/<int:pk>", HanshaClientCustomerRetrieveUpdateDestroyView.as_view()),
    path("/create", HanshaClientCustomerCreateView.as_view()),
    ...
]
```

### ポイント

- パスは `/` から始まる
- `<int:pk>` で ID を受け取る
- View は `.as_view()` で登録

---

## core/config/ - 設定ファイル

環境ごとに設定ファイルが分かれている。

```
core/config/
├── _base_settings.py    # ベース設定（全環境共通 + ローカル用ダミー値）
├── local.py             # ローカル開発環境
├── devserver.py         # Dev サーバー環境
├── staging.py           # Staging 環境
├── production.py        # 本番環境
├── batch.py             # バッチ処理用
└── test.py              # テスト環境
```

### 機密情報の管理パターン

| 環境 | 管理方法 |
|------|----------|
| ローカル | `_base_settings.py` のダミー値 or `.env` |
| Dev/Staging/本番 | GCP Secret Manager |
| バッチ | 環境変数（JSON） |
| テスト | ダミー値 |

### 既存の外部 API 設定例（Dow Jones）

```python
# core/config/_base_settings.py（ローカル用ダミー値）
DOW_JONES_INFO = {
    "dow_jones_client_id": "xxx",
    "dow_jones_username": "xxx",
    "dow_jones_password": "xxx",
    ...
}

# core/config/devserver.py（Dev 環境）
from core.lib.google_cloud import get_json_secret
DOW_JONES_INFO = get_json_secret("riskeyes-v1-dow_jones-info-dev")

# core/config/production.py（本番環境）
DOW_JONES_INFO = get_json_secret("riskeyes-v1-dow_jones-info-prod")
```

### 使用側

```python
from django.conf import settings

client_id = settings.DOW_JONES_INFO["dow_jones_client_id"]
```

### GCP Secret Manager

`core/lib/google_cloud.py` にラッパーメソッドがある：

```python
from google.cloud import secretmanager  # GCP 公式パッケージ

def get_secret(secret_name):
    """文字列型シークレットを取得"""
    ...

def get_json_secret(secret_name):
    """JSON型シークレットを取得"""
    return json.loads(get_secret(secret_name))
```

---

## 今回の AlarmBox 連携の配置

| 種類 | 配置場所 | ファイル名 |
|------|----------|------------|
| Model | `core/models/riskeyes_v2/` | `alarmbox.py` |
| 設定 | `core/config/` | `_base_settings.py` 他 |
| 管理コマンド | `core/management/commands/` | `save_alarmbox_token.py` |
| API クライアント | `lib/alarmbox/` | `client.py`, `token_service.py` |
| 型定義 | `lib/alarmbox/` | `types.py` |
| 例外定義 | `lib/alarmbox/` | `exceptions.py` |
| Serializer | `customer/serializers/` | `alarmbox.py` |
| View | `customer/views/` | `alarmbox.py` |
| URL | `customer/urls.py` | 既存ファイルに追記 |

### AlarmBox 設定の追加例

```python
# core/config/_base_settings.py（ローカル用）
ALARMBOX_INFO = {
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
}

# core/config/devserver.py
ALARMBOX_INFO = get_json_secret("riskeyes-alarmbox-info-dev")

# core/config/production.py
ALARMBOX_INFO = get_json_secret("riskeyes-alarmbox-info-prod")
```

### 理由

- Model は core に集約する慣習
- 設定は core/config/ に環境別で管理
- 管理コマンドは core/management/commands/ に配置
- 外部 API クライアントは `lib/` に置く（company_search と同じ）
- customer の一機能なので serializers/, views/ に追加
