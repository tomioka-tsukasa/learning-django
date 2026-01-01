# Django REST Framework 認証アプローチ完全ガイド

## 目次

1. [認証方式の概要](#認証方式の概要)
2. [セッション認証](#セッション認証)
3. [Token 認証](#token認証)
4. [JWT 認証](#jwt認証)
5. [比較表](#比較表)
6. [実装例](#実装例)

---

## 認証方式の概要

Web アプリケーションでユーザーを識別する方法は大きく分けて 3 つあります：

1. **セッション認証** - 伝統的な Web アプリ向け
2. **Token 認証** - シンプルな API 向け
3. **JWT 認証** - モダンな API 向け

---

## セッション認証

### 仕組み

```
1. ユーザーがログイン
   ↓
2. サーバーがセッションIDを生成してDBに保存
   ↓
3. ブラウザにクッキーとしてセッションIDを送信
   Set-Cookie: sessionid=abc123xyz
   ↓
4. 以降のリクエストでブラウザが自動的にクッキーを送信
   Cookie: sessionid=abc123xyz
   ↓
5. サーバーがセッションDBを確認してユーザー特定
```

### データフロー

```
┌─────────┐                      ┌─────────┐
│ Browser │                      │ Server  │
└────┬────┘                      └────┬────┘
     │                                │
     │ POST /login                    │
     │ {username, password}           │
     ├───────────────────────────────>│
     │                                │
     │                           ┌────▼────┐
     │                           │Session  │
     │                           │DB       │
     │                           │INSERT   │
     │                           │abc123   │
     │                           └────┬────┘
     │                                │
     │ Set-Cookie: sessionid=abc123   │
     │<───────────────────────────────┤
     │                                │
     │ GET /api/tweets/               │
     │ Cookie: sessionid=abc123       │
     ├───────────────────────────────>│
     │                                │
     │                           ┌────▼────┐
     │                           │Session  │
     │                           │DB       │
     │                           │SELECT   │
     │                           │user_id  │
     │                           └────┬────┘
     │                                │
     │ Response: tweets               │
     │<───────────────────────────────┤
```

### Django 実装

```python
from django.contrib.auth import authenticate, login

def login_view(request):
    """セッション認証ログイン"""
    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(username=username, password=password)
    if user:
        # セッションにログイン状態を保存
        login(request, user)
        return Response({"message": "ログイン成功"})

    return Response({"error": "認証失敗"}, status=400)
```

#### `login()` の内部処理

```python
def login(request, user, backend=None):
    """
    セッションにユーザー情報を保存
    """
    # 1. セッションキー生成
    if not request.session.session_key:
        request.session.create()

    # 2. セッションにユーザーID保存
    request.session['_auth_user_id'] = user.pk
    request.session['_auth_user_backend'] = user.backend

    # 3. DBに保存
    request.session.save()

    # 4. レスポンスヘッダーにSet-Cookieをセット
    # Set-Cookie: sessionid=abc123xyz; HttpOnly; Path=/
```

#### DB テーブル構造

```sql
-- django_session テーブル
session_key                              | session_data           | expire_date
abc123xyz...                             | {_auth_user_id: 1}     | 2025-12-25
```

### 特徴

**メリット:**

- ブラウザが自動でクッキー管理
- Django 標準機能で簡単
- CSRF 保護がある

**デメリット:**

- API 向きではない（クッキー依存）
- モバイルアプリで使いづらい
- サーバー側でセッション管理が必要（スケールしにくい）
- CORS 設定が複雑

**適用場面:**

- Django テンプレートを使った伝統的な Web アプリ
- 管理画面
- SSR（サーバーサイドレンダリング）

---

## Token 認証

### 仕組み

```
1. ユーザーがログイン
   ↓
2. サーバーがトークンを生成してDBに保存
   ↓
3. トークンをJSONレスポンスで返す
   {"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}
   ↓
4. クライアントがトークンをlocalStorageなどに保存
   ↓
5. 以降のリクエストでヘッダーにトークンを付与
   Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
   ↓
6. サーバーがトークンDBを確認してユーザー特定
```

### データフロー

```
┌─────────┐                      ┌─────────┐
│ Client  │                      │ Server  │
└────┬────┘                      └────┬────┘
     │                                │
     │ POST /api/login                │
     │ {username, password}           │
     ├───────────────────────────────>│
     │                                │
     │                           ┌────▼────┐
     │                           │Token    │
     │                           │DB       │
     │                           │INSERT   │
     │                           │9944b... │
     │                           └────┬────┘
     │                                │
     │ {"token": "9944b..."}          │
     │<───────────────────────────────┤
     │                                │
  ┌──▼───┐                            │
  │Local │                            │
  │Store │                            │
  │9944b │                            │
  └──┬───┘                            │
     │                                │
     │ GET /api/tweets/               │
     │ Authorization: Token 9944b...  │
     ├───────────────────────────────>│
     │                                │
     │                           ┌────▼────┐
     │                           │Token    │
     │                           │DB       │
     │                           │SELECT   │
     │                           │user_id  │
     │                           └────┬────┘
     │                                │
     │ Response: tweets               │
     │<───────────────────────────────┤
```

### DRF 実装

#### 設定

```python
# settings.py
INSTALLED_APPS = [
    'rest_framework',
    'rest_framework.authtoken',  # 追加
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ]
}
```

```bash
python manage.py migrate  # authtoken_token テーブル作成
```

#### ログイン View

```python
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate

class LoginView(APIView):
    """Token認証ログイン"""

    def post(self, request):
        username = request.data['username']
        password = request.data['password']

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "認証失敗"}, status=400)

        # トークン取得または作成
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
        })
```

#### DB テーブル構造

```sql
-- authtoken_token テーブル
key (トークン)                              | user_id | created
9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b | 1       | 2025-12-07
```

#### クライアント側の使用例

```javascript
// React例
// 1. ログイン
const response = await fetch("/api/login/", {
  method: "POST",
  body: JSON.stringify({ username: "taro", password: "pass123" }),
});
const data = await response.json();
localStorage.setItem("token", data.token); // トークン保存

// 2. 認証が必要なAPI呼び出し
const token = localStorage.getItem("token");
const tweets = await fetch("/api/tweets/", {
  headers: {
    Authorization: `Token ${token}`, // ヘッダーに付与
  },
});
```

### 特徴

**メリット:**

- シンプルで分かりやすい
- クロスプラットフォーム（Web, モバイル）
- DRF 標準機能
- CSRF 対策不要

**デメリット:**

- トークンに有効期限がない（永続的）
- トークンの取り消しには DB 削除が必要
- トークン自体に情報を持たない（毎回 DB 確認）

**適用場面:**

- シンプルな API
- 学習用プロジェクト
- 社内ツール

---

## JWT 認証

### 仕組み

```
1. ユーザーがログイン
   ↓
2. サーバーがJWT（アクセストークン + リフレッシュトークン）を生成
   ※DBには保存しない（署名で検証）
   ↓
3. JWTをJSONレスポンスで返す
   {
     "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  // 短期
     "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  // 長期
   }
   ↓
4. クライアントが両方保存
   ↓
5. アクセストークンをヘッダーに付与
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ↓
6. サーバーは署名を検証（DB不要）
   ↓
7. アクセストークン期限切れ時、リフレッシュトークンで更新
```

### JWT の構造

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE2MzM1MDAwMDB9.signature
│                                      │                                      │
└────────── Header ──────────┘        └────────── Payload ─────────┘        └─ Signature
```

#### デコード例

```json
// Header
{
  "alg": "HS256",
  "typ": "JWT"
}

// Payload
{
  "user_id": 1,
  "username": "taro",
  "exp": 1735689600,  // 有効期限（Unix timestamp）
  "iat": 1735686000   // 発行時刻
}

// Signature
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  SECRET_KEY
)
```

### データフロー

```
┌─────────┐                      ┌─────────┐
│ Client  │                      │ Server  │
└────┬────┘                      └────┬────┘
     │                                │
     │ POST /api/token/               │
     │ {username, password}           │
     ├───────────────────────────────>│
     │                                │
     │                          JWT生成
     │                          (DB不要)
     │                                │
     │ {"access": "eyJ...",           │
     │  "refresh": "eyJ..."}          │
     │<───────────────────────────────┤
     │                                │
  ┌──▼───┐                            │
  │Local │                            │
  │Store │                            │
  │eyJ.. │                            │
  └──┬───┘                            │
     │                                │
     │ GET /api/tweets/               │
     │ Authorization: Bearer eyJ...   │
     ├───────────────────────────────>│
     │                                │
     │                          署名検証
     │                          (DB不要)
     │                                │
     │ Response: tweets               │
     │<───────────────────────────────┤
     │                                │
     │ (15分後、access期限切れ)      │
     │                                │
     │ POST /api/token/refresh/       │
     │ {"refresh": "eyJ..."}          │
     ├───────────────────────────────>│
     │                                │
     │                          リフレッシュ
     │                          トークン検証
     │                                │
     │ {"access": "eyJ_new..."}       │
     │<───────────────────────────────┤
```

### DRF 実装

#### インストール

```bash
pip install djangorestframework-simplejwt
```

#### 設定

```python
# settings.py
from datetime import timedelta

INSTALLED_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',  # 追加
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ]
}

# JWT設定
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),   # アクセストークン: 15分
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),      # リフレッシュトークン: 7日
    'ROTATE_REFRESH_TOKENS': True,                    # リフレッシュ時に新トークン発行
    'BLACKLIST_AFTER_ROTATION': True,                 # 古いトークンをブラックリスト化
}
```

#### URL 設定

```python
# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
```

#### カスタムログイン View（オプション）

```python
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate

class LoginView(APIView):
    """JWT認証ログイン"""

    def post(self, request):
        username = request.data['username']
        password = request.data['password']

        user = authenticate(username=username, password=password)
        if not user:
            return Response({"error": "認証失敗"}, status=400)

        # JWT生成
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
        })
```

#### クライアント側の使用例

```javascript
// React例
// 1. ログイン
const response = await fetch("/api/token/", {
  method: "POST",
  body: JSON.stringify({ username: "taro", password: "pass123" }),
});
const data = await response.json();
localStorage.setItem("access", data.access);
localStorage.setItem("refresh", data.refresh);

// 2. 認証が必要なAPI呼び出し
const access = localStorage.getItem("access");
const tweets = await fetch("/api/tweets/", {
  headers: {
    Authorization: `Bearer ${access}`,
  },
});

// 3. アクセストークン期限切れ時、リフレッシュ
if (tweets.status === 401) {
  const refresh = localStorage.getItem("refresh");
  const refreshResponse = await fetch("/api/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
  const newTokens = await refreshResponse.json();
  localStorage.setItem("access", newTokens.access);

  // リトライ
  const tweets = await fetch("/api/tweets/", {
    headers: {
      Authorization: `Bearer ${newTokens.access}`,
    },
  });
}
```

### 特徴

**メリット:**

- ステートレス（DB アクセス不要で高速）
- スケールしやすい
- 有効期限あり（セキュリティ高い）
- トークン自体に情報を持てる
- 実務で広く使われている

**デメリット:**

- 実装がやや複雑
- トークンサイズが大きい
- 取り消しが難しい（ブラックリスト必要）

**適用場面:**

- 本格的な API
- マイクロサービス
- モバイルアプリ
- SPA（React, Vue 等）

---

## 比較表

| 項目                   | セッション認証    | Token 認証         | JWT 認証                 |
| ---------------------- | ----------------- | ------------------ | ------------------------ |
| **認証情報の保存場所** | サーバー（DB）    | サーバー（DB）     | クライアント             |
| **認証方法**           | クッキー自動送信  | ヘッダーに手動付与 | ヘッダーに手動付与       |
| **有効期限**           | あり（設定可能）  | なし（永続）       | あり（短期）             |
| **DB 確認**            | 毎回必要          | 毎回必要           | 不要（署名検証のみ）     |
| **スケーラビリティ**   | 低い              | 中程度             | 高い                     |
| **実装の複雑さ**       | 簡単              | 簡単               | やや複雑                 |
| **セキュリティ**       | CSRF 対策必要     | CSRF 不要          | CSRF 不要                |
| **トークンサイズ**     | -                 | 40 文字            | 200 文字以上             |
| **取り消し**           | 簡単（DB 削除）   | 簡単（DB 削除）    | 難しい（ブラックリスト） |
| **クロスドメイン**     | 難しい            | 簡単               | 簡単                     |
| **適用場面**           | 従来型 Web アプリ | シンプル API       | 本格 API                 |
| **使用例**             | Django 管理画面   | 社内ツール API     | React + DRF              |

---

## 実装例

### プロジェクト構成

```
tweet_project/
├── user/
│   ├── views.py
│   │   ├── UserRegisterView
│   │   ├── LoginView (Token)
│   │   └── LoginJWTView (JWT)
│   ├── serializers.py
│   └── urls.py
└── settings.py
```

### 切り替え可能な設定

```python
# settings.py

# Token認証を使う場合
INSTALLED_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ]
}

# JWT認証を使う場合（コメントアウトを入れ替え）
# INSTALLED_APPS = [
#     'rest_framework',
#     'rest_framework_simplejwt',
# ]
#
# REST_FRAMEWORK = {
#     'DEFAULT_AUTHENTICATION_CLASSES': [
#         'rest_framework_simplejwt.authentication.JWTAuthentication',
#     ]
# }
```

### URL 設定

```python
# user/urls.py
from django.urls import path
from .views import UserRegisterView, LoginView, LoginJWTView

urlpatterns = [
    path('register/', UserRegisterView.as_view()),
    path('login/', LoginView.as_view()),        # Token認証
    path('login-jwt/', LoginJWTView.as_view()), # JWT認証
]
```

---

## まとめ

### 選び方のフローチャート

```
プロジェクトのタイプは？
│
├─ Django テンプレート使用
│  └─> セッション認証
│
├─ シンプルなAPI（学習・社内ツール）
│  └─> Token認証
│
└─ 本格的なAPI（SPA・モバイル）
   └─> JWT認証
```

### 推奨事項

- **学習段階**: Token 認証から始める
- **実務**: JWT 認証を採用
- **既存プロジェクト**: セッション認証を継続

このプロジェクトでは**Token 認証と JWT 認証の両方を実装**し、設定で切り替えられるようにします。
