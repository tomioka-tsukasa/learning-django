# Python/Django ロギング完全ガイド

## 目次

1. [ロギングとは](#ロギングとは)
2. [基本的な使い方](#基本的な使い方)
3. [ログレベル](#ログレベル)
4. [Logger の取得方法](#logger-の取得方法)
5. [Django での設定](#django-での設定)
6. [実践例](#実践例)
7. [print vs logger](#print-vs-logger)
8. [ベストプラクティス](#ベストプラクティス)

---

## ロギングとは

**プログラムの実行状況や問題を記録する仕組み**

```python
# 悪い例
print("ユーザーがログインしました")  # 開発時しか見えない

# 良い例
logger.info("ユーザーがログインしました")  # ファイルやクラウドに保存できる
```

---

## 基本的な使い方

### インポートと初期化

```python
import logging

# __name__ = 現在のモジュール名（例: user.views）
logger = logging.getLogger(__name__)
```

### ログ出力

```python
logger.debug("デバッグ情報")
logger.info("情報メッセージ")
logger.warning("警告")
logger.error("エラー")
logger.critical("致命的エラー")
```

---

## ログレベル

### レベルの重要度

```
DEBUG (10)
  ↓ 詳細
INFO (20)
  ↓
WARNING (30)
  ↓
ERROR (40)
  ↓
CRITICAL (50)
  ↓ 重大
```

### 各レベルの用途

| レベル | 数値 | 用途 | 例 |
|--------|------|------|-----|
| `DEBUG` | 10 | 開発時の詳細情報 | 変数の値、処理の流れ、SQL クエリ |
| `INFO` | 20 | 通常の情報 | ユーザー登録、ログイン成功、処理完了 |
| `WARNING` | 30 | 警告（問題ではない） | 非推奨機能の使用、設定の不備 |
| `ERROR` | 40 | エラー（処理は継続） | バリデーションエラー、API 失敗 |
| `CRITICAL` | 50 | 致命的エラー | サーバークラッシュ、DB 接続失敗 |

### 使い分けの例

```python
# DEBUG: 開発時のみ必要な詳細情報
logger.debug(f"Received data: {request.data}")
logger.debug(f"Query executed: {query}")

# INFO: 正常な動作の記録
logger.info(f"User {username} logged in successfully")
logger.info(f"Email sent to {email}")

# WARNING: 問題になる可能性がある状況
logger.warning(f"Deprecated API endpoint used: /old-api/")
logger.warning(f"Rate limit approaching: {request_count}/1000")

# ERROR: エラーだが処理は継続
logger.error(f"Failed to send email: {e}")
logger.error(f"External API timeout: {api_url}")

# CRITICAL: システムが動作不能
logger.critical(f"Database connection lost!")
logger.critical(f"Payment gateway unavailable!")
```

---

## Logger の取得方法

### パターン 1: モジュール名を使う（推奨）

```python
import logging

logger = logging.getLogger(__name__)
```

**`__name__` の値:**
- `user/views.py` → `user.views`
- `user/serializers.py` → `user.serializers`

**メリット:**
- どのファイルからのログか自動で識別
- 設定でモジュールごとにログレベルを変更可能

---

### パターン 2: カスタム名を使う

```python
logger = logging.getLogger('my_custom_logger')
```

**用途:**
- 特定の機能専用のロガー
- 例: `payment_logger`, `security_logger`

---

## Django での設定

### 基本設定（settings.py）

```python
# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    # フォーマッター: ログの表示形式
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },

    # ハンドラー: ログの出力先
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/debug.log',
            'formatter': 'verbose',
        },
    },

    # ロガー: どのログをどのハンドラーに送るか
    'loggers': {
        'user': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    },
}
```

---

### フォーマッター詳細

#### 利用可能な変数

```python
'format': '{levelname} {asctime} {name} {module} {funcName} {lineno} {message}'
```

| 変数 | 説明 | 例 |
|------|------|-----|
| `levelname` | ログレベル名 | INFO, ERROR |
| `asctime` | 日時 | 2025-12-12 10:30:45 |
| `name` | ロガー名 | user.views |
| `module` | モジュール名 | views |
| `funcName` | 関数名 | login_view |
| `lineno` | 行番号 | 42 |
| `message` | メッセージ | User logged in |

#### 出力例

```
INFO 2025-12-12 10:30:45 user.views login_view 42 User taro logged in successfully
```

---

### ハンドラーの種類

#### 1. StreamHandler（コンソール出力）

```python
'console': {
    'class': 'logging.StreamHandler',
    'formatter': 'simple',
}
```

**用途:** 開発時、デバッグ時

---

#### 2. FileHandler（ファイル出力）

```python
'file': {
    'class': 'logging.FileHandler',
    'filename': 'logs/app.log',
    'formatter': 'verbose',
}
```

**用途:** 本番環境、ログの永続化

---

#### 3. RotatingFileHandler（ファイルローテーション）

```python
'rotating_file': {
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': 'logs/app.log',
    'maxBytes': 1024 * 1024 * 10,  # 10MB
    'backupCount': 5,  # 5世代保存
    'formatter': 'verbose',
}
```

**動作:**
- `app.log` が 10MB に達すると `app.log.1` にリネーム
- 最大 5 ファイル保存（古いものから削除）

**用途:** ディスク容量を節約したい場合

---

#### 4. TimedRotatingFileHandler（時間ベースローテーション）

```python
'timed_file': {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': 'logs/app.log',
    'when': 'midnight',  # 毎日深夜0時
    'interval': 1,
    'backupCount': 30,  # 30日分保存
    'formatter': 'verbose',
}
```

**用途:** 日次ログレポート

---

### 実務的な設定例

```python
# settings.py
import os

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {funcName}:{lineno} - {message}',
            'style': '{',
        },
    },

    'handlers': {
        # 開発環境: コンソールに全て出力
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },

        # 本番環境: INFOレベル以上をファイルに保存（日次ローテーション）
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'when': 'midnight',
            'backupCount': 30,
            'formatter': 'verbose',
        },

        # エラー専用ログ
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },

    'loggers': {
        # アプリケーション全体
        '': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
        },

        # userアプリ専用
        'user': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',  # userアプリだけDEBUGレベル
            'propagate': False,
        },

        # Django本体のログ
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },

        # データベースクエリ（開発時のみ有効化）
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ログディレクトリ作成
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
```

---

## 実践例

### views.py での使用

```python
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate

logger = logging.getLogger(__name__)  # user.views


class LoginView(APIView):
    def post(self, request):
        logger.debug(f"Login attempt with data: {request.data}")

        username = request.data.get('username')
        password = request.data.get('password')

        # 認証
        user = authenticate(username=username, password=password)

        if user is None:
            logger.warning(f"Login failed for username: {username}")
            return Response(
                {"error": "認証失敗"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            logger.warning(f"Inactive user login attempt: {username}")
            return Response(
                {"error": "アカウントが無効です"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 成功
        logger.info(f"User logged in successfully: {username}")

        return Response({
            "message": "ログイン成功",
            "user": {
                "id": user.id,
                "username": user.username
            }
        })
```

**出力例:**

```
[DEBUG] 2025-12-12 10:30:45 user.views post:15 - Login attempt with data: {'username': 'taro', 'password': '***'}
[INFO] 2025-12-12 10:30:45 user.views post:35 - User logged in successfully: taro
```

---

### エラーハンドリング

```python
import logging

logger = logging.getLogger(__name__)


def send_email(to, subject, body):
    try:
        # メール送信処理
        smtp.send(to, subject, body)
        logger.info(f"Email sent to {to}: {subject}")
    except SMTPException as e:
        logger.error(f"Failed to send email to {to}: {e}")
        # 処理は継続（メールは必須ではない）
    except Exception as e:
        logger.critical(f"Unexpected error in send_email: {e}")
        raise  # 想定外のエラーは再送出
```

---

### セキュリティログ

```python
import logging

security_logger = logging.getLogger('security')


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        ip_address = request.META.get('REMOTE_ADDR')

        user = authenticate(username=username, password=password)

        if user is None:
            # 失敗ログ（攻撃検知用）
            security_logger.warning(
                f"Failed login attempt: username={username}, ip={ip_address}"
            )

            # 連続失敗をカウント
            failed_count = cache.incr(f'login_fail_{ip_address}', default=0)

            if failed_count > 5:
                security_logger.error(
                    f"Possible brute force attack from {ip_address}"
                )
        else:
            security_logger.info(
                f"Successful login: username={username}, ip={ip_address}"
            )
```

---

## print vs logger

### 比較表

| 機能 | `print` | `logger` |
|------|---------|----------|
| **レベル分け** | ❌ できない | ✅ DEBUG/INFO/ERROR等 |
| **出力先制御** | ❌ 標準出力のみ | ✅ ファイル、DB、クラウド等 |
| **フォーマット** | ❌ 手動 | ✅ 自動（時刻、ファイル名等） |
| **本番環境** | ❌ 邪魔 | ✅ 必須 |
| **検索・分析** | ❌ 困難 | ✅ 容易 |
| **オンオフ切替** | ❌ コード修正必要 | ✅ 設定で可能 |

---

### print の問題点

```python
# 開発時
def calculate_total(items):
    print(f"Calculating total for {len(items)} items")  # デバッグ用
    total = sum(item.price for item in items)
    print(f"Total: {total}")  # デバッグ用
    return total
```

**問題:**
1. 本番環境でも出力される（パフォーマンス低下）
2. 出力先が標準出力だけ（記録されない）
3. 重要度が分からない
4. 削除し忘れると邪魔

---

### logger に置き換え

```python
import logging

logger = logging.getLogger(__name__)


def calculate_total(items):
    logger.debug(f"Calculating total for {len(items)} items")
    total = sum(item.price for item in items)
    logger.debug(f"Total: {total}")
    return total
```

**メリット:**
1. 本番環境では `DEBUG` を無効化（設定で制御）
2. ファイルに保存される
3. レベルで重要度が分かる
4. 残しても問題ない

---

## ベストプラクティス

### 1. 適切なログレベルを使う

```python
# ❌ 悪い例
logger.info("Variable x = 123")  # デバッグ情報にINFOは不適切

# ✅ 良い例
logger.debug("Variable x = 123")  # DEBUGが適切
```

---

### 2. 構造化されたログメッセージ

```python
# ❌ 悪い例
logger.info("User login")

# ✅ 良い例
logger.info(f"User logged in: username={username}, ip={ip_address}")
```

---

### 3. 機密情報をログに出さない

```python
# ❌ 悪い例
logger.info(f"User logged in with password: {password}")

# ✅ 良い例
logger.info(f"User logged in: username={username}")
```

---

### 4. 例外ログには `exc_info=True` を使う

```python
try:
    risky_operation()
except Exception as e:
    # ❌ 悪い例
    logger.error(f"Error: {e}")

    # ✅ 良い例（スタックトレースも記録）
    logger.error("Error in risky_operation", exc_info=True)
```

**出力:**
```
ERROR Error in risky_operation
Traceback (most recent call last):
  File "views.py", line 42, in risky_operation
    result = 1 / 0
ZeroDivisionError: division by zero
```

---

### 5. モジュールごとにロガーを取得

```python
# ❌ 悪い例
logger = logging.getLogger('my_logger')  # 全ファイルで同じ名前

# ✅ 良い例
logger = logging.getLogger(__name__)  # ファイルごとに自動で名前付け
```

---

### 6. ログディレクトリを gitignore に追加

```bash
# .gitignore
logs/
*.log
```

---

## まとめ

### ログレベルの使い分け

- `DEBUG`: 開発時の詳細情報
- `INFO`: 正常な動作の記録
- `WARNING`: 注意が必要な状況
- `ERROR`: エラー（処理継続）
- `CRITICAL`: システム停止レベル

### 開発フロー

1. **開発時**: コンソールに `DEBUG` レベルで出力
2. **ステージング**: ファイルに `INFO` レベルで保存
3. **本番**: ファイルローテーション + エラーログ分離

### 実務での活用

- ユーザー行動の追跡
- エラーの原因調査
- セキュリティ監視
- パフォーマンス分析

**ログは運用の目！適切に記録しましょう。**
