# DRF Serializer ガイド

## Serializer とは

データの変換を担当するコンポーネント。

```
【入力】JSON → Python → DB
【出力】DB → Python → JSON
```

---

## Serializer vs ModelSerializer

### Serializer

全てのフィールドを手動で定義する。

```python
class TweetSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    author = serializers.StringRelatedField(read_only=True)
    content = serializers.CharField(max_length=280)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        return Tweet.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.content = validated_data.get("content", instance.content)
        instance.save()
        return instance
```

### ModelSerializer

Model から自動生成。`Meta` クラスで設定。

```python
class TweetSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Tweet
        fields = ["id", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]
```

### 比較表

| | Serializer | ModelSerializer |
|---|---|---|
| フィールド定義 | 全て手動 | Model から自動生成 |
| `Meta` クラス | 不要 | 必須 |
| `create()` / `update()` | 手動実装 | 自動生成 |
| 柔軟性 | 高い | 低い |
| コード量 | 多い | 少ない |

### ユースケース

**ModelSerializer を使う**

- Model と 1:1 で対応する API
- 通常の CRUD 操作
- 素早く実装したい場合

**Serializer を使う**

- Model が存在しない（ログイン、検索クエリなど）
- 複数の Model をまたぐデータ構造
- 外部 API のレスポンスを整形
- Model と異なるバリデーションルールが必要
- 細かい制御が必要な場合

#### Serializer ユースケース詳細

**1. Model が存在しない（ログイン）**

DB に保存しない。認証して結果を返すだけ。

```python
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["username"],
            password=attrs["password"]
        )
        if not user:
            raise serializers.ValidationError("認証失敗")
        attrs["user"] = user
        return attrs
```

**2. Model が存在しない（検索クエリ）**

検索条件を受け取るだけ。DB には保存しない。

```python
class TweetSearchSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True)
    author = serializers.CharField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to"):
            if attrs["date_from"] > attrs["date_to"]:
                raise serializers.ValidationError("日付範囲が不正です")
        return attrs
```

**3. 複数の Model をまたぐデータ構造**

ダッシュボード API など、複数 Model を1つのレスポンスにまとめる。

```python
class DashboardSerializer(serializers.Serializer):
    user_count = serializers.IntegerField()
    tweet_count = serializers.IntegerField()
    recent_tweets = TweetSerializer(many=True)
    popular_users = UserSerializer(many=True)

# View での使用例
data = {
    "user_count": User.objects.count(),
    "tweet_count": Tweet.objects.count(),
    "recent_tweets": Tweet.objects.all()[:5],
    "popular_users": User.objects.annotate(...).order_by(...)[:5],
}
serializer = DashboardSerializer(data)
```

**4. 外部 API のレスポンスを整形**

外部 API から取得したデータを自分の API 形式に変換。

```python
class WeatherSerializer(serializers.Serializer):
    """外部天気APIのレスポンスを整形"""
    city = serializers.CharField()
    temperature = serializers.FloatField()
    description = serializers.CharField()

# 外部APIのレスポンス（形式が異なる）
external_data = {
    "name": "Tokyo",
    "main": {"temp": 20.5},
    "weather": [{"description": "sunny"}]
}

# 自分の形式に変換
formatted = {
    "city": external_data["name"],
    "temperature": external_data["main"]["temp"],
    "description": external_data["weather"][0]["description"],
}
serializer = WeatherSerializer(formatted)
```

**5. Model と異なるバリデーションルールが必要**

パスワード変更など、Model のフィールドと異なる入力が必要な場合。

```python
class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("現在のパスワードが違います")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("新しいパスワードが一致しません")
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
```

---

## ModelSerializer の構造

### クラス直下のプロパティ

フィールドの挙動をカスタマイズする。

```python
class TweetSerializer(serializers.ModelSerializer):
    # デフォルト: author は ID（数値）で出力
    # カスタム: __str__ の値（ユーザー名）で出力
    author = serializers.StringRelatedField(read_only=True)
```

| 定義方法 | 出力結果 |
|---------|---------|
| 定義なし（デフォルト） | `"author": 1` |
| `StringRelatedField` | `"author": "taro"` |

### Meta クラス

Serializer 全体の設定をまとめる。

```python
class Meta:
    model = Tweet
    fields = ["id", "author", "content", "created_at", "updated_at"]
    read_only_fields = ["id", "author", "created_at", "updated_at"]
```

**`fields`**: 扱うフィールドを明示的に指定（必須）

- Model を継承しても自動で全公開されない
- セキュリティ上の設計（意図しない情報漏洩を防ぐ）
- `fields = "__all__"` は非推奨

**`read_only_fields`**: 読み取り専用フィールド

- 出力時: 値を返す
- 入力時: 無視する

---

## Serializer の分け方

### 分割の基準

View はリソース（URL）で分けるが、Serializer は **データの流れ** で分ける。

| Serializer | 方向 | 役割 |
|------------|------|------|
| ReadSerializer | DB → 出力 | 何を返すか |
| CreateSerializer | 入力 → DB | 何を受け取るか |
| UpdateSerializer | 入力 → DB | 何を更新できるか |

### 例：Tweet

**作成時（入力）**

```json
{ "content": "Hello" }
```

**取得時（出力）**

```json
{
  "id": 1,
  "author": "taro",
  "content": "Hello",
  "created_at": "2025-12-15T10:00:00Z",
  "updated_at": "2025-12-15T10:00:00Z"
}
```

### 分ける場合

```python
class TweetSerializer(serializers.ModelSerializer):
    """出力用"""
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Tweet
        fields = ["id", "author", "content", "created_at", "updated_at"]


class TweetCreateSerializer(serializers.ModelSerializer):
    """入力用"""
    class Meta:
        model = Tweet
        fields = ["content"]

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
```

### 1つにまとめる場合

```python
class TweetSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Tweet
        fields = ["id", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
```

### 分けるべきケース

- 入力と出力でフィールドが大きく異なる
- 作成と更新でバリデーションルールが異なる
- 役割を明示的に分けたい
- ネストした関連データの扱いが入出力で異なる

### まとめてよいケース

- シンプルな CRUD で入出力の差が小さい
- `read_only_fields` で十分対応できる
