# 予約システム仕様

## システム構成

- Backend: FastAPI
- DB: Supabase Postgres
- ORM: SQLAlchemy 2.x
- Hosting: Vercel
- Template: Jinja2
- Test: pytest / FastAPI TestClient

ローカルテストでは SQLite を使うが、本番構成は `Vercel + Supabase` を標準とする。

## 主な機能

- 店舗ログイン
- 店舗登録
- 予約設定
- 休業日設定
- カレンダー生成
- 予約一覧 / 編集 / 削除
- 顧客向け予約導線
- 予約確認トークン
- QR コード表示

## データモデル

- `stores`
- `reservation_configs`
- `holiday_rules`
- `calendar_slots`
- `reservations`
- `system_settings`

## 環境変数

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres?sslmode=require
BASE_URL=https://your-project.vercel.app
LINE_CHANNEL_TOKEN=your-line-channel-token
LINE_CHANNEL_SECRET=your-line-channel-secret
DEBUG=false
AUTO_INIT_DB=true
```

## 開発

```powershell
pip install -r requirements.txt
python run.py
```

## テスト

```powershell
pytest tests -v
```
