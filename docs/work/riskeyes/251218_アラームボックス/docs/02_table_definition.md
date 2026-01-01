# AlarmBoxデータ格納テーブル定義

## 概要

AlarmBox APIから取得した信用チェック結果を格納するためのテーブル定義です。

---

## テーブル構成

```
┌─────────────────────────┐
│ hansha_alarmbox_credit_checks │  ← メインテーブル（信用チェック結果）
├─────────────────────────┤
│ id (PK, UUIDv7)         │
│ client_id               │  ← 外部キー制約なし（request.user.idから取得）
│ credit_check_id         │  ← AlarmBox側 信用チェックID（pending時はnull）
│ corporation_number      │
│ company_name            │
│ result                  │
│ status                  │  ← pending/success/error
│ purchased_at            │
│ expired_at              │
│ pdf_file_path           │  ← GCSのパス
│ created_at              │
│ updated_at              │
└───────────┬─────────────┘
            │ 1:N
            ▼
┌───────────────────────────────┐
│ hansha_alarmbox_credit_check_infos │  ← リスク情報テーブル
├───────────────────────────────┤
│ id (PK)                       │
│ alarmbox_credit_check_id (FK) │  → hansha_alarmbox_credit_checks.id
│ received_on                   │
│ tag                           │
│ description                   │
│ source                        │
│ created_at                    │
└───────────────────────────────┘
```

---

## テーブル詳細

### 1. hansha_alarmbox_credit_checks（メインテーブル）

AlarmBox APIから取得した信用チェックの基本情報を格納します。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|-----------|------|
| id | CHAR(32) | NO | - | 主キー（UUIDv7） |
| client_id | INT | NO | - | クライアントID |
| credit_check_id | INT | YES | NULL | AlarmBox側 信用チェックID |
| corporation_number | VARCHAR(13) | NO | - | 法人番号（13桁） |
| company_name | VARCHAR(255) | YES | NULL | 企業名 |
| result | VARCHAR(10) | YES | NULL | 判定結果（ok/hold/ng/null） |
| status | VARCHAR(20) | NO | 'pending' | ステータス（pending/success/error） |
| purchased_at | DATETIME | YES | NULL | 購入日 |
| expired_at | DATETIME | YES | NULL | 有効期限 |
| pdf_file_path | VARCHAR(500) | YES | NULL | PDFファイルのGCSパス |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 作成日時 |
| updated_at | DATETIME | NO | CURRENT_TIMESTAMP | 更新日時 |

#### インデックス

| インデックス名 | カラム | 用途 |
|--------------|--------|------|
| idx_client_id | client_id | クライアント別検索 |
| idx_credit_check_id | credit_check_id | AlarmBox ID検索 |
| idx_corporation_number | corporation_number | 法人番号検索 |
| idx_purchased_at | purchased_at | 購入日検索 |

#### status の値

| 値 | 意味 |
|----|------|
| pending | 処理中 |
| success | 成功 |
| error | エラー |

#### result の値

| 値 | 意味 |
|----|------|
| ok | 低リスク |
| hold | 中リスク（要注意） |
| ng | 高リスク |
| NULL | 判定中/データなし |

---

### 2. hansha_alarmbox_credit_check_infos（リスク情報テーブル）

企業に関するリスク情報の履歴を格納します。1つの信用チェックに対して複数のリスク情報が紐づきます。

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|-----------|------|
| id | INT | NO | AUTO_INCREMENT | 主キー |
| alarmbox_credit_check_id | CHAR(32) | NO | - | FK → hansha_alarmbox_credit_checks.id |
| received_on | DATE | NO | - | 情報発生日 |
| tag | VARCHAR(100) | NO | - | タグ名（例：業績、登記変更） |
| description | TEXT | NO | - | 詳細説明 |
| source | VARCHAR(100) | YES | NULL | 情報ソース（例：財務、登記情報） |
| created_at | DATETIME | NO | CURRENT_TIMESTAMP | 作成日時 |

#### インデックス

| インデックス名 | カラム | 用途 |
|--------------|--------|------|
| idx_credit_check_id | alarmbox_credit_check_id | 親テーブル結合 |

---

## APIレスポンスとテーブルの対応

### APIレスポンス例

```json
{
  "credit_check": {
    "credit_check_id": 12345,
    "purchase_date": "2025-12-18",
    "expiration_date": "2026-12-18",
    "corporation_name": "株式会社サンプル",
    "corporation_number": "1234567890123",
    "result": "hold",
    "pdf_file_data": "JVBERi0xLjQK...",
    "infos": [
      {
        "received_date": "2025-12-01",
        "tags": [
          { "name": "業績", "description": "売上低迷", "source": "財務" },
          { "name": "人事", "description": "大量退職", "source": "ニュース" }
        ]
      },
      {
        "received_date": "2025-11-15",
        "tags": [
          { "name": "登記変更", "description": "本店移転", "source": "登記情報" }
        ]
      }
    ]
  }
}
```

### 格納後のデータ

**hansha_alarmbox_credit_checks**

| id | client_id | credit_check_id | corporation_number | company_name | result | purchase_date | expiration_date | pdf_file_path |
|----|-----------|-----------------|-------------------|--------------|--------|---------------|-----------------|---------------|
| 018c3a5b-8f2a-7000-8000-000000000001 | 100 | 12345 | 1234567890123 | 株式会社サンプル | hold | 2025-12-18 00:00:00 | 2026-12-18 00:00:00 | gs://bucket/credit_checks/12345.pdf |

**hansha_alarmbox_credit_check_infos**

| id | alarmbox_credit_check_id | received_on | tag | description | source |
|----|--------------------------|-------------|-----|-------------|--------|
| 1 | 018c3a5b-8f2a-7000-8000-000000000001 | 2025-12-01 | 業績 | 売上低迷 | 財務 |
| 2 | 018c3a5b-8f2a-7000-8000-000000000001 | 2025-12-01 | 人事 | 大量退職 | ニュース |
| 3 | 018c3a5b-8f2a-7000-8000-000000000001 | 2025-11-15 | 登記変更 | 本店移転 | 登記情報 |

---

## 検索クエリ例

### 特定クライアントの信用チェック一覧

```sql
SELECT * FROM hansha_alarmbox_credit_checks
WHERE client_id = 100
ORDER BY purchased_at DESC;
```

### 特定企業のリスク情報一覧

```sql
SELECT
    cc.company_name,
    cc.result,
    ci.received_on,
    ci.tag,
    ci.description,
    ci.source
FROM hansha_alarmbox_credit_checks cc
JOIN hansha_alarmbox_credit_check_infos ci
    ON cc.id = ci.alarmbox_credit_check_id
WHERE cc.corporation_number = '1234567890123'
ORDER BY ci.received_on DESC;
```

### 「業績」に関するリスクがある企業一覧

```sql
SELECT DISTINCT
    cc.corporation_number,
    cc.company_name,
    cc.result
FROM hansha_alarmbox_credit_checks cc
JOIN hansha_alarmbox_credit_check_infos ci
    ON cc.id = ci.alarmbox_credit_check_id
WHERE ci.tag = '業績';
```

---

## 設計上の考慮事項

### 1. なぜ2テーブル構成にしたか

- **データの重複を防ぐ**: 1テーブルだとメイン情報が繰り返し保存される
- **更新が楽**: 企業名の修正等が1箇所で済む
- **リスク情報がない企業も扱える**: infosが空でもメインテーブルに1行で表現できる

### 2. infosとtagsを分けなかった理由

- **シンプルさ優先**: 3テーブルより2テーブルの方が実装・保守が楽
- **received_dateの重複は許容**: 同じ日付に複数タグがあっても、データ量的に問題ない
- **検索要件を満たせる**: name, source での絞り込みは2テーブルで十分可能

### 3. PDFの扱い

- **GCSに保存**: pdf_file_dataはBase64でサイズが大きいため、DBには保存しない
- **パスのみ格納**: `gs://bucket/credit_checks/{credit_check_id}.pdf` 形式で保存

---

## 参考：購入履歴テーブルとの関係

別担当の「購入履歴テーブル」との関係は以下のイメージです：

```
┌─────────────────────┐
│ 購入履歴テーブル      │  ← クライアントがいつ購入したかの履歴
│ (別担当)            │
└─────────┬───────────┘
          │ 参照
          ▼
┌─────────────────────────┐
│ hansha_alarmbox_credit_checks │  ← 購入結果のデータ格納
└─────────────────────────┘
```

※ 具体的なリレーションは購入履歴テーブルの設計次第
