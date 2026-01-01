# レイヤードアーキテクチャ

## 概要

アプリケーションを「責務」ごとに層に分ける設計パターン。

```
┌─────────────────────────────────────┐
│  プレゼンテーション層（View/API）    │  ← リクエスト受付・レスポンス返却
├─────────────────────────────────────┤
│  サービス層（ビジネスロジック）       │  ← 「何をするか」の処理
├─────────────────────────────────────┤
│  データアクセス層（Model/Repository） │  ← DBとのやり取り
├─────────────────────────────────────┤
│  データベース                        │  ← 実際のデータ保存
└─────────────────────────────────────┘
```

---

## 各層の責務イメージ

```
View: 「バリデーション通ったよ、あとよろしく」
  |
  v
Service: 「OK、俺が全部やっとくわ」
  |
  +---> Client:「AlarmBox、購入して」
  +---> Client:「詳細も取ってきて」
  +---> GCS:「PDF 保存しといて」
  +---> Model:「DB に記録して」
  |
  v
View: 「結果返すね」
```

| 層 | 役割 | 一言で言うと |
|---|------|------------|
| View | 受付・返却 | 「窓口」 |
| Serializer | 検査 | 「入力チェック係」 |
| **Service** | **処理の統括** | **「現場監督」** |
| Client | 外部通信 | 「外注担当」 |
| Model | DB操作 | 「倉庫係」 |

Service が「現場監督」として、必要な人（Client, GCS, Model）に指示を出して、一連の仕事を完遂させる。

---

## 各層の役割

### 1. プレゼンテーション層（View / Serializer）

**役割:** 外部との窓口

```python
# customer/views/alarmbox.py
class CreditCheckPurchaseView(APIView):
    def post(self, request):
        # リクエストを受け取る
        serializer = CreditCheckPurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # サービス層を呼ぶ
        result = CreditCheckService.purchase_and_save(...)

        # レスポンスを返す
        return Response(data, status=201)
```

責務:
- HTTP リクエストの受付
- 入力のバリデーション（Serializer）
- レスポンスの整形

### 2. サービス層（Service）

**役割:** ビジネスロジック = 「アプリが何をするか」

```python
# lib/alarmbox/credit_check_service.py
class CreditCheckService:
    def purchase_and_save(self, corporation_number, client_id):
        # 1. AlarmBox API で購入
        # 2. 詳細情報を取得
        # 3. PDF を GCS に保存
        # 4. DB に保存
        return credit_check
```

責務:
- 複数の処理を組み合わせる
- トランザクション管理
- 外部 API との連携

### 3. データアクセス層（Model / Repository）

**役割:** DB とのやり取り

```python
# core/models/riskeyes_v2/alarmbox.py
class HanshaAlarmboxCreditCheck(models.Model):
    client_id = models.IntegerField()
    corporation_number = models.CharField(max_length=13)
    # ...
```

責務:
- CRUD 操作
- データの永続化

---

## なぜ分けるのか？

### 分けない場合（Fat View）

```python
class CustomerView(APIView):
    def post(self, request):
        # バリデーション
        # AlarmBox API 呼び出し
        # GCS 保存
        # DB 保存
        # メール送信
        # ログ記録
        # ... 1000行のコード
```

問題点:
- テストしづらい
- 再利用できない
- 変更が大変

### 分けた場合

```python
class CustomerView(APIView):
    def post(self, request):
        serializer = CreditCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = CreditCheckService().purchase_and_save(serializer.validated_data)
        return Response(result)
```

利点:
- 各層を独立してテスト可能
- サービス層は他の View からも呼べる
- 変更の影響範囲が限定的

---

## 用語の対応関係

「アプリケーション層」「データベース層」という言い方は文脈によって変わる。

### パターン1: シンプルな2層で語る場合

```
┌─────────────────────────┐
│  アプリケーション層      │  ← View + Service + Model 全部
├─────────────────────────┤
│  データベース層          │  ← MySQL/PostgreSQL 等の DBMS 自体
└─────────────────────────┘
```

### パターン2: 3層アーキテクチャで語る場合

```
┌─────────────────────────┐
│  プレゼンテーション層    │  ← UI / API（View）
├─────────────────────────┤
│  アプリケーション層      │  ← ビジネスロジック（Service）
├─────────────────────────┤
│  データ層               │  ← データアクセス（Model + DB）
└─────────────────────────┘
```

### 対応表

| 言い方 | レイヤードアーキテクチャでの対応 |
|--------|-------------------------------|
| アプリケーション層 | 文脈による（サービス層 or コード全体） |
| データベース層 | データアクセス層 + DB 自体 |
| ビジネスロジック層 | サービス層 |
| プレゼン層 / UI 層 | プレゼンテーション層（View） |

**「アプリケーション層」は曖昧な用語なので、厳密に話したいときは「サービス層」「プレゼンテーション層」等の具体的な名前を使うのがベター。**

---

## このプロジェクトでの実態

`04_project_structure.md` に書いてある通り:

> **services/ ディレクトリがない** - ビジネスロジックは View か Model に書く慣習？

このプロジェクトでは:
- 明確なサービス層がないケースもある
- `lib/` に外部 API クライアントを置く
- 複雑な処理は `lib/` 内で完結させることもある

AlarmBox 連携では `lib/alarmbox/credit_check_service.py` にサービス層を配置。

---

## 実装順序のアプローチ

### ボトムアップ（Model → View）

```
Model → Migration → Client → Service → Serializer → View → URL
```

**メリット:** 常に動くコードが書ける（参照先が存在する）
**デメリット:** 何のために作ってるか見失いやすい

### トップダウン（View → Model）

```
View → Serializer → Service → Client → Model → Migration
```

**メリット:** 目的が明確（「これが必要だから作る」）
**デメリット:** 途中でエラーになる（import 先がない等）

### 推奨

**全体のシーケンス図を理解した上でボトムアップ**

シーケンス図で「誰が誰を呼ぶか」が見えていれば、Model を作っている時も「Service がこう使うから」と理解できる。

---

## AlarmBox 連携のレイヤー構成

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
