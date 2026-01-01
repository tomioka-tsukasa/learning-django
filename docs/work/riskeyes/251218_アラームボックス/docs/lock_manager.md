# LockManager 解説

## LockManager とは

**「同時に1つだけ実行させる」ための仕組み**

複数プロセスが同時に同じ処理を実行すると競合状態が発生する。これを防ぐためにロック（排他制御）を使う。

---

## なぜロックが必要か

### 問題: 競合状態

```
時刻    プロセスA              プロセスB
────────────────────────────────────────────
0:00    トークン読み込み
0:01                           トークン読み込み
0:02    API呼び出し
0:03                           API呼び出し
0:04    新トークン取得
0:05                           新トークン取得（Aのは無効に！）
0:06    DB保存（古いトークン）  ← ここで問題！
0:07                           DB保存（新しいトークン）

結果: DB に無効なトークンが保存される可能性
```

### 解決: ロック

```
時刻    プロセスA              プロセスB
────────────────────────────────────────────
0:00    ロック取得 🔒
0:01                           ロック待ち... ⏳
0:02    トークン読み込み
0:03    API呼び出し            ロック待ち... ⏳
0:04    新トークン取得
0:05    DB保存
0:06    ロック解放 🔓
0:07                           ロック取得 🔒
0:08                           トークン読み込み（新しい！）
0:09                           期限切れじゃない → 何もしない
0:10                           ロック解放 🔓

結果: 安全に1つずつ処理される
```

---

## LockManager の仕組み

### キャッシュを使った排他制御

```python
class LockManager:
    def await_lock(self):
        # キャッシュに「使用中」フラグを立てる
        # 既にフラグがあれば待機
        self.cache.add("lock_key", {"acquired_at": now})

    def release_lock(self):
        # キャッシュの「使用中」フラグを消す
        self.cache.delete("lock_key")
```

### キャッシュの実体（環境別）

| 環境 | キャッシュ | 説明 |
|------|------------|------|
| ローカル | LocMemCache | プロセス内メモリ |
| 本番 | Valkey | 共有キャッシュサーバー（Redis 互換） |

### 設定箇所

```python
# core/config/_production_settings.py
"lock": {
    "BACKEND": "django_valkey.cache.ValkeyCache",
    "LOCATION": "valkey://10.146.0.100:6379",
}

LOCK_CACHE_ALIASES = "lock"
```

---

## 主要メソッド

| メソッド | 役割 |
|----------|------|
| `await_lock()` | ロック取得（取れるまで待機） |
| `release_lock()` | ロック解放 |
| `lock()` | with 句用（取得→処理→解放を自動化） |

---

## await_lock 詳細

```python
def await_lock(
    self, timeout: int = 600, initial_delay: float = 1.0, max_delay: float = 30.0
):
```

| 引数 | デフォルト | 意味 |
|------|------------|------|
| `timeout` | 600秒 | 最大待機時間（超えたらエラー） |
| `initial_delay` | 1.0秒 | 最初のリトライ間隔 |
| `max_delay` | 30.0秒 | リトライ間隔の上限 |

### cache.add の仕組み

```
add() = 「キーが存在しなければ追加」

┌─────────────────────────────────────────────┐
│ キーが存在しない → 追加成功 → True を返す    │
│ キーが既に存在   → 何もしない → False を返す │
└─────────────────────────────────────────────┘

これにより「早い者勝ち」が実現する
```

### ループの流れ

```
while True:
    │
    ├─→ cache.add() 試行
    │       │
    │       ├─ 成功 → return（正常終了）
    │       │
    │       └─ 失敗 → 続行
    │
    ├─→ タイムアウト確認
    │       │
    │       ├─ 超過 → raise TimeoutError
    │       │
    │       └─ まだ余裕 → 続行
    │
    ├─→ time.sleep()（待機）
    │
    └─→ ループ先頭へ
```

### 指数バックオフ + ジッター

```python
jitter = random.uniform(0.5, 1.5)  # ランダム係数
sleep_time = min(current_delay * jitter, max_delay)
time.sleep(sleep_time)

current_delay = min(current_delay * 1.5, max_delay)  # 次回は1.5倍
```

**待機時間の変化:**

| 回数 | current_delay | 実際の待機（ジッター込み） |
|------|---------------|---------------------------|
| 1回目 | 1.0秒 | 0.5〜1.5秒 |
| 2回目 | 1.5秒 | 0.75〜2.25秒 |
| 3回目 | 2.25秒 | 1.1〜3.4秒 |
| ... | ... | ... |
| 上限 | 30秒 | 15〜45秒 |

**なぜ指数バックオフ + ジッター？**

同時に複数プロセスが待機している場合、全員が同じ間隔でリトライすると競合が多発する。ランダムな間隔にすることで競合を分散。

---

## release_lock 詳細

```python
def release_lock(self, raise_exception: bool = False):
```

| 引数 | デフォルト | 意味 |
|------|------------|------|
| `raise_exception` | False | エラー時に例外を投げるか |

### 処理内容

```python
self.cache.delete(self._lock_key)  # キャッシュから削除 = ロック解放
```

---

## lock（コンテキストマネージャ）

### with 句とは

**「開始処理」と「終了処理」を自動でやってくれる仕組み**

```python
# with なし（忘れるリスクあり）
lock_manager.await_lock()
do_something()
lock_manager.release_lock()  # ← 忘れるとロックされっぱなし

# with あり（自動で解放）
with lock_manager.lock():
    do_something()
# ← 自動で release_lock() される
```

### @contextmanager

```python
from contextlib import contextmanager

@contextmanager
def lock(
    self, timeout: int = 600, initial_delay: float = 1.0, max_delay: float = 30.0
):
    try:
        self.await_lock(
            timeout=timeout, initial_delay=initial_delay, max_delay=max_delay
        )
        yield  # ← ここで with の中身が実行される
    finally:
        self.release_lock()  # ← エラーでも必ず実行
```

### yield の動き

```
lock() メソッド                  with の中
─────────────────────────────────────────────
await_lock()
      │
      ↓
    yield ─────────────→ do_something()
                               │
      ←───────────────────────┘
      │
      ↓
release_lock()
```

### try/finally の重要性

```python
with lock_manager.lock():
    raise Exception("エラー発生！")

# finally があるので:
# 1. await_lock() → ロック取得
# 2. yield → 処理中にエラー発生
# 3. finally → release_lock() → ロック解放 ✅
```

---

## 使用例

```python
lock_manager = LockManager(
    name="alarmbox-token-refresh",  # ロックの名前（識別用）
    parallelism=1                   # 同時実行数（1 = 1つだけ）
)

# 基本的な使い方
with lock_manager.lock(timeout=30):
    token.refresh_from_db()
    result = AlarmboxClient.refresh_token(...)
    token.save()

# 細かく制御
with lock_manager.lock(timeout=60, initial_delay=0.5, max_delay=10.0):
    do_something()
```

---

## parallelism について

```python
LockManager(name="xxx", parallelism=3)
```

| parallelism | 意味 |
|-------------|------|
| 1 | 同時に1つだけ実行可能 |
| 3 | 同時に3つまで実行可能（スロットが3つ） |

---

## まとめ

| 概念 | 意味 |
|------|------|
| `LockManager` | 同時実行を防ぐ仕組み（キャッシュベース） |
| `await_lock` | ロック取得（取れるまで待機） |
| `release_lock` | ロック解放 |
| `lock()` | with 句用（取得→処理→解放を自動化） |
| `@contextmanager` | with 対応にするデコレータ |
| `yield` | 一時停止して with の中を実行 |
