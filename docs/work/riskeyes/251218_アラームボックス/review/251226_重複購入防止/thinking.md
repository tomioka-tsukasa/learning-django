# 重複購入防止：シナリオ整理と設計検討

## 前提

- 購入処理は課金が発生する
- 課金済みなのにエラーを返すのはクレーム案件
- 管理画面はユーザーが触れない
- 失敗時はユーザー自身がリカバリできる必要がある

---

## シナリオ一覧

| # | 購入 (purchase_credit_check) | 詳細取得 (get_credit_check) | PDF保存 | DB保存 | 結果 |
|---|------------------------------|----------------------------|---------|--------|------|
| 1 | 成功 | 成功 | 成功 | 成功 | status=success、正常完了 |
| 2 | 失敗 | - | - | - | status=error、リトライ可能 |
| 3 | 成功 | 失敗 | - | - | status=success、課金済み、詳細なし |
| 4 | 成功 | 成功 | 失敗 | - | status=success、課金済み、PDFなし |
| 5 | 成功 | 成功 | 成功 | 失敗 | status=success、課金済み、全データあるが未保存 |

---

## 各シナリオの詳細

### シナリオ1: 正常完了
- 問題なし

### シナリオ2: 購入失敗
- 課金されていない
- `status=error` でユーザーに返す
- ユーザーは再度購入ボタンを押せる（リトライ可能）

### シナリオ3~5: 購入成功後の失敗
- **共通点**: 課金は発生済み
- **共通点**: `credit_check_id` は取得できている（purchaseの戻り値）
- **共通点**: AlarmBox側にはデータが存在する

---

## ユーザーフロー

### 正常系（シナリオ1）

```
購入ボタン -> POST -> 完全なデータが返る -> 詳細画面表示
```

### 異常系（シナリオ3~5）

```
購入ボタン -> POST -> 不完全なデータが返る（PDFなし等）
-> 詳細画面表示（「PDFがありません」等の表示）
-> ユーザーが「再読み込み」的なアクションをする
-> GET -> 不足情報を再取得 -> 詳細画面更新
```

---

## 実装方針

### 購入成功後は絶対にエラーを返さない

```python
try:
    # 購入（ここで課金発生）
    purchase_result = client.purchase_credit_check(...)
    credit_check_id = purchase_result["credit_check"]["credit_check_id"]
except Exception:
    # 購入失敗 -> error（リトライ可能）
    credit_check.status = "error"
    credit_check.save()
    raise

# ---- ここから先は絶対に例外を投げない ----

# 詳細取得（失敗しても続行）
detail = None
try:
    detail = client.get_credit_check(credit_check_id, with_pdf=True)
except Exception:
    logger.error(f"詳細取得失敗: {traceback.format_exc()}")

# PDF保存（失敗しても続行）
pdf_file_path = None
try:
    if detail and detail.get("pdf_file_data"):
        pdf_file_path = cls._save_pdf_to_gcs(...)
except Exception:
    logger.error(f"PDF保存失敗: {traceback.format_exc()}")

# 取得できた情報だけで success
credit_check.credit_check_id = credit_check_id
credit_check.status = "success"
if detail:
    credit_check.company_name = detail.get("corporation_name")
    credit_check.result = detail.get("result")
    ...
credit_check.pdf_file_path = pdf_file_path
credit_check.save()

return credit_check  # エラーではなく成功として返す
```

### リカバリ方法

新しいエンドポイントは不要。

既存の「詳細取得API」（`GET /api/alarmbox/credit-checks/{id}`）で：
1. POSTのレスポンスで不完全なデータが返る（PDFなし等）
2. フロントで詳細画面を表示（「PDFがありません」等）
3. ユーザーが「再読み込み」的なアクションをする
4. GET -> 不足情報を再取得・保存 -> 詳細画面更新

---

## 各処理時点で保存可能なフィールド

| フィールド | pending作成時 | 購入成功時 | 詳細取得成功時 |
|-----------|-------------|-----------|--------------|
| client_id | o | o | o |
| corporation_number | o | o | o |
| status | pending | success | success |
| credit_check_id | - | o | o |
| company_name | - | - | o |
| result | - | - | o |
| purchased_at | - | - | o |
| expired_at | - | - | o |
| pdf_file_path | - | - | o (PDF保存後) |

購入成功時点で即座に `status=success` + `credit_check_id` を保存する理由:
- 購入成功 = 課金済み
- ここでサーバーが落ちても、`credit_check_id` があればリカバリ可能
- 詳細取得後にまとめて保存だと、途中で落ちたら `status=pending` + `credit_check_id=NULL` でリカバリ不可

---

## TODO

- [ ] 詳細取得API（GET）で不足情報を埋める処理を追加する
