# curl コマンドガイド

## バックスラッシュ `\`

シェルでの**行の継続**。長いコマンドを複数行に分けて書くため。

```bash
# これは1行として実行される
curl -X POST http://example.com \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# 上と同じ
curl -X POST http://example.com -H "Content-Type: application/json" -d '{"key": "value"}'
```

---

## 基本オプション

| オプション | 意味 | 例 |
|-----------|------|-----|
| `-X` | HTTPメソッド指定 | `-X POST`, `-X PUT`, `-X DELETE` |
| `-H` | ヘッダー追加 | `-H "Content-Type: application/json"` |
| `-d` | リクエストボディ（data） | `-d '{"name": "test"}'` |

```bash
# GET（デフォルトなので -X 不要）
curl http://example.com/api/users

# POST
curl -X POST http://example.com/api/users \
  -H "Content-Type: application/json" \
  -d '{"name": "田中"}'

# DELETE
curl -X DELETE http://example.com/api/users/1
```

---

## よく使うオプション

| オプション | 意味 | 用途 |
|-----------|------|------|
| `-i` | レスポンスヘッダーも表示 | ステータスコード確認 |
| `-v` | 詳細表示（verbose） | デバッグ時 |
| `-s` | 進捗表示を消す（silent） | スクリプト内で使用 |
| `-o` | ファイルに保存 | ダウンロード |
| `-O` | 元のファイル名で保存 | ダウンロード |
| `-L` | リダイレクトに従う | 301/302対応 |
| `-k` | SSL証明書エラー無視 | 開発環境 |
| `-u` | Basic認証 | `-u user:pass` |
| `-F` | フォームデータ（multipart） | ファイルアップロード |

---

## 実用例

```bash
# レスポンスヘッダー確認
curl -i http://localhost:8000/api/users

# 詳細デバッグ（リクエスト/レスポンス全部見える）
curl -v http://localhost:8000/api/users

# ファイルダウンロード
curl -o output.pdf http://example.com/file.pdf
curl -O http://example.com/file.pdf  # file.pdf として保存

# リダイレクト対応
curl -L http://example.com/redirect

# Basic認証
curl -u username:password http://example.com/api

# ファイルアップロード（multipart/form-data）
curl -X POST http://example.com/upload \
  -F "file=@/path/to/file.pdf" \
  -F "name=document"

# Bearer トークン認証
curl -H "Authorization: Bearer eyJhbGc..." http://example.com/api

# JSONをファイルから読み込む
curl -X POST http://example.com/api \
  -H "Content-Type: application/json" \
  -d @request.json
```

---

## `-d` vs `-F`

| オプション | Content-Type | 用途 |
|-----------|--------------|------|
| `-d` | `application/x-www-form-urlencoded` または手動指定 | JSON、フォーム |
| `-F` | `multipart/form-data`（自動） | ファイルアップロード |

```bash
# -d でJSON（Content-Type手動指定が必要）
curl -X POST http://example.com/api \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'

# -d でフォーム（デフォルトのContent-Type）
curl -X POST http://example.com/api \
  -d "name=test&age=20"

# -F でファイル（Content-Type自動）
curl -X POST http://example.com/upload \
  -F "file=@photo.jpg"
```

---

## 組み合わせ例

```bash
# 本番でよく使うパターン
curl -s -X POST http://localhost:8000/api \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer xxx" \
  -d '{"key": "value"}' | jq .

# jq でJSON整形（見やすくなる）
```

---

## 補足: `@` の使い方

`-d` や `-F` で `@` を使うとファイルから読み込める。

```bash
# JSONファイルから読み込み
curl -X POST http://example.com/api \
  -H "Content-Type: application/json" \
  -d @data.json

# ファイルアップロード
curl -X POST http://example.com/upload \
  -F "file=@/path/to/image.png"
```
