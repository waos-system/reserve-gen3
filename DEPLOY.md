# Deploy

このアプリは本番を `Vercel + Supabase (Postgres)`、ローカル開発を `.env.local + Supabase` とする。

## Environment Policy

- Local: `.env.local` を使用する
- Production: Vercel の Environment Variables を使用する
- 優先順位: `Vercel の環境変数 > .env.local > .env`

`app/database.py` で `postgres://` / `postgresql://` を `postgresql+psycopg://` に正規化するため、Supabase の接続文字列はそのまま設定してよい。

## Architecture

- App: FastAPI on Vercel Serverless Functions
- DB: Supabase Postgres
- ORM: SQLAlchemy 2.x
- Session: Starlette `SessionMiddleware`

## Local Setup

### 1. Supabase project を作成

1. Supabase で project を作成する
2. `Project Settings -> Database` から接続文字列を取得する
3. DB パスワードと project ref を控える

### 2. `.env.local` を作成

`.env.local` を以下の内容で作成する。

```env
SECRET_KEY=your-random-secret
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres?sslmode=require
BASE_URL=http://localhost:8000
LINE_CHANNEL_TOKEN=
LINE_CHANNEL_SECRET=
DEBUG=true
AUTO_INIT_DB=true
```

補足:

- ローカル実行時は `BASE_URL=http://localhost:8000`
- `AUTO_INIT_DB=true` にしておくと初回起動時にテーブルを自動作成する
- `.env.local` は `.gitignore` に入っているためコミットされない

### 3. 依存関係をインストール

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. アプリを起動

```powershell
python run.py
```

または

```powershell
uvicorn app.main:app --reload --port 8000
```

### 5. 初期データを入れる場合

```powershell
python seed_data.py
```

### 6. 動作確認

- App: `http://localhost:8000`
- Login: `http://localhost:8000/store/login`
- Health check: `http://localhost:8000/health`

確認ポイント:

- Supabase 側に `stores`, `reservation_configs`, `calendar_slots`, `reservations` などのテーブルが作成される
- ローカル画面からログイン、設定、カレンダー生成、予約作成ができる

## Vercel Production Setup

Vercel には `.env.local` を使わず、Environment Variables を直接設定する。

### Required env vars

```env
SECRET_KEY=your-random-secret
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres?sslmode=require
BASE_URL=https://your-project.vercel.app
LINE_CHANNEL_TOKEN=your-line-channel-access-token
LINE_CHANNEL_SECRET=your-line-channel-secret
DEBUG=false
AUTO_INIT_DB=true
```

### Deploy steps

1. このリポジトリを Vercel に接続する
2. Framework Preset は `Other` のままでよい
3. Python runtime で `api/index.py` がエントリポイントとして使用される
4. 上記の環境変数を Vercel に設定する
5. デプロイする

`vercel.json` はすべてのリクエストを `api/index.py` にルーティングする。

本番でマイグレーション管理を導入する場合は、将来的に Alembic を追加して `AUTO_INIT_DB=false` に切り替える。

## Test

```powershell
pytest tests -v
```
