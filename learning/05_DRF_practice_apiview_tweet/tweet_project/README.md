# Tweet API 実装タスク

## ルール

### 基本方針

- 学習目的のため、**ソースコードは自動生成しない**
- ユーザー自身がコードを書く。Claude は教える・導く役割

### 自動生成 OK

- マークダウンファイル（`.md`）
- 解説・ドキュメントファイル

### ソース参照用ファイル

ユーザーが参照するためのソースコードは以下に配置：

```
prompt/sources/
```

---

## タスク一覧

- [x] tweets アプリ作成
- [x] Tweet モデル作成
- [x] makemigrations 実行
- [x] ユーザー登録・ログイン API（Token認証）
- [ ] マイグレーション適用
- [ ] Serializer 作成（tweets/serializers.py）
- [ ] View 作成（tweets/views.py）
- [ ] Permission 作成（tweets/permissions.py）
- [ ] URL 設定
- [ ] 動作確認

---

## タスクヒント

### マイグレーション適用

```bash
python manage.py migrate
```

### Serializer 作成

- `TweetSerializer`: 一覧・詳細表示用
- `TweetCreateSerializer`: 投稿作成用（author は自動設定）

### View 作成

**TweetListCreateView** (`/api/v1/tweets/`)

| メソッド | 認証 | 説明 |
|---------|------|------|
| GET | 不要 | ツイート一覧 |
| POST | 必須 | ツイート投稿 |

**TweetDetailView** (`/api/v1/tweets/<id>/`)

| メソッド | 認証 | 説明 |
|---------|------|------|
| GET | 不要 | ツイート詳細 |
| PUT/PATCH | 必須（本人のみ） | ツイート更新 |
| DELETE | 必須（本人のみ） | ツイート削除 |

### Permission 作成

- `IsAuthorOrReadOnly`: 本人のみ編集・削除可

### URL 設定

1. `tweets/urls.py` 作成
2. `api_v1/urls.py` に tweets を追加

### 動作確認

```bash
python manage.py runserver
```

---

## API 設計メモ

- 一覧・詳細: 誰でもアクセス可
- 投稿: ログインユーザーのみ
- 更新・削除: 投稿者本人のみ
