# UUID 設計ガイド

Django + MySQL 環境での UUID 運用について整理したドキュメント。

---

## 目次

1. [UUID の基礎知識](#uuid-の基礎知識)
2. [UUID バージョン比較](#uuid-バージョン比較)
3. [Django UUIDField の挙動](#django-uuidfield-の挙動)
4. [プロジェクト内の現状](#プロジェクト内の現状)
5. [設計方針と結論](#設計方針と結論)

---

## UUID の基礎知識

### UUID とは

UUID（Universally Unique Identifier）は、128ビットの一意な識別子。

### 標準形式（RFC 4122）

```
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   8    - 4  - 4  - 4  -    12
```

| 形式 | 例 | 文字数 |
|---|---|---|
| ハイフン付き（標準） | `019b5928-3b8f-7a91-ad10-0927985dda1a` | **36文字** |
| ハイフンなし | `019b59283b8f7a91ad100927985dda1a` | **32文字** |

**RFC 4122 ではハイフン付きが標準形式**として定義されている。

### 参考リンク

- [Wikipedia: UUID](https://en.wikipedia.org/wiki/Universally_unique_identifier)
- [RFC 4122](https://www.rfc-editor.org/rfc/rfc4122)

---

## UUID バージョン比較

### 主要バージョン

| バージョン | 生成方法 | 特徴 | ソート可能 |
|---|---|---|---|
| **v1** | タイムスタンプ + MACアドレス | 時系列順だがMACアドレス漏洩リスク | △ |
| **v3** | 名前空間 + MD5ハッシュ | 同じ入力 → 同じUUID（決定的） | × |
| **v4** | 完全ランダム | 最も一般的、衝突確率は極めて低い | × |
| **v5** | 名前空間 + SHA-1ハッシュ | v3のSHA-1版 | × |
| **v6** | v1の改良版（タイムスタンプ先頭） | v1互換 + ソート可能 | ○ |
| **v7** | Unix タイムスタンプ + ランダム | **推奨**: 時系列ソート可能 + プライバシー安全 | ○ |

### UUIDv7 の構造

```
019b5928-3b8f-7a91-ad10-0927985dda1a
├─────────────┤├──┤├──────────────────┤
  タイムスタンプ  Ver    ランダム
    (48bit)     (4bit)   (76bit)
```

- **タイムスタンプ**: Unix エポックからのミリ秒（先頭48ビット）
- **バージョン**: `7`（4ビット）
- **ランダム**: 暗号学的に安全なランダム値（76ビット）

### UUIDv7 のメリット

1. **時系列ソート可能**: タイムスタンプが先頭にあるため、生成順 = ソート順
2. **インデックス効率**: B-tree インデックスで連続した値が近くに配置される
3. **プライバシー安全**: MACアドレスを含まない（v1の問題を解消）
4. **衝突耐性**: 同一ミリ秒でも76ビットのランダム値で衝突を回避

### Python での UUIDv7

```python
# Python 標準ライブラリ（3.14 未満）: v7 未対応
import uuid
uuid.uuid4()  # v4 のみ

# uuid_utils パッケージを使用
import uuid_utils
uuid_utils.uuid7()  # UUIDv7 生成
```

**注意**: Python 標準の `uuid` モジュールは v1, v3, v4, v5 のみ対応。**UUIDv7 は Python 3.14 から対応予定**。

---

## Django UUIDField の挙動

### MySQL での保存形式

**Django の `UUIDField` は MySQL で CHAR(32) ハイフンなしで保存する**

```python
# Model 定義
id = models.UUIDField(primary_key=True, default=uuid7)

# 内部処理（概念）
uuid_value = uuid.UUID("019b5928-3b8f-7a91-ad10-0927985dda1a")
uuid_value.hex  # → "019b59283b8f7a91ad100927985dda1a"（DB保存値）
```

### DB ごとの挙動

| DB | 内部保存 | 出力形式 |
|---|---|---|
| **PostgreSQL** | 128ビット（ネイティブ UUID 型） | ハイフン付き（標準形式） |
| **MySQL** | CHAR(32) 文字列 | ハイフンなし |

### 参考リンク

- [Django UUIDField](https://docs.djangoproject.com/en/4.1/ref/models/fields/#uuidfield)
- [Django Ticket #26139](https://code.djangoproject.com/ticket/26139)
- [PostgreSQL UUID型](https://www.postgresql.org/docs/current/datatype-uuid.html)

---

## プロジェクト内の現状

### lib/uuid.py の実装

```python
from uuid import UUID
from uuid_utils import uuid7 as uuid_utils_uuid7

def uuid7(timestamp: int | None = None, nanos: int | None = None) -> UUID:
    """Generate a UUIDv7."""
    return UUID(uuid_utils_uuid7(timestamp=timestamp, nanos=nanos).hex)
```

**ポイント**:
- `uuid_utils.uuid7()` → `uuid_utils.UUID` 型を返す
- Django の `UUIDField` は `uuid.UUID` 型を期待
- `.hex` → `UUID()` で標準ライブラリの型に変換

### DDL と Model の整合性

| テーブル | DDL | Model | 整合性 |
|---|---|---|---|
| `hansha_client_child_roles` | CHAR(32) | UUIDField | ✅ 一致 |
| `hansha_alarmbox_credit_checks` | CHAR(32) | UUIDField | ✅ 一致 |
| `hansha_v2_risk_alert` | CHAR(36) | UUIDField | ❌ 不一致（既存、変更予定なし） |

Django の `UUIDField` は MySQL で CHAR(32) ハイフンなしで保存するため、DDL も CHAR(32) に統一するのが望ましい。

```sql
-- DDL: CHAR(32) = 32文字（ハイフンなし）
id CHAR(32) PRIMARY KEY

-- 実際の保存値: 32文字（ハイフンなし）
"019b59283b8f7a91ad100927985dda1a"
```

### 既存パターン

```python
# プロジェクト標準パターン
from lib.uuid import uuid7

id = models.UUIDField(
    default=uuid7,
    primary_key=True,
    db_comment="UUIDv7",
)
client_id = models.IntegerField(db_comment="利用者ID", db_index=True)
```

使用箇所:
- `HanshaV2RiskAlert`
- `HanshaV2RiskAlertWeb`
- `HanshaV2RiskAlertWebDetail`
- `HanshaV2NotifySettings`
- `HanshaV2NotifyTeams` / `Slack` / `Chatwork` / `Mail`

---

## 設計方針と結論

### 推奨: プロジェクト既存パターンに従う

```python
from lib.uuid import uuid7

class HanshaAlarmboxCreditCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7)
    client_id = models.IntegerField(db_index=True)
    # ...
```

### 理由

1. **一貫性**: プロジェクト内で広く使われているパターン
2. **シンプル**: `lib/uuid.py` が型変換を吸収済み
3. **動作**: CHAR(36) に 32文字を入れても MySQL は動作する
4. **UUIDv7 のメリット**: 時系列ソート可能、インデックス効率が良い

### DDL との乖離について

| 対応案 | メリット | デメリット |
|---|---|---|
| **現状維持** | 変更不要、既存と一貫性 | 設計意図との乖離が残る |
| DDL を CHAR(32) に修正 | 整合性が取れる | マイグレーション必要 |
| CharField + str(uuid7()) | ハイフン付きで保存 | UUIDField のメリット（型認識）を失う |

**結論**: 既存パターンとの一貫性を優先し、`UUIDField` + `lib.uuid.uuid7` を使用する。

---

## 補足: ハイフン付きで保存したい場合

```python
from lib.uuid import uuid7

# CharField + lambda で明示的にハイフン付き文字列化
id = models.CharField(
    max_length=36,
    primary_key=True,
    default=lambda: str(uuid7())
)
```

`str(uuid.UUID(...))` はハイフン付き形式を返す:
```python
str(uuid7())  # → "019b5928-3b8f-7a91-ad10-0927985dda1a"
```

ただし、このプロジェクトでは `UUIDField` パターンが標準のため、特別な理由がない限り推奨しない。
