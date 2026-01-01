# 信用チェック 重複購入防止

## 背景

中村さんからのレビューアドバイス:

> 悲観Lockだけ設置しておいてください。(REはUserLockかな？)

```
悲観ロック（
すでにレコードを作っていないかチェック
レコード作成(status=未確定)
外部API接続（失敗したらstatus=error）
レコードの更新（response_idを更新＋status = success）
）
※transactionを張らない
```

---

## 問題: 二重課金のリスク

同じ法人番号に対して同時にリクエストが来た場合、二重課金が発生する可能性がある。

```
リクエストA: purchase_credit_check("1234567890123") -> 課金
リクエストB: purchase_credit_check("1234567890123") -> 課金
```

---

## なぜトランザクションを張らないのか

### トランザクション中のレコードは他から見えない

```
リクエストA: 開始 -> pending作成（未コミット）-> API呼び出し中...
リクエストB: 開始 -> 「pendingある？」-> 見えない -> API叩く -> 二重課金
```

### 失敗時にロールバックされる

```python
with transaction.atomic():
    record = create(status="pending")  # 作成
    api_call()                          # <- ここで失敗
    record.status = "success"
# ロールバック -> status="pending" も消える
```

-> 失敗した痕跡が残らない -> 次のリクエストで「処理中」を検知できない

---

## 解決策: 悲観ロック + ステータス管理

### 処理フロー

```
1. ロック取得（LockManager）
   |
2. 既存チェック（同じ法人番号で pending/success がある？）
   -> あれば「購入済み」エラー
   |
3. レコード作成（status = "pending"）
   |
4. 外部API呼び出し: 購入（AlarmBox）
   -> 失敗したら status = "error" に更新
   |
5. 外部API呼び出し: 詳細取得（失敗しても続行）
   |
6. PDF保存（失敗しても続行）
   |
7. レコード更新（status = "success"）
   |
8. ロック解放
```

### 重要: 購入成功後は絶対にエラーを返さない

課金が発生するのは `purchase_credit_check` の成功時点。
それ以降の処理（詳細取得、PDF保存）が失敗しても:
- ユーザーにはエラーを返さない
- 取得できた情報だけで `status=success` として返す
- 不足情報は後でリカバリ

### なぜ両方必要か

| 仕組み | 役割 |
|--------|------|
| LockManager | チェック~作成の間を1人ずつにする |
| ステータス管理 | 処理中・成功・失敗を記録して検知可能にする |

ステータス管理だけだと、チェックと作成の間に隙間がある:

```
リクエストA: チェック -> なし
リクエストB: チェック -> なし（Aがまだ作成してない）
リクエストA: pending作成
リクエストB: pending作成
両方API叩く -> 二重課金
```

---

## ユーザーフロー

### 正常系

```
購入ボタン -> POST -> 完全なデータが返る -> 詳細画面表示
```

### 異常系（詳細取得/PDF保存が失敗）

```
購入ボタン -> POST -> 不完全なデータが返る（PDFなし等）
-> 詳細画面表示（「PDFがありません」等の表示）
-> ユーザーが「再読み込み」的なアクションをする
-> GET -> 不足情報を再取得 -> 詳細画面更新
```

---

## 修正内容

### 1. DDL（statusカラム追加）

```sql
ALTER TABLE hansha_alarmbox_credit_checks ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'ステータス';
```

### 2. Model修正

```python
# core/models/riskeyes_v2/alarmbox.py

class HanshaAlarmboxCreditCheck(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "処理中"
        SUCCESS = "success", "成功"
        ERROR = "error", "エラー"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # 変更（NOT NULL -> NULL許可）
    credit_check_id = models.IntegerField(null=True)
    company_name = models.CharField(max_length=255, null=True)
    purchased_at = models.DateTimeField(null=True)
    expired_at = models.DateTimeField(null=True)
```

### 3. Service修正

```python
# lib/alarmbox/credit_check_service.py

from core.lib.lock import LockManager
from lib.alarmbox.exceptions import AlarmboxAPIError

class CreditCheckService:
    LOCK_NAME = "alarmbox_credit_check"

    @classmethod
    def purchase_and_save(cls, client_id, corporation_number, ...):
        # ユーザー単位でロック
        lock_manager = LockManager(
            name=f"{cls.LOCK_NAME}_{client_id}",
            parallelism=1
        )

        with lock_manager.lock(timeout=60):
            # 1. 既存チェック
            existing = HanshaAlarmboxCreditCheck.objects.filter(
                client_id=client_id,
                corporation_number=corporation_number,
                status__in=[Status.PENDING, Status.SUCCESS],
            ).exists()

            if existing:
                raise AlarmboxAPIError("この法人番号は処理中または購入済みです")

            # 2. pending で作成
            credit_check = HanshaAlarmboxCreditCheck.objects.create(
                client_id=client_id,
                corporation_number=corporation_number,
                status=Status.PENDING,
            )

            # 3. 購入
            try:
                purchase_result = client.purchase_credit_check(...)
                credit_check_id = purchase_result["credit_check"]["credit_check_id"]
            except Exception:
                credit_check.status = Status.ERROR
                credit_check.save()
                raise

            # ---- ここから先は購入成功後なので、絶対に例外を投げない ----

            # 4. 詳細取得（失敗しても続行）
            detail = None
            try:
                detail = client.get_credit_check(credit_check_id, with_pdf=True)
            except Exception:
                logger.error(f"詳細取得失敗: {traceback.format_exc()}")

            # 5. PDF保存（失敗しても続行）
            pdf_file_path = None
            if detail and detail.get("pdf_file_data"):
                try:
                    pdf_file_path = cls._save_pdf_to_gcs(...)
                except Exception:
                    logger.error(f"PDF保存失敗: {traceback.format_exc()}")

            # 6. 取得できた情報だけで success
            credit_check.credit_check_id = credit_check_id
            credit_check.status = Status.SUCCESS
            credit_check.pdf_file_path = pdf_file_path
            if detail:
                credit_check.company_name = detail.get("corporation_name")
                credit_check.result = detail.get("result")
                ...
            credit_check.save()

            return credit_check
```

### 4. DDL（0048_customer_alarmbox.sql）

```sql
-- 追加
status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'ステータス',

-- 変更（NOT NULL -> NULL許可）
credit_check_id INT DEFAULT NULL,
company_name VARCHAR(255) DEFAULT NULL,
purchased_at DATETIME DEFAULT NULL,
expired_at DATETIME DEFAULT NULL,
```

---

## 用語整理

| 用語 | 意味 |
|------|------|
| 悲観ロック | 「どうせ衝突する」と最初からロックして待たせる方式 |
| 楽観ロック | 「たぶん衝突しない」と更新時にチェックする方式 |
| トランザクション | 複数処理を1つのまとまりとして扱う。失敗したら全部ロールバック |
| LockManager | RiskEyesのRedis/Cacheベースのロック機構 |
| UserLock | ユーザー単位でロックすること（`name=f"xxx_{client_id}"`）|

---

## TODO

- [ ] 詳細取得API（GET）で不足情報を埋める処理を追加する
