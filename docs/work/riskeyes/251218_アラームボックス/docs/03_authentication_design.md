# AlarmBox API 認証設計

## 確定事項

### アカウント方針

- RiskEyes 側で 1 つの AlarmBox アカウントを持つ
- 全 RiskEyes ユーザーの信用チェックをそのアカウントで実行
- トークンは RiskEyes 側で一元管理

```
RiskEyesユーザーA ─┐
RiskEyesユーザーB ─┼→ RISK EYES API ─→ (共通のトークン) ─→ AlarmBox API
RiskEyesユーザーC ─┘
```

### トークンの特性

| トークン | 有効期限 | 備考 |
|----------|----------|------|
| access_token | 24時間（※） | `expires_in: 86400` |
| refresh_token | 無期限 | 使用するたびに新しいものに更新される |

※ ドキュメントに「例」としか記載がないため、実際の値は要確認

### 認証フロー

```
【初回のみ】
管理者がブラウザで認証 → access_token + refresh_token を取得・保存

【通常運用】
access_token で API 呼び出し
    ↓
24時間経過で期限切れ
    ↓
refresh_token で新しい access_token を自動取得
    ↓
新しい access_token + 新しい refresh_token を保存
    ↓
(これを繰り返すことで永続的に運用可能)
```

### トークン保存場所

**DB に保存する**

理由：
- refresh_token は 24 時間ごとに更新される
- 更新処理がシンプル（SQL で UPDATE するだけ）
- トランザクションで整合性を保証できる
- サーバーで一元管理でき、ユーザーに露出しない

### 比較検討

| 方法 | 概要 | セキュリティ | 運用コスト |
|------|------|--------------|------------|
| 環境変数 | `.env` やサーバー環境変数に直書き | △ 低い | ◎ 簡単 |
| DB | 専用テーブルに保存 | ○ 中程度 | ○ 普通 |
| Secrets Manager | GCP/AWS のシークレット管理サービス | ◎ 高い | △ 設定必要 |
| Vault | HashiCorp Vault など専用ツール | ◎ 高い | × 導入コスト大 |
| Cookie / LocalStorage | ブラウザに保存 | × 低い | ○ 普通 |

### 不採用理由

| 方法 | 不採用理由 |
|------|------------|
| 環境変数 | 動的な更新ができない |
| Secrets Manager | 更新がバージョン追加方式で煩雑 / トランザクションがない |
| Vault | 導入・運用コストが高い（今回の規模には過剰） |
| Cookie / LocalStorage | ユーザー間で共有できない / トークンがユーザーに露出する |

---

## テーブル定義

### hansha_alarmbox_tokens

```sql
CREATE TABLE hansha_alarmbox_tokens (
    id INT PRIMARY KEY DEFAULT 1,
    access_token VARCHAR(512) NOT NULL,   -- 暗号化された値を保存
    refresh_token VARCHAR(512) NOT NULL,  -- 暗号化された値を保存
    expired_at DATETIME DEFAULT NULL,     -- access_token の有効期限
    updated_at DATETIME NOT NULL,         -- レコード更新日時

    CONSTRAINT single_row CHECK (id = 1)
);
```

**設計ポイント：**

- `id = 1` の制約で常に 1 レコードのみ存在することを保証
- トークンは `lib/crypt.py` で暗号化して保存（AES + HMAC）
- 暗号化後のサイズを考慮して `VARCHAR(512)` を使用

---

## 暗号化

### 採用方式

既存の `lib/crypt.py` を使用（AES + HMAC）

### 実装

```python
# Model に暗号化/復号メソッドを追加
class AlarmboxToken(models.Model):
    def get_decrypted_access_token(self) -> str:
        return self.decrypt(self.access_token)

    def set_encrypted_access_token(self, value: str) -> None:
        self.access_token = self.encrypt(value)
```

### キー管理

- 設定場所: `core/config/_base_settings.py` の `CRYPT`
- 全環境で同一キーを使用
- キーローテーション非対応

---

## 参考：OAuth 2.0 用語整理

| 名前 | 説明 | 有効期限 |
|------|------|----------|
| client_id | アプリ識別子（公開可） | 無期限 |
| client_secret | アプリの秘密鍵（非公開） | 無期限 |
| 認可コード | ブラウザ認証後に取得する一時コード | 1回限り |
| access_token | API 呼び出しに使うトークン | 24時間 |
| refresh_token | access_token を再取得するためのトークン | 無期限（更新あり） |

### Refresh Token Rotation

refresh_token は使用するたびに新しいものに置き換わる（古いものは無効化）。

これはセキュリティ対策：
- 固定だと漏洩時に永久に悪用される
- 更新方式なら、正規ユーザーが先に使えば無効化される
