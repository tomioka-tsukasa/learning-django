# マイグレーションSQL生成カスタムコマンド解説

## 概要

**makemigrationsを拡張して、`.py` と同時に `.sql` ファイルも生成するカスタムコマンド**

---

## なぜ必要？

### 問題

Django標準では `.py` ファイルしか生成されない：

```bash
python manage.py makemigrations
# → tweets/migrations/0001_initial.py のみ生成
```

実際のSQLを見るには手動で：

```bash
python manage.py sqlmigrate tweets 0001 > 0001_initial.sql
```

---

### 解決

カスタムコマンドで自動化：

```bash
python manage.py makemigrations
# → .py と .sql を同時生成
```

---

## ユースケース

### 1. DBAレビュー

```
開発者: マイグレーション作成
    ↓
DBA: SQLファイルをレビュー（DDL確認）
    ↓
承認後: 本番環境へデプロイ
```

**理由:** `.py` より `.sql` の方がDBAが読みやすい

---

### 2. 本番環境での手動実行

```sql
-- 0001_initial.sql
CREATE TABLE tweets_tweet (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    ...
);
```

本番DBに直接実行（Djangoを経由しない）

---

### 3. Git差分レビュー

```diff
+ -- 0002_add_likes.sql
+ ALTER TABLE tweets_tweet ADD COLUMN likes_count INTEGER NOT NULL DEFAULT 0;
```

SQLファイルがあれば、PRレビュー時に「どんなテーブル変更か」が一目瞭然

---

### 4. ドキュメント化

SQLファイルがスキーマ変更の履歴になる

---

## 実際の導入シチュエーション

### ケース1: 大規模プロジェクト

**状況:**
- 複数チーム開発
- DBAチームが存在
- 本番DBへの変更は厳格に管理

**対応:**
1. 開発者がマイグレーション作成
2. SQLファイルが自動生成
3. DBAがSQLレビュー
4. 承認後、本番適用

---

### ケース2: レガシーDB統合

**状況:**
- Django以外のシステムも同じDBを使用
- マイグレーションを直接実行できない

**対応:**
1. SQLファイルを生成
2. 既存のDB変更フローに組み込む
3. 手動でSQLを実行

---

### ケース3: セキュリティ要件

**状況:**
- 本番環境でDjangoコードを実行できない
- SQLのみ実行可能

**対応:**
SQLファイルを事前生成して承認プロセスを通す

---

## 必要性の判断

### 必要なケース

- ✅ DBAレビューが必要
- ✅ 本番DBへの直接アクセスが制限
- ✅ チーム規模が大きい
- ✅ 金融・医療など厳格な業界

---

### 不要なケース

- ❌ 小規模プロジェクト
- ❌ 開発者が全権限を持つ
- ❌ スタートアップ（スピード重視）

---

## このコマンドの機能

### 1. 通常モード

```bash
python manage.py makemigrations
```

- `.py` と `.sql` を同時生成
- 新規マイグレーションのみ対象

---

### 2. 既存変換モード

```bash
python manage.py makemigrations --convert-to-sql
```

- 既存の `.py` から `.sql` を生成
- プロジェクト導入時に使う

---

## コード解説（簡潔版）

### 1. 新規ファイル検出

```python
# 実行前のファイル一覧
before_files = self.get_migration_files(target_apps)

# makemigrations実行
super().handle(*args, **options)

# 実行後のファイル一覧
after_files = self.get_migration_files(target_apps)

# 差分 = 新規ファイル
new_files = after_files - before_files
```

---

### 2. SQL生成

```python
for file_path in new_files:
    # .py を読み込んで operations を取得
    operations = migration_class.operations

    # 各operationをSQLに変換
    for operation in operations:
        if operation_type == "CreateModel":
            sql = "CREATE TABLE ..."
        elif operation_type == "AddField":
            sql = "ALTER TABLE ... ADD COLUMN ..."
        # ...

    # .sql ファイルに書き込み
    with open(sql_file, "w") as f:
        f.write(sql)
```

---

### 3. サポートする操作

- CreateModel → `CREATE TABLE`
- DeleteModel → `DROP TABLE`
- AddField → `ALTER TABLE ADD COLUMN`
- RemoveField → `ALTER TABLE DROP COLUMN`
- AlterField → `ALTER TABLE MODIFY`
- RenameField → `ALTER TABLE RENAME COLUMN`
- AddIndex → `CREATE INDEX`
- その他...

---

## 実務での使い方

### 導入時

```bash
# 既存マイグレーションをSQL化
python manage.py makemigrations --convert-to-sql
```

---

### 日常運用

```bash
# 通常通り
python manage.py makemigrations

# → .py と .sql が両方できる
# → .sql をレビュー依頼
# → 承認後、migrate実行
```

---

## まとめ

| 項目 | 内容 |
|------|------|
| **目的** | マイグレーションのSQL可視化・レビュー |
| **必要性** | 大規模/厳格なプロジェクトで有効 |
| **メリット** | DBAレビュー、本番手動実行、履歴管理 |
| **デメリット** | 小規模プロジェクトでは過剰 |

**小規模・学習プロジェクトでは不要。エンタープライズ向けの機能。**
