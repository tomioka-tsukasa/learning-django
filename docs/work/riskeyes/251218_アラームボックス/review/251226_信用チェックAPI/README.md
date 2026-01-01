# 信用チェックAPI レビューFB（Soceyさん）

## 1. [want] UUIDField を使う

### 現在
```python
id = models.CharField(max_length=36, primary_key=True)  # UUIDv7
```

### 修正後
```python
from lib.uuid import uuid7

id = models.UUIDField(primary_key=True, default=uuid7)
```

### 理由
- Django が UUID として認識してくれる
- バリデーションが自動で効く
- DBによっては最適化される

### 注意: UUIDv7 と Python バージョン

#### 背景
- Python 標準の `uuid` モジュールは **v1, v3, v4, v5** のみ対応
- **UUIDv7 は Python 3.14 から対応予定**（現在は 3.12）
- UUIDv7 を使うには `uuid_utils` パッケージが必要

#### 発生したエラー

```python
# 最初の実装（NG）
id = models.UUIDField(primary_key=True, default=uuid_utils.uuid7)
```

```
内部エラー: ['"019b5926-3b8f-7a91-ad10-0927985dda1a" は有効なUUIDではありません。']
```

#### 原因
```python
import uuid
import uuid_utils

u = uuid_utils.uuid7()
print(type(u))                    # <class 'uuid_utils.UUID'>
print(isinstance(u, uuid.UUID))   # False ← これが問題！
```

| | 実際の値 | Django が期待する値 |
|---|---|---|
| 型 | `uuid_utils.UUID` | `uuid.UUID`（標準ライブラリ） |
| 互換性 | `isinstance(u, uuid.UUID)` → False | True が必要 |

Django の `UUIDField` は標準の `uuid.UUID` 型を期待するが、`uuid_utils.uuid7()` は独自の `uuid_utils.UUID` 型を返すため、バリデーションエラーが発生した。

#### 解決策
プロジェクトに既存の変換処理があった！

```python
# lib/uuid.py
from uuid import UUID
from uuid_utils import uuid7 as uuid_utils_uuid7

def uuid7(timestamp: int | None = None, nanos: int | None = None) -> UUID:
    """Generate a UUIDv7."""
    return UUID(uuid_utils_uuid7(timestamp=timestamp, nanos=nanos).hex)
```

##### コード解説

```python
uuid_utils_uuid7(timestamp=timestamp, nanos=nanos)
```
- `uuid_utils` パッケージの `uuid7()` を呼び出し
- UUIDv7 を生成（戻り値: `uuid_utils.UUID` 型）

```python
.hex
```
- UUID をハイフンなしの16進数文字列に変換
- 例: `"019b59283b8f7a91ad100927985dda1a"`

```python
UUID(...)
```
- Python 標準の `uuid.UUID` コンストラクタ
- 16進数文字列から `uuid.UUID` インスタンスを生成

##### 処理の流れ
```
uuid_utils.uuid7()
    ↓
uuid_utils.UUID("019b5928-3b8f-7a91-ad10-0927985dda1a")
    ↓ .hex
"019b59283b8f7a91ad100927985dda1a"（文字列）
    ↓ UUID(...)
uuid.UUID("019b5928-3b8f-7a91-ad10-0927985dda1a")（標準ライブラリの型）
```

これで `uuid_utils.UUID` → `uuid.UUID` への変換が行われ、Django の `UUIDField` が受け入れられる型になる。

#### 最終的な実装
```python
from lib.uuid import uuid7  # プロジェクト共通のUUIDv7生成関数

id = models.UUIDField(primary_key=True, default=uuid7)
```

---

## 2. [should] client_id に index を張る

### 現在
```python
client_id = models.IntegerField()
```

### 修正後
```python
client_id = models.IntegerField(db_index=True)
```

### 理由
一覧取得で毎回 `WHERE client_id = xxx` するため、index がないと全件スキャン → 遅い

---

## 3. [should] サーバ側エラーをそのまま返さない

### 現在
```python
except AlarmboxAPIError as e:
    logger.error(f"AlarmBox APIエラー: {e}")
    return Response({"error": str(e)}, ...)  # ← エラー内容がそのまま
```

### 修正後
```python
except AlarmboxAPIError as e:
    logger.error(f"AlarmBox APIエラー: {e}")
    return Response(
        {"error": "外部サービスでエラーが発生しました"},  # ← 汎用メッセージ
        status=status.HTTP_502_BAD_GATEWAY,
    )
```

### 理由
- APIキー、内部URL、スタック情報などが漏れる可能性
- 攻撃者にヒントを与える
- `logger.error` は CloudRun ログに出るだけなので開発者のみ閲覧可能 → 安全

---

## 4. [want] traceback を出力する

### 現在
```python
except Exception as e:
    logger.error(f"内部エラー: {e}")  # ← エラーメッセージだけ
```

### 修正後
```python
import traceback

except Exception as e:
    logger.error(f"内部エラー: {e}\n{traceback.format_exc()}")  # ← スタックトレース付き
```

### 理由
- どこでエラーが起きたかわからないとデバッグが難しい
- `try-except` で catch すると自動で Traceback は出ない
- 明示的に `traceback.format_exc()` を使う必要がある

### 出力例
```
内部エラー: connection refused
Traceback (most recent call last):
  File "credit_check_service.py", line 45, in purchase_and_save
    result = client.purchase_credit_check(...)
  File "client.py", line 67, in _request
    raise AlarmboxAPIError(...)
```

---

## 5. [must] DDL の CHAR(36) → CHAR(32) 修正

### 背景

Django の `UUIDField` は MySQL で **ハイフンなし（32文字）** で保存する。
既存 DDL が `CHAR(36)` だと、設計意図と実装が乖離する。

### 対象テーブル

| テーブル | カラム | 修正内容 |
|---|---|---|
| `hansha_alarmbox_credit_checks` | `id` | CHAR(36) → CHAR(32) |
| `hansha_alarmbox_credit_check_infos` | `alarmbox_credit_check_id` | CHAR(36) → CHAR(32) |

### 修正手順（本番想定）

#### Step 1: 既存データのハイフン削除

```sql
-- メインテーブルのハイフン削除
UPDATE hansha_alarmbox_credit_checks
SET id = REPLACE(id, '-', '');

-- リスク情報テーブルのハイフン削除（FK）
UPDATE hansha_alarmbox_credit_check_infos
SET alarmbox_credit_check_id = REPLACE(alarmbox_credit_check_id, '-', '');
```

#### Step 2: 外部キー制約を一時的に削除

```sql
-- 外部キー制約の確認
SELECT CONSTRAINT_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_NAME = 'hansha_alarmbox_credit_check_infos'
  AND REFERENCED_TABLE_NAME = 'hansha_alarmbox_credit_checks';

-- 外部キー制約を削除
ALTER TABLE hansha_alarmbox_credit_check_infos
DROP FOREIGN KEY fk_hansha_alarmbox_credit_check_infos_credit_check;
```

#### Step 3: カラム型を変更

```sql
-- メインテーブルの id を CHAR(32) に変更
ALTER TABLE hansha_alarmbox_credit_checks
MODIFY COLUMN id CHAR(32) NOT NULL COMMENT '主キー（UUIDv7）';

-- リスク情報テーブルの FK カラムを CHAR(32) に変更
ALTER TABLE hansha_alarmbox_credit_check_infos
MODIFY COLUMN alarmbox_credit_check_id CHAR(32) NOT NULL COMMENT '信用チェックID';
```

**注意**: `PRIMARY KEY` は `MODIFY COLUMN` で再指定不要（既に設定済みのため維持される）

#### Step 4: 外部キー制約を再作成

```sql
ALTER TABLE hansha_alarmbox_credit_check_infos
ADD CONSTRAINT fk_hansha_alarmbox_credit_check_infos_credit_check
FOREIGN KEY (alarmbox_credit_check_id)
REFERENCES hansha_alarmbox_credit_checks(id)
ON DELETE CASCADE
ON UPDATE CASCADE;
```

#### Step 5: 確認

```sql
-- カラム型の確認
DESCRIBE hansha_alarmbox_credit_checks;
DESCRIBE hansha_alarmbox_credit_check_infos;

-- データの確認（32文字になっているか）
SELECT id, LENGTH(id) FROM hansha_alarmbox_credit_checks LIMIT 5;
SELECT alarmbox_credit_check_id, LENGTH(alarmbox_credit_check_id)
FROM hansha_alarmbox_credit_check_infos LIMIT 5;
```

### 一括実行版

```sql
-- ============================================
-- CHAR(36) → CHAR(32) マイグレーション
-- ============================================

BEGIN;

-- 1. 既存データのハイフン削除
UPDATE hansha_alarmbox_credit_checks
SET id = REPLACE(id, '-', '');

UPDATE hansha_alarmbox_credit_check_infos
SET alarmbox_credit_check_id = REPLACE(alarmbox_credit_check_id, '-', '');

-- 2. 外部キー制約を削除
ALTER TABLE hansha_alarmbox_credit_check_infos
DROP FOREIGN KEY fk_hansha_alarmbox_credit_check_infos_credit_check;

-- 3. カラム型を変更
ALTER TABLE hansha_alarmbox_credit_checks
MODIFY COLUMN id CHAR(32) NOT NULL COMMENT '主キー（UUIDv7）';

ALTER TABLE hansha_alarmbox_credit_check_infos
MODIFY COLUMN alarmbox_credit_check_id CHAR(32) NOT NULL COMMENT '信用チェックID';

-- 4. 外部キー制約を再作成
ALTER TABLE hansha_alarmbox_credit_check_infos
ADD CONSTRAINT fk_hansha_alarmbox_credit_check_infos_credit_check
FOREIGN KEY (alarmbox_credit_check_id)
REFERENCES hansha_alarmbox_credit_checks(id)
ON DELETE CASCADE
ON UPDATE CASCADE;

COMMIT;
```

### 注意点

- **バックアップを取ってから実行**
- 外部キー制約がある場合、先に削除してからカラム変更
- `REPLACE(id, '-', '')` でハイフンを除去

---

## 修正チェックリスト

- [x] `id` を `UUIDField` に変更（`lib.uuid.uuid7` を使用）
- [x] `client_id` に `db_index=True` 追加
- [ ] DDL の CHAR(36) → CHAR(32) 修正
- [ ] エラーレスポンスを汎用メッセージに変更
- [ ] `traceback.format_exc()` を追加
