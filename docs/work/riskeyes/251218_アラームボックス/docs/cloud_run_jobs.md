# CloudRunJobs 解説

## CloudRunJobs とは

**Google Cloud Run Jobs** を Django コマンドから簡単に使えるようにしたラッパークラス。

### Cloud Run Jobs の特徴

- サーバーレスでコンテナを実行
- スケジュール実行（cron）が可能
- 実行時間に応じた従量課金
- 自動スケーリング・リトライ

---

## スケジュール定義（cron 形式）

```python
schedule = "0 */12 * * *"
```

```
┌───────────── 分 (0-59)
│ ┌─────────── 時 (0-23)
│ │ ┌───────── 日 (1-31)
│ │ │ ┌─────── 月 (1-12)
│ │ │ │ ┌───── 曜日 (0-7, 0と7は日曜)
│ │ │ │ │
0 */12 * * *
```

| フィールド | 値     | 意味                       |
| ---------- | ------ | -------------------------- |
| 分         | `0`    | 0分ちょうど                |
| 時         | `*/12` | 12時間ごと（0時, 12時）    |
| 日         | `*`    | 毎日                       |
| 月         | `*`    | 毎月                       |
| 曜日       | `*`    | 毎曜日                     |

**結果**: 毎日 0:00 と 12:00 に実行

---

## ローカル vs GCP の違い

### 実行環境

| 環境       | コンテナ | スケジューラー   |
| ---------- | -------- | ---------------- |
| ローカル   | なし     | なし（手動実行） |
| GCP        | あり     | Cloud Scheduler  |

### ローカル実行時の動作

```python
# command.py:537-540
def delay(self, *args, **kwargs):
    if self.env == "local" or self.env == "test":
        self.handle(*args, **kwargs)  # ← 直接実行（GCP API 呼ばない）
        self.operation = MockOperation()
        return self.operation
```

ローカルでは Cloud Run API を呼ばず、直接 `run()` を実行する。

```
【本番環境】
manage.py → Cloud Run API → GCP がコンテナ起動 → run() 実行
                 ↑
              課金発生

【ローカル環境】
manage.py → 直接 run() 実行
              ↑
           課金なし・GCP接続なし
```

---

## コンテナとは

**「アプリと必要なものを全部まとめた箱」**

### 問題: 環境の違い

```
開発者A「俺の PC では動くよ」
開発者B「俺の PC では動かない...」
本番サーバー「エラーです」

原因:
├── Python のバージョンが違う
├── ライブラリのバージョンが違う
└── OS の設定が違う
```

### 解決: コンテナ

```
┌─────────────────────────────┐
│ コンテナ（箱）               │
│  ├── Python 3.12            │
│  ├── Django                 │
│  ├── 必要なライブラリ全部    │
│  └── アプリのコード          │
└─────────────────────────────┘

この箱ごと渡せば、どこでも同じ環境で動く
```

### ローカルと GCP のコンテナ

| 環境       | コンテナ                         |
| ---------- | -------------------------------- |
| ローカル   | なし（直接 Python 実行）         |
| GCP        | あり（Docker コンテナ内で実行）  |

---

## Docker 関連ファイル

```
/riskeyes-v2-api/
├── DockerfileServer              ← コンテナの設計図
├── docker-compose.yml            ← ローカル開発用の構成
└── docker/
    └── server/
        ├── entrypoint.sh         ← 起動スクリプト
        ├── run_django_command.sh ← コマンド実行スクリプト
        └── nginx/                ← Nginx 設定
```

### DockerfileServer の概要

```dockerfile
# ベースイメージ（Python 3.12 入りの軽量 Linux）
FROM python:3.12.12-slim AS builder

# 作業ディレクトリ
WORKDIR /app

# Pipfile から依存パッケージをインストール
COPY Pipfile Pipfile.lock ./
RUN pipenv sync

# アプリケーションコードをコピー
COPY ./ /app/

# 起動コマンド
CMD "/entrypoint.sh"
```

### デプロイの流れ

```
DockerfileServer（設計図）
       ↓ docker build
Docker イメージ（ミールキット完成品）
       ↓ docker push
GCP Container Registry（冷凍庫に保管）
       ↓ Cloud Run が pull
コンテナ実行（温めて提供）
```

---

## GCP での実行の仕組み

### 実行フロー

```
Cloud Scheduler
    ↓ 「12時間経ったよ」
Cloud Run Jobs API
    ↓ 「コンテナ起動して」
Docker コンテナ起動
    ↓ 引数: ["refresh-alarmbox-token"]
run_django_command.sh
    ↓
python manage.py refresh_alarmbox_token
    ↓
Command.run() 実行
```

### run_django_command.sh

```bash
/app/.venv/bin/python /app/manage.py "$@"
```

| 部分                    | 意味                     |
| ----------------------- | ------------------------ |
| `/app/.venv/bin/python` | コンテナ内の Python      |
| `/app/manage.py`        | Django のエントリポイント |
| `"$@"`                  | 渡された引数すべて        |

### Cloud Run Jobs の API 呼び出し

```python
# command.py:545-553
request = run_v2.RunJobRequest(
    name=self.job_path(),
    overrides=run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=arguments,  # ← ここで引数を渡す
            )
        ]
    ),
)
```

---

## 初回実行とスケジュール開始

### スケジュール発火のタイミング

| 項目               | 回答                               |
| ------------------ | ---------------------------------- |
| 初回の実行         | 手動 または 次のスケジュール時刻   |
| スケジュール発火開始 | デプロイ完了後                    |

### 具体例

```
schedule = "0 */12 * * *"  （0:00 と 12:00 に実行）

【シナリオ】14:00 にデプロイした場合

14:00  デプロイ完了
  ↓    （何も起きない）
0:00   ← 初回の自動実行（デプロイから10時間後）
  ↓
12:00  ← 2回目
  ...
```

**デプロイ直後に自動実行はされない。次のスケジュール時刻まで待つ。**

### 推奨フロー

```
1. save_alarmbox_token で初回トークン保存
      ↓
2. デプロイ
      ↓
3. Cloud Scheduler or Cloud Run Jobs で手動実行
      ↓
4. 以降は 12時間ごとに自動
```

### 手動実行の方法

**Cloud Run Jobs から（おすすめ）**

```
GCP コンソール
  → Cloud Run
    → ジョブ
      → refresh-alarmbox-token-xxx
        → 「実行」ボタン
```

**gcloud コマンド**

```bash
gcloud run jobs execute refresh-alarmbox-token-production --region=asia-northeast1
```

---

## CloudRunJobs 基底クラスの主要機能

| 機能          | 説明                                   |
| ------------- | -------------------------------------- |
| `schedule`    | cron 形式でスケジュール定義            |
| `parallelism` | 同時実行数（デフォルト1）              |
| `timeout`     | タイムアウト秒数                       |
| `max_retries` | 失敗時のリトライ回数                   |
| `LockManager` | 重複実行防止のロック機構（自動）       |
| `delay()`     | 即時実行をトリガー                     |
| `reserve()`   | 指定時刻に実行を予約                   |

---

## self.stdout について

Django 管理コマンドの標準出力ストリーム。

```python
self.stdout.write("メッセージ")  # Django コマンド推奨
print("メッセージ")              # これでも動くが非推奨
```

### 出力先

| 環境       | 出力先          |
| ---------- | --------------- |
| ローカル   | ターミナル画面  |
| Cloud Run  | Cloud Logging   |

### スタイル付きメッセージ

```python
self.stdout.write(self.style.SUCCESS("成功"))  # 緑色
self.stdout.write(self.style.ERROR("失敗"))    # 赤色
self.stdout.write(self.style.WARNING("警告"))  # 黄色
```

---

## 用語集

| 用語            | 説明                                       |
| --------------- | ------------------------------------------ |
| cron            | 時間指定で自動実行する仕組み               |
| コンテナ        | アプリと環境をまとめた箱                   |
| Docker          | コンテナを扱うツール                       |
| Cloud Run       | GCP でコンテナを動かすサービス             |
| Cloud Scheduler | GCP の cron サービス（スケジュール管理）   |
| Cloud Logging   | GCP のログ収集サービス                     |
