# レビュー対応 2025/12/23

## 確定した仕様

- バッチ処理: CloudRunJobs を使用
- バッチ間隔: 12時間ごと
- DB: `riskeyes_v2` を使用（モデル配置場所を調整）
- フォールバック: バッチ失敗時に View で更新（現在の実装を残す）
- ロック: バッチ・View 両方に LockManager を適用

---

## Devin レビュー

### [must]

- [ ] DBルーティングとマイグレーションの不整合
  - モデルを `core/models/riskeyes_v2/` に配置
  - マイグレーションファイルを再作成

- [x] トークン出力のセキュリティリスク
  - 成功メッセージのみに変更済み

### [should]

- [x] `AlarmboxClient.__init__` の `self.headers` が未使用
  - 将来の信用調査API実装で使用予定のため残す

- [x] `exceptions.py` の不要な `pass`
  - 削除済み

- [x] マイグレーションファイル名の不一致
  - 削除済み、正しい名前で再作成する

---

## チームメンバー（SoceyN）レビュー

### [should]

- [x] ロックが必要
  - `TokenService._refresh_token()` に LockManager を追加
  - バッチ vs View、View vs View の競合を防止

### [imo]

- [x] バッチ処理の追加
  - CloudRunJobs で 12時間ごとにトークン更新
  - ファイル: `core/management/commands/refresh_alarmbox_token.py`

- [x] トークンの暗号化
  - `lib/crypt.py` を使用（AES + HMAC）
  - Model に暗号化/復号メソッドを追加

### [question]

- [x] 認証情報は dev と prod で異なるか？
  - 異なる（dev用/prod用それぞれ GCP Secret Manager で管理）

---

## 対応タスク

1. [x] モデルを `core/models/riskeyes_v2/` に移動
2. [x] マイグレーションファイルを正しい名前で再作成
3. [x] `TokenService._refresh_token()` にロック追加
4. [x] バッチコマンド作成（`refresh_alarmbox_token.py`）
5. [x] README.md 更新（バッチ運用について追記）
6. [x] トークン暗号化の対応
