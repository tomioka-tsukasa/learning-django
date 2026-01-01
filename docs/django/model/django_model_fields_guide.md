# Django モデルフィールド完全ガイド

## 目次

1. [モデルの基本構造](#モデルの基本構造)
2. [ForeignKey（外部キー）](#foreignkey外部キー)
3. [フィールドの共通オプション](#フィールドの共通オプション)
4. [日時フィールドの特殊オプション](#日時フィールドの特殊オプション)
5. [Meta クラス](#meta-クラス)
6. [主要なフィールドタイプ](#主要なフィールドタイプ)

---

## モデルの基本構造

```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Tweet(models.Model):
    """ツイートモデル"""

    # フィールド定義
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)

    # メタ情報
    class Meta:
        ordering = ['-created_at']

    # 文字列表現
    def __str__(self):
        return self.content[:20]
```

---

## ForeignKey（外部キー）

### 基本的な使い方

```python
author = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='tweets',
    verbose_name='投稿者'
)
```

---

### `on_delete` - 関連オブジェクト削除時の動作

**ユーザーが削除されたとき、そのユーザーのツイートをどうするか？**

#### `CASCADE` - カスケード削除（推奨）

```python
on_delete=models.CASCADE
```

**動作:**
```python
user = User.objects.get(username='taro')
user.delete()  # ユーザー削除

# → taro のツイート全て自動削除される
```

**用途:**
- 親子関係が強い場合
- 例: ユーザーとツイート、注文と注文明細

---

#### `PROTECT` - 削除を防ぐ

```python
on_delete=models.PROTECT
```

**動作:**
```python
user = User.objects.get(username='taro')
user.delete()  # エラー！

# ProtectedError: Cannot delete some instances because they are referenced
# → 先にツイートを削除しないとユーザーを削除できない
```

**用途:**
- 重要なデータを守りたい
- 例: カテゴリと商品

---

#### `SET_NULL` - NULL にする

```python
author = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True  # null=True が必須
)
```

**動作:**
```python
user.delete()  # ユーザー削除
# → ツイートは残るが、author が NULL になる
```

**用途:**
- データは残したいが、関連を切りたい
- 例: 投稿と削除済みユーザー（「削除されたユーザー」として表示）

---

#### `SET_DEFAULT` - デフォルト値にする

```python
author = models.ForeignKey(
    User,
    on_delete=models.SET_DEFAULT,
    default=1  # default が必須
)
```

**動作:**
```python
user.delete()
# → author が default のユーザー（id=1）になる
```

**用途:**
- 「匿名ユーザー」や「システムユーザー」を用意しておく

---

#### `SET()` - カスタム関数で設定

```python
def get_anonymous_user():
    return User.objects.get(username='anonymous')

author = models.ForeignKey(
    User,
    on_delete=models.SET(get_anonymous_user)
)
```

**動作:**
```python
user.delete()
# → author が関数の戻り値（匿名ユーザー）になる
```

---

#### `DO_NOTHING` - 何もしない（非推奨）

```python
on_delete=models.DO_NOTHING
```

**動作:**
```python
user.delete()
# → ツイートの author_id はそのまま
# → 存在しないユーザーIDを参照（整合性エラー）
```

**用途:** ほぼない（データベース整合性が壊れる）

---

### `on_delete` の選び方フローチャート

```
削除時にどうする？
│
├─ 子データも一緒に削除していい
│  └─> CASCADE
│
├─ 親データの削除を防ぎたい
│  └─> PROTECT
│
├─ 子データは残すが関連を切りたい
│  ├─ NULL にする
│  │  └─> SET_NULL
│  └─ デフォルト値にする
│     └─> SET_DEFAULT
│
└─ カスタム処理
   └─> SET(function)
```

---

### `related_name` - 逆参照の名前

**ユーザーからツイートにアクセスする際の属性名**

```python
author = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='tweets'  # ← これ
)
```

#### 使用例

```python
# ツイート → ユーザー（順方向）
tweet = Tweet.objects.get(id=1)
user = tweet.author  # ForeignKey で定義した名前

# ユーザー → ツイート（逆方向）
user = User.objects.get(username='taro')
tweets = user.tweets.all()  # related_name で定義した名前
```

#### `related_name` がない場合

```python
author = models.ForeignKey(User, on_delete=models.CASCADE)
# related_name を指定しない場合
```

**デフォルト:** `モデル名_set`

```python
user = User.objects.get(username='taro')
tweets = user.tweet_set.all()  # ← tweet_set（自動生成）
```

#### 命名規則

```python
# 単数形のモデル → 複数形の related_name
class Tweet(models.Model):
    author = models.ForeignKey(User, related_name='tweets')  # 複数形

class Comment(models.Model):
    tweet = models.ForeignKey(Tweet, related_name='comments')  # 複数形
```

#### `related_name='+'` - 逆参照を無効化

```python
author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
```

**用途:**
```python
# user.tweets はアクセスできない（エラー）
# 逆参照が不要な場合に使う
```

---

### `verbose_name` - 人間が読める名前

**管理画面やフォームで表示される名前**

```python
author = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    verbose_name='投稿者'  # ← 日本語名
)
content = models.TextField(verbose_name='内容')
```

#### 管理画面での表示

```
Tweetの追加

投稿者: [選択]
内容:   [テキストエリア]
```

`verbose_name` がないと英語のフィールド名が表示されます：

```
Add Tweet

Author:  [選択]
Content: [テキストエリア]
```

---

## フィールドの共通オプション

### `null` - データベースでNULLを許可

```python
email = models.EmailField(null=True)
```

**意味:** データベースのカラムで NULL 値を許可

```sql
-- データベース
email VARCHAR(254) NULL
```

**使用例:**
```python
user = User(username='taro')  # email は指定しない
user.save()  # OK（email は NULL）
```

**注意:**
- 文字列フィールド（CharField, TextField）では `blank=True` を使う
- `null=True` は主に数値、日付、外部キーで使う

---

### `blank` - フォームで空欄を許可

```python
email = models.EmailField(blank=True)
```

**意味:** Django のフォームやバリデーションで空欄を許可

**使用例:**
```python
# フォームで email を入力しない
form = UserForm({'username': 'taro'})  # email なし
form.is_valid()  # OK（blank=True なので）
```

**`null` と `blank` の違い:**

| オプション | 対象 | 意味 |
|-----------|------|------|
| `null=True` | データベース | NULL値を許可 |
| `blank=True` | フォーム/バリデーション | 空欄を許可 |

**組み合わせ例:**

```python
# 文字列フィールド（推奨）
bio = models.TextField(blank=True, default='')  # NULL ではなく空文字

# 数値フィールド
age = models.IntegerField(null=True, blank=True)  # NULL 許可

# 外部キー
category = models.ForeignKey(
    Category,
    on_delete=models.SET_NULL,
    null=True,  # 必須
    blank=True  # フォームで選択しなくてもOK
)
```

---

### `default` - デフォルト値

```python
is_active = models.BooleanField(default=True)
status = models.CharField(max_length=20, default='draft')
```

**動作:**
```python
user = User(username='taro')
# is_active は指定しない
user.save()
print(user.is_active)  # True（default値）
```

**注意:** 関数を渡す場合

```python
# ❌ 間違い
created_at = models.DateTimeField(default=datetime.now())
# → モデル定義時の時刻で固定される

# ✅ 正解
created_at = models.DateTimeField(default=datetime.now)
# → オブジェクト作成時に関数が呼ばれる
```

---

### `unique` - 一意性制約

```python
email = models.EmailField(unique=True)
```

**意味:** 同じ値の重複を許さない

```python
User.objects.create(email='taro@example.com')
User.objects.create(email='taro@example.com')  # エラー！
# IntegrityError: UNIQUE constraint failed
```

**データベース:**
```sql
email VARCHAR(254) UNIQUE
```

---

### `choices` - 選択肢を制限

```python
class Tweet(models.Model):
    STATUS_CHOICES = [
        ('draft', '下書き'),
        ('published', '公開'),
        ('archived', 'アーカイブ'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
```

**使用例:**
```python
tweet = Tweet.objects.create(content='Hello', status='published')
print(tweet.status)  # 'published'
print(tweet.get_status_display())  # '公開'（日本語）
```

**Python 3.10+ なら Enum を使える:**

```python
from django.db import models

class TweetStatus(models.TextChoices):
    DRAFT = 'draft', '下書き'
    PUBLISHED = 'published', '公開'
    ARCHIVED = 'archived', 'アーカイブ'

class Tweet(models.Model):
    status = models.CharField(
        max_length=20,
        choices=TweetStatus.choices,
        default=TweetStatus.DRAFT
    )
```

---

### `db_index` - インデックス作成

```python
username = models.CharField(max_length=150, db_index=True)
```

**意味:** 検索を高速化するためのインデックスを作成

**用途:**
- 頻繁に検索されるフィールド
- `filter()`, `get()` で使われるフィールド

```python
# username で検索することが多い
User.objects.filter(username='taro')  # 高速化
```

**注意:** むやみに付けるとデータ挿入が遅くなる

---

### `help_text` - 説明文

```python
content = models.TextField(
    max_length=280,
    help_text='280文字以内で入力してください'
)
```

**管理画面での表示:**
```
内容: [テキストエリア]
      280文字以内で入力してください  ← help_text
```

---

## 日時フィールドの特殊オプション

### `auto_now_add` - 作成時のみ自動設定

```python
created_at = models.DateTimeField(auto_now_add=True)
```

**動作:**
```python
tweet = Tweet.objects.create(content='Hello')
print(tweet.created_at)  # 2025-12-14 10:30:00（自動設定）

# 後から変更しても無視される
tweet.created_at = datetime(2020, 1, 1)
tweet.save()
print(tweet.created_at)  # 2025-12-14 10:30:00（変わらない）
```

**用途:** 作成日時

---

### `auto_now` - 更新時に毎回自動設定

```python
updated_at = models.DateTimeField(auto_now=True)
```

**動作:**
```python
tweet = Tweet.objects.create(content='Hello')
print(tweet.updated_at)  # 2025-12-14 10:30:00

# 更新すると自動で現在時刻になる
tweet.content = 'Updated'
tweet.save()
print(tweet.updated_at)  # 2025-12-14 11:00:00（自動更新）
```

**用途:** 更新日時

---

### `auto_now_add` と `auto_now` の違い

| オプション | タイミング | 用途 |
|-----------|-----------|------|
| `auto_now_add=True` | 作成時のみ | 作成日時 |
| `auto_now=True` | 更新時も毎回 | 更新日時 |

**典型的な組み合わせ:**

```python
class Tweet(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)  # 作成日時
    updated_at = models.DateTimeField(auto_now=True)      # 更新日時
```

---

### 注意点

**`default` と併用できない:**

```python
# ❌ エラー
created_at = models.DateTimeField(auto_now_add=True, default=datetime.now)

# ✅ どちらか一方
created_at = models.DateTimeField(auto_now_add=True)
# または
created_at = models.DateTimeField(default=datetime.now)
```

---

## Meta クラス

### `ordering` - デフォルトの並び順

```python
class Meta:
    ordering = ['-created_at']  # 新しい順
```

**効果:**
```python
# 明示的にorder_byしなくても並び順が適用される
Tweet.objects.all()  # 自動で新しい順
```

**複数条件:**
```python
ordering = ['-created_at', 'id']  # 作成日時降順 → ID昇順
```

**昇順・降順:**
```python
ordering = ['created_at']   # 昇順（古い順）
ordering = ['-created_at']  # 降順（新しい順）
```

---

### `verbose_name` / `verbose_name_plural` - モデルの表示名

```python
class Meta:
    verbose_name = 'ツイート'
    verbose_name_plural = 'ツイート'
```

**管理画面での表示:**
```
ツイート（複数形）
├─ ツイートを追加
└─ ツイート一覧
```

指定しない場合：
```
Tweets  ← 英語のまま
```

---

### `db_table` - テーブル名を指定

```python
class Meta:
    db_table = 'custom_tweets'
```

**デフォルト:** `アプリ名_モデル名`
```
tweets_tweet
```

**カスタム:**
```
custom_tweets
```

---

### `unique_together` - 複数フィールドの組み合わせで一意

```python
class Meta:
    unique_together = [['user', 'tweet']]
```

**意味:** 同じユーザーが同じツイートに2回いいねできない

```python
Like.objects.create(user=user1, tweet=tweet1)  # OK
Like.objects.create(user=user1, tweet=tweet1)  # エラー！
```

**Django 4.0+ では `constraints` 推奨:**

```python
from django.db import models

class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['user', 'tweet'],
            name='unique_user_tweet'
        )
    ]
```

---

### `indexes` - インデックス定義

```python
class Meta:
    indexes = [
        models.Index(fields=['author', '-created_at']),
    ]
```

**用途:** 複合インデックスで検索高速化

```python
# author と created_at で絞り込む検索が速くなる
Tweet.objects.filter(author=user, created_at__gte=date)
```

---

## 主要なフィールドタイプ

### 文字列フィールド

#### `CharField` - 短い文字列

```python
username = models.CharField(max_length=150)
```

**用途:** ユーザー名、タイトル、ステータス

**データベース:** `VARCHAR(150)`

---

#### `TextField` - 長い文字列

```python
content = models.TextField()
bio = models.TextField(max_length=500)  # 最大文字数を推奨
```

**用途:** 本文、説明文

**データベース:** `TEXT`

---

#### `EmailField` - メールアドレス

```python
email = models.EmailField()
```

**バリデーション:** メール形式チェック

**データベース:** `VARCHAR(254)`

---

#### `URLField` - URL

```python
website = models.URLField()
```

**バリデーション:** URL形式チェック

---

#### `SlugField` - URL用文字列

```python
slug = models.SlugField(unique=True)
```

**用途:** URL の一部（`/posts/my-first-post/`）

**許可文字:** 英数字、ハイフン、アンダースコア

---

### 数値フィールド

#### `IntegerField` - 整数

```python
age = models.IntegerField()
view_count = models.IntegerField(default=0)
```

**範囲:** -2147483648 〜 2147483647

---

#### `PositiveIntegerField` - 正の整数

```python
likes_count = models.PositiveIntegerField(default=0)
```

**範囲:** 0 〜 2147483647

---

#### `FloatField` - 浮動小数点数

```python
rating = models.FloatField()
```

**用途:** 評価値、割合

---

#### `DecimalField` - 固定小数点数

```python
price = models.DecimalField(max_digits=10, decimal_places=2)
```

**用途:** 金額（`9999.99` など）

**必須オプション:**
- `max_digits`: 全体の桁数
- `decimal_places`: 小数点以下の桁数

---

### 日時フィールド

#### `DateTimeField` - 日時

```python
created_at = models.DateTimeField(auto_now_add=True)
published_at = models.DateTimeField(null=True, blank=True)
```

**データベース:** `DATETIME`

---

#### `DateField` - 日付

```python
birth_date = models.DateField()
```

**データベース:** `DATE`

---

#### `TimeField` - 時刻

```python
meeting_time = models.TimeField()
```

**データベース:** `TIME`

---

### 真偽値フィールド

#### `BooleanField` - 真偽値

```python
is_active = models.BooleanField(default=True)
is_published = models.BooleanField(default=False)
```

**データベース:** `BOOLEAN`

---

### ファイルフィールド

#### `FileField` - ファイル

```python
document = models.FileField(upload_to='documents/')
```

**`upload_to`:** アップロード先ディレクトリ

---

#### `ImageField` - 画像

```python
avatar = models.ImageField(upload_to='avatars/')
```

**バリデーション:** 画像ファイルかチェック

**必要:** `Pillow` ライブラリ

```bash
pip install Pillow
```

---

### リレーションフィールド

#### `ForeignKey` - 多対一

```python
author = models.ForeignKey(User, on_delete=models.CASCADE)
```

**用途:** ツイートと投稿者（1ユーザー → 複数ツイート）

---

#### `ManyToManyField` - 多対多

```python
tags = models.ManyToManyField(Tag)
```

**用途:** ツイートとタグ（1ツイート → 複数タグ、1タグ → 複数ツイート）

---

#### `OneToOneField` - 一対一

```python
profile = models.OneToOneField(Profile, on_delete=models.CASCADE)
```

**用途:** ユーザーとプロフィール（1ユーザー → 1プロフィール）

---

## まとめ

### よく使うパターン

#### 作成・更新日時

```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

---

#### 外部キー

```python
author = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='tweets'
)
```

---

#### オプショナルな文字列

```python
bio = models.TextField(blank=True, default='')
```

---

#### オプショナルな外部キー

```python
category = models.ForeignKey(
    Category,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)
```

---

#### 選択肢

```python
STATUS_CHOICES = [
    ('draft', '下書き'),
    ('published', '公開'),
]
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
```

---

これでDjangoモデルの主要な機能は網羅できます！
