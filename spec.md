# 予約システム仕様書

> **このドキュメントは生成AIが実行時に必ず参照・更新するものです。**
> 最終更新: 2024-01-01
> バージョン: 1.0.0

---

## 1. システム概要

### 目的
店舗向け予約管理システム。店舗側の管理機能と顧客向け予約機能の2フローを提供。

### 技術スタック
| 項目 | 技術 | 理由 |
|------|------|------|
| バックエンド | Python 3.11 / FastAPI | 軽量・高速・型安全 |
| データベース | SQLite | サーバー不要・運用コスト0 |
| ORM | SQLAlchemy 2.x | Python標準的ORM |
| テンプレート | Jinja2 | FastAPI標準 |
| 認証 | セッションベース (itsdangerous) | シンプル・安全 |
| LINE通知 | LINE Messaging API | 予約確認・通知 |
| QRコード | qrcode[pil] | 予約確認用 |
| 祝日 | jpholiday | 日本祝日自動判定 |
| テスト | pytest / httpx | 非同期対応テスト |
| WSGI | Uvicorn | 軽量ASGI サーバー |

### 運用コスト
- サーバー: VPS最小構成 or Render.com 無料プラン
- DB: SQLite (ファイルベース)
- LINE: 無料プラン (月1000通まで)
- ドメイン: 任意

---

## 2. データベース設計

### テーブル一覧

#### stores (店舗)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| phone_number | VARCHAR(20) UNIQUE | ログインID |
| password_hash | VARCHAR(255) | bcryptハッシュ |
| store_name | VARCHAR(100) | 店舗名 |
| line_channel_token | TEXT | LINE Bot トークン |
| line_user_id | VARCHAR(100) | 店舗LINE ユーザーID |
| created_at | DATETIME | |

#### reservation_configs (予約設定)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| store_id | INTEGER FK | |
| slot_type | VARCHAR(20) | DAILY/HOURLY/HALFDAY |
| business_start | VARCHAR(5) | HH:MM |
| business_end | VARCHAR(5) | HH:MM |
| slot_interval_minutes | INTEGER | HOURLY時の間隔(分) |
| capacity_per_slot | INTEGER | スロットあたり最大人数 |
| box_count | INTEGER | ボックス数(席数・担当者数等) |
| box_label | VARCHAR(50) | ボックスの名称 |
| calendar_months_ahead | INTEGER | カレンダー作成月数(デフォルト3) |

#### holiday_rules (定休日ルール)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| store_id | INTEGER FK | |
| rule_type | VARCHAR(20) | WEEKLY/SPECIFIC |
| day_of_week | INTEGER | 0=月曜〜6=日曜 |
| specific_date | DATE | SPECIFIC時の日付 |
| half_day_restriction | VARCHAR(10) | NULL=終日/AM/PM |

#### calendar_slots (カレンダースロット)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| store_id | INTEGER FK | |
| slot_date | DATE | 日付 |
| slot_label | VARCHAR(50) | 表示名(10:00-11:00等) |
| slot_start | VARCHAR(5) | HH:MM |
| slot_end | VARCHAR(5) | HH:MM |
| max_capacity | INTEGER | 最大予約可能人数 |
| is_available | BOOLEAN | 予約受付可否 |
| is_holiday | BOOLEAN | 休日フラグ |
| holiday_reason | VARCHAR(100) | 休日理由 |
| override_note | TEXT | 手動変更メモ |

#### reservations (予約)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| reservation_number | VARCHAR(20) UNIQUE | 予約番号(RES-YYYYMMDD-XXXX) |
| store_id | INTEGER FK | |
| slot_id | INTEGER FK | |
| customer_name | VARCHAR(100) | 予約者名 |
| customer_phone | VARCHAR(20) | 電話番号 |
| customer_email | VARCHAR(255) | メールアドレス(任意) |
| party_size | INTEGER | 予約人数 |
| status | VARCHAR(20) | PENDING/CONFIRMED/CANCELLED |
| confirmation_token | VARCHAR(100) | LINE確認用トークン |
| line_user_id | VARCHAR(100) | |
| qr_code_path | VARCHAR(255) | QRコード画像パス |
| notes | TEXT | 備考 |
| created_at | DATETIME | |
| confirmed_at | DATETIME | |

#### system_settings (システム設定)
| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PK | |
| store_id | INTEGER FK | |
| key | VARCHAR(100) | 設定キー |
| value | TEXT | 設定値 |

---

## 3. 機能仕様

### 3.1 店舗管理フロー

#### ログイン
- URL: `/store/login`
- 電話番号 + パスワードで認証
- セッション有効期限: 24時間

#### 予約設定
- URL: `/store/setup`
- 予約タイプ選択:
  - `DAILY`: 1日単位（例: 1日10人まで）
  - `HOURLY`: 時間単位（例: 1時間ごとに2人）
  - `HALFDAY`: 午前/午後（例: 各10人）
- ボックス設定: 席数・担当者数など
- 営業時間設定
- 定休日設定

#### カレンダー生成
- URL: `/store/calendar`
- 生成範囲: 翌月〜3ヶ月後末日（設定変更可）
- 日本祝日を自動的に休日設定
- 定休日ルールを自動適用
- 手動での休日設定・人数変更可能

#### 予約状況確認
- URL: `/store/reservations`
- 日付・ステータスでフィルタリング
- 予約詳細表示

### 3.2 顧客予約フロー

#### 予約作成
1. 日付選択 (`/book/{store_id}`)
2. 時間スロット選択
3. 情報入力（名前・電話番号・メール任意）
4. 確認画面
5. 完了画面（QRコード・予約番号表示）

#### LINE通知フロー
1. 予約作成 → 仮予約(PENDING)
2. LINE仮予約通知（確認URLリンク付き）
3. 顧客がURLクリック → CONFIRMED
4. 店舗にLINE通知

---

## 4. API エンドポイント

### 認証
- `GET/POST /store/login` - ログイン
- `GET /store/logout` - ログアウト

### 店舗管理
- `GET/POST /store/setup` - 予約設定
- `GET/POST /store/holidays` - 定休日設定
- `GET /store/calendar` - カレンダー表示
- `POST /store/calendar/generate` - カレンダー生成
- `POST /store/calendar/slot/{id}` - スロット手動編集
- `GET /store/reservations` - 予約一覧

### 顧客予約
- `GET /book/{store_id}` - 日付選択
- `GET /book/{store_id}/slots/{date}` - スロット一覧
- `GET/POST /book/{store_id}/form/{slot_id}` - 予約フォーム
- `POST /book/{store_id}/confirm` - 予約確認
- `GET /book/complete/{reservation_number}` - 完了画面
- `GET /confirm/{token}` - LINE確認リンク

---

## 5. 環境変数

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./reservation.db
LINE_CHANNEL_TOKEN=your-line-channel-token
LINE_CHANNEL_SECRET=your-line-channel-secret
BASE_URL=https://your-domain.com
```

---

## 6. セットアップ手順

### 開発環境
```bash
# リポジトリクローン後
cd reservation_system
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .envを編集して設定

# DBマイグレーション（初回）
python -m app.database init

# 開発サーバー起動
uvicorn app.main:app --reload --port 8000
```

### 本番環境
```bash
# systemdサービス設定
# /etc/systemd/system/reservation.service に設定後
systemctl start reservation
systemctl enable reservation
```

---

## 7. テスト

```bash
# 全テスト実行
pytest tests/ -v

# カバレッジレポート
pytest tests/ --cov=app --cov-report=html
```

---

## 8. 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2024-01-01 | 1.0.0 | 初版作成 |

---
*このドキュメントは生成AIとの協業において自動更新されます。*
