## 基本パターン

[mypy-モジュール名]

---

## 具体例

### 1. 特定のモジュール

[mypy-tweets.models]
ignore_errors = True

tweets/models.py だけ無視

---

### 2. パッケージ全体（ワイルドカード）

[mypy-tweets.*]
ignore_errors = True

tweets/ 配下の全ファイル無視

---

### 3. 特定のサードパーティライブラリ

[mypy-django.*]
ignore_missing_imports = True

django パッケージ全体で import エラー無視

---

### 4. 複数指定

[mypy-tweets.*,user.*]
ignore_errors = True

tweets と user の両方

---

### ルール

| パターン           | 意味                  |
| ------------------ | --------------------- |
| mypy-tweets.models | tweets/models.py      |
| mypy-tweets.\*     | tweets/ 配下全て      |
| mypy-django.\*     | django パッケージ全体 |
| mypy-\*.models     | 全アプリの models.py  |

`*` = ワイルドカード（何でもマッチ）
