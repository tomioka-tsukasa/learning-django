# Serializerとは何か

**Serializerは「翻訳機」です**

データを**色々な形に変換**して、**ルールをチェック**する役割を持っています。

---

## Serializerの3つの主な役割

### 1️⃣ データ変換(シリアライズ): Pythonオブジェクト → JSON

```python
# モデル(Pythonオブジェクト)
user = User.objects.get(id=1)
# user.name = "太郎"
# user.email = "taro@example.com"

# Serializerで変換
serializer = UserSerializer(user)
serializer.data
# → {'name': '太郎', 'email': 'taro@example.com'}  ← JSON形式

# APIのレスポンスとして返せる!
return Response(serializer.data)
```

**なぜ必要?**
- Pythonのオブジェクトはそのままブラウザに送れない
- JSON形式に変換する必要がある
- Serializerが自動でやってくれる!


### 2️⃣ バリデーション: 受け取ったデータが正しいかチェック

```python
# クライアントから送られてきたデータ
data = {
    'name': '',  # ← 空っぽ!
    'email': 'invalid-email'  # ← メール形式じゃない!
}

# Serializerでチェック
serializer = UserSerializer(data=data)
if serializer.is_valid():
    print("OK!")
else:
    print(serializer.errors)
    # → {'name': ['この項目は必須です'],
    #     'email': ['正しいメールアドレスを入力してください']}
```

**なぜ必要?**
- ユーザーが変なデータを送ってくるかもしれない
- データベースに保存する前にチェックしたい
- Serializerがルールに沿ってチェックしてくれる!


### 3️⃣ データ保存: バリデーション済みのデータをDBに保存

```python
# データ受け取り
data = {'name': '太郎', 'email': 'taro@example.com'}

# バリデーション
serializer = UserSerializer(data=data)
if serializer.is_valid():
    # 保存!
    user = serializer.save()  # ← これでDBに保存される
    # User.objects.create(name='太郎', email='taro@example.com') と同じ
```

**なぜ必要?**
- バリデーション済みのデータを簡単に保存できる
- わざわざ `Model.objects.create()` を書かなくていい
- Serializerが自動でやってくれる!

---

## 具体例で理解しよう

### 準備: モデルとSerializerの定義

```python
# models.py
class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    age = models.IntegerField()

# serializers.py
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'age']

    # カスタムバリデーション
    def validate_age(self, value):
        if value < 18:
            raise serializers.ValidationError("18歳以上でないと登録できません")
        return value
```

---

### シナリオ1: バリデーション + DB保存(ユーザー登録)

データをチェックして、問題なければDBに保存する **一番よく使うパターン**

```python
# views.py
@api_view(['POST'])
def register_user(request):
    """
    ユーザーデータをバリデーションして、問題なければDBに保存
    """
    # クライアントからのリクエスト
    # POST /api/register_user
    # Body: {"name": "太郎", "email": "taro@example.com", "age": 20}

    # ① バリデーション
    serializer = UserSerializer(data=request.data)

    if serializer.is_valid():
        # ② DB保存
        user = serializer.save()  # ← ここでDBに保存される!
        # 内部的に User.objects.create(name='太郎', email='taro@example.com', age=20) が実行される

        print(f"保存されたユーザー: ID={user.id}, Name={user.name}")
        # → 保存されたユーザー: ID=1, Name=太郎

        # ③ 保存成功レスポンス
        return Response({
            'status': 'success',
            'message': 'ユーザーを登録しました',
            'user': serializer.data  # 保存したデータをJSON形式で返す
        }, status=201)  # 201 = Created
    else:
        # バリデーション失敗 → DB保存はしない
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=400)
```

**実行例:**

```python
# 成功時
# リクエスト: {"name": "太郎", "email": "taro@example.com", "age": 20}
# レスポンス:
{
    "status": "success",
    "message": "ユーザーを登録しました",
    "user": {
        "id": 1,
        "name": "太郎",
        "email": "taro@example.com",
        "age": 20
    }
}
# → DBに保存される! ✅

# 失敗時
# リクエスト: {"name": "", "email": "invalid", "age": 15}
# レスポンス:
{
    "status": "error",
    "errors": {
        "name": ["この項目は必須です"],
        "email": ["正しいメールアドレスを入力してください"],
        "age": ["18歳以上でないと登録できません"]
    }
}
# → DBには保存されない! ❌
```

---

### シナリオ2: DBから取得したデータをJSON形式で返す

既にDBに保存されているデータを取得して返す場合

```python
# views.py
@api_view(['GET'])
def get_user(request, user_id):
    """
    指定されたIDのユーザー情報を取得
    """
    # GET /api/users/1

    try:
        # ① DBからユーザーを取得
        user = User.objects.get(id=user_id)
        # user.name = "太郎"
        # user.email = "taro@example.com"
        # user.age = 20

        # ② Pythonオブジェクト → JSON形式に変換
        serializer = UserSerializer(user)

        # ③ JSON形式で返す
        return Response(serializer.data, status=200)
        # レスポンス:
        # {
        #     "id": 1,
        #     "name": "太郎",
        #     "email": "taro@example.com",
        #     "age": 20
        # }

    except User.DoesNotExist:
        return Response({
            'error': 'ユーザーが見つかりません'
        }, status=404)
```

---

### 全体の流れ: バリデーション → DB保存 → レスポンス

```
【クライアント】
    ↓ (1) POSTリクエスト送信
    |    Body: {"name": "太郎", "email": "taro@example.com", "age": 20}
    ↓
【Django View】
    ↓ (2) request.data を受け取る
    ↓
【Serializer - バリデーション】
    ↓ (3) UserSerializer(data=request.data)
    ↓ (4) serializer.is_valid() でチェック
    |    ・name が空じゃないか?
    |    ・email が正しい形式か?
    |    ・age が 18以上か?
    ↓
    |-- ❌ バリデーション失敗
    |       → serializer.errors を返す
    |       → DB保存はしない!
    |       → status=400
    |
    |-- ✅ バリデーション成功
        ↓ (5) serializer.save() を呼ぶ
        ↓
【データベース】
        ↓ (6) User.objects.create() が実行される
        ↓ (7) DBに保存完了!
        |      id: 1
        |      name: "太郎"
        |      email: "taro@example.com"
        |      age: 20
        ↓
【Serializer - シリアライズ】
        ↓ (8) 保存したデータをPythonオブジェクト → JSON形式に変換
        ↓      serializer.data
        ↓
【Django View】
        ↓ (9) Response(serializer.data, status=201)
        ↓
【クライアント】
        ← (10) JSONレスポンス受信
             {
                 "status": "success",
                 "message": "ユーザーを登録しました",
                 "user": {
                     "id": 1,
                     "name": "太郎",
                     "email": "taro@example.com",
                     "age": 20
                 }
             }
```

---

### ポイントまとめ

| シナリオ | バリデーション | DB保存 | 用途 |
|---------|--------------|--------|-----|
| **シナリオ1** | ✅ する | ✅ する | 新規登録、データ作成(一番よく使う!) |
| **シナリオ2** | ❌ しない | - | DBから取得したデータを返すだけ |

**重要:**
- `serializer.is_valid()` → バリデーションのみ
- `serializer.save()` → DB保存(バリデーション成功後のみ)
- `serializer.data` → JSON形式のデータ

**実務では:**
- シナリオ1(バリデーション+保存)を使うのが99%
- バリデーションだけで保存しないパターンはほぼ使わない

---

## なぜSerializerを使うの?

### Serializerを使わない場合:

```python
@api_view(['POST'])
def register_user(request):
    # 全部手動で書く必要がある!
    name = request.data.get('name')
    email = request.data.get('email')
    age = request.data.get('age')

    # バリデーション(自分で書く)
    if not name:
        return Response({'error': 'nameは必須です'}, status=400)
    if '@' not in email:
        return Response({'error': 'メールアドレスが無効です'}, status=400)
    if age < 18:
        return Response({'error': '18歳以上でないと登録できません'}, status=400)

    # 保存(自分で書く)
    user = User.objects.create(name=name, email=email, age=age)

    # JSONで返す(自分で辞書を作る)
    return Response({
        'name': user.name,
        'email': user.email,
        'age': user.age
    }, status=201)
```

### Serializerを使う場合:

```python
@api_view(['POST'])
def register_user(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)
```

**めっちゃシンプル!**

---

## まとめ: Serializerは「便利な翻訳機+チェッカー+保存係」

| 役割 | 何をする? | 例 |
|-----|----------|---|
| **変換(シリアライズ)** | Pythonオブジェクト ⇔ JSON | API response |
| **バリデーション** | データが正しいかチェック | メール形式、必須項目 |
| **保存** | DBに保存する処理を簡単に | `serializer.save()` |

Serializerは**1つで3役**こなす便利なツールなんです!
