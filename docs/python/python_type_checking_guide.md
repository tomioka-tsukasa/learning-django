# Python TYPE_CHECKING と文字列型注釈 - 実務編

## TYPE_CHECKING とは

**型チェック時だけ `True` になる定数**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # mypy/Pylance 実行時だけ実行される
    from expensive_module import HeavyClass
else:
    # python manage.py runserver 時だけ実行される
    HeavyClass = None
```

---

## 文字列型注釈とは

**型を文字列で書くことで、評価を遅延させる**

```python
# 通常
def get_user() -> User:
    ...

# 文字列型注釈
def get_user() -> "User":  # まだ定義されていなくてもOK
    ...
```

---

## 実務でよく使うパターン

### パターン1: 循環参照の回避

```python
# user.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tweet import Tweet  # 型チェック時だけインポート

class User:
    def get_tweets(self) -> list["Tweet"]:  # 文字列型注釈
        from .tweet import Tweet  # 実行時にインポート
        return Tweet.objects.filter(author=self)
```

```python
# tweet.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

class Tweet:
    def get_author(self) -> "User":
        from .user import User
        return User.objects.get(id=self.author_id)
```

**ポイント:** インポートを分けることで循環参照を回避

---

### パターン2: 重いライブラリの遅延インポート

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    import numpy as np

class DataAnalyzer:
    def process(self, data: "pd.DataFrame") -> "np.ndarray":
        # 実行時にインポート
        import pandas as pd
        import numpy as np
        # 処理...
```

**メリット:** 型チェックは効くが、実行時は使うときだけインポート（起動高速化）

---

### パターン3: Django の get_user_model()

```python
from typing import TYPE_CHECKING
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
    UserType = AbstractBaseUser
else:
    UserType = get_user_model()

# 使用例
def send_email(user: UserType) -> None:
    print(user.email)
```

**理由:** `get_user_model()` は関数なので型として使えない

---

### パターン4: API レスポンスの型定義

```python
from typing import TYPE_CHECKING, TypedDict, Protocol

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

class UserData(TypedDict):
    id: int
    username: str
    email: str

# Protocol で「必要なメソッドだけ」定義
class UserLike(Protocol):
    id: int
    username: str
    email: str

def format_user(user: UserLike) -> UserData:
    # AbstractBaseUser でも、カスタムUserでも、
    # id, username, email があればOK
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email
    }
```

**メリット:** 具体的な型に依存せず、インターフェースだけ定義

---

### パターン5: 外部APIクライアントの型定義

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stripe import Customer, PaymentIntent
    from sendgrid import SendGridAPIClient

class PaymentService:
    def charge(self, amount: int) -> "PaymentIntent":
        import stripe  # 実行時にインポート
        return stripe.PaymentIntent.create(amount=amount)

class EmailService:
    def send(self, to: str) -> None:
        from sendgrid import SendGridAPIClient  # 実行時
        # 送信処理...
```

**用途:** 外部ライブラリを使う場合でも起動時にインポートしない

---

### パターン6: サービス層の依存注入

```python
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from django.core.cache import cache

class CacheProtocol(Protocol):
    def get(self, key: str) -> any: ...
    def set(self, key: str, value: any) -> None: ...

class UserService:
    def __init__(self, cache: CacheProtocol):
        self.cache = cache

    def get_user_cached(self, user_id: int) -> "User":
        from .models import User  # 実行時インポート
        cached = self.cache.get(f"user_{user_id}")
        if cached:
            return cached
        user = User.objects.get(id=user_id)
        self.cache.set(f"user_{user_id}", user)
        return user
```

**メリット:** テスト時にモックを注入しやすい

---

### パターン7: 設定の型定義

```python
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from redis import Redis
    from elasticsearch import Elasticsearch

class AppConfig(TypedDict):
    debug: bool
    redis_client: "Redis"
    es_client: "Elasticsearch"

def init_config() -> AppConfig:
    from redis import Redis
    from elasticsearch import Elasticsearch

    return {
        "debug": True,
        "redis_client": Redis(),
        "es_client": Elasticsearch()
    }
```

---

## Django モデルでの使用例（簡潔版）

```python
from django.db import models
from django.contrib.auth import get_user_model
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

User = get_user_model()

class Tweet(models.Model):
    author: "AbstractBaseUser" = models.ForeignKey(User, on_delete=models.CASCADE)
    content: str = models.TextField(max_length=280)
    created_at: datetime = models.DateTimeField(auto_now_add=True)
```

**効果:** エディタで `tweet.author.username` が補完される

---

## よくあるミス

### ❌ 間違い: 実行時にインポートしたものを型注釈に使う

```python
from expensive_module import HeavyClass  # 常にインポートされる

def process(data: HeavyClass):  # 型チェックはOKだが実行時に重い
    ...
```

### ✅ 正解: TYPE_CHECKING で分ける

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from expensive_module import HeavyClass

def process(data: "HeavyClass"):  # 実行時はインポートされない
    from expensive_module import HeavyClass  # 使うときだけ
    ...
```

---

## まとめ

| パターン | 用途 |
|---------|------|
| **循環参照回避** | 相互にインポートし合うモジュール |
| **遅延インポート** | 重いライブラリの起動時間削減 |
| **Protocol** | インターフェースだけ定義したい |
| **Django モデル** | get_user_model() 対応 |

**基本ルール:**
- 型チェック専用のインポートは `if TYPE_CHECKING:` 内に
- 型注釈で使う時は文字列 `"ClassName"` にする
- 実行時に必要なら関数内でインポート
