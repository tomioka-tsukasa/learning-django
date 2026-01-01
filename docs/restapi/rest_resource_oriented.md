# REST API のリソース指向設計

## 基本概念

REST では **「何をするか」ではなく「何に対してするか」** で URL を設計する。

- URL = リソース（名詞）
- HTTP メソッド = 操作（動詞）

## 「何に対してするか」の考え方

### リソースとは

リソース = **操作対象となるデータやモノ**

```
ツイート、ユーザー、コメント、商品、注文...
```

URL は「どのリソースに対して操作するか」を表す。

### HTTP メソッドで操作を表現

同じ URL でも、メソッドによって意味が変わる。

```
POST   /tweets/   → ツイート（全体）に「追加する」
GET    /tweets/   → ツイート（全体）を「取得する」
GET    /tweets/1/ → ツイート1件を「取得する」
PUT    /tweets/1/ → ツイート1件を「更新する」
DELETE /tweets/1/ → ツイート1件を「削除する」
```

### Web ページ vs REST API

**Web ページ（HTML）**

ブラウザは GET と POST しか送れない。だから URL で操作を区別する。

```
GET  /tweets/         → 一覧ページ表示
GET  /tweets/create/  → 作成フォーム表示
POST /tweets/create/  → 作成処理
GET  /tweets/1/edit/  → 編集フォーム表示
POST /tweets/1/edit/  → 更新処理
POST /tweets/1/delete/ → 削除処理
```

**REST API（JSON）**

HTTP メソッドを全て使える。だから URL は「対象」だけを表す。

```
GET    /tweets/      → 一覧取得
POST   /tweets/      → 作成
GET    /tweets/1/    → 詳細取得
PUT    /tweets/1/    → 更新
DELETE /tweets/1/    → 削除
```

`/create/` や `/edit/` は不要。**フォームページはフロントエンドの責務**。

### 具体例：ツイート投稿の流れ

```
【フロントエンド】
1. ユーザーが /tweets/create/ ページにアクセス（フロントのルーティング）
2. フォームに入力
3. 送信ボタンをクリック

【API リクエスト】
POST /api/v1/tweets/
Content-Type: application/json
{ "content": "Hello World" }

【API レスポンス】
201 Created
{ "id": 1, "author": "taro", "content": "Hello World", ... }
```

API は「ツイートを作る」だけ。どの画面から呼ばれるかは関知しない。

## URL 設計の比較

### NG: 操作ベース（RPC スタイル）

```
POST /tweets/create/
GET  /tweets/getAll/
GET  /tweets/getById/1/
POST /tweets/update/1/
POST /tweets/delete/1/
```

### OK: リソースベース（REST スタイル）

```
POST   /tweets/      # 新規作成
GET    /tweets/      # 一覧取得
GET    /tweets/1/    # 詳細取得
PUT    /tweets/1/    # 更新
DELETE /tweets/1/    # 削除
```

## コレクション vs 個別リソース

| URL | 種類 | 対応メソッド |
|-----|------|-------------|
| `/tweets/` | コレクション（複数） | GET（一覧）, POST（追加） |
| `/tweets/1/` | 個別リソース（単数） | GET（詳細）, PUT/PATCH（更新）, DELETE（削除） |

## DRF での実装パターン

```python
# コレクション操作
class TweetListCreateView(APIView):
    def get(self, request):    # 一覧
        ...
    def post(self, request):   # 新規作成
        ...

# 個別リソース操作
class TweetDetailView(APIView):
    def get(self, request, pk):      # 詳細
        ...
    def put(self, request, pk):      # 更新
        ...
    def delete(self, request, pk):   # 削除
        ...
```

```python
# urls.py
urlpatterns = [
    path("tweets/", TweetListCreateView.as_view()),
    path("tweets/<int:pk>/", TweetDetailView.as_view()),
]
```

## メリット

1. **予測しやすい**: URL を見ればリソースがわかる
2. **シンプル**: 操作は HTTP メソッドで表現
3. **統一性**: どの API も同じパターンで設計できる
4. **キャッシュ可能**: GET リクエストはキャッシュできる
