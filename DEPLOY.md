# 本番環境 構築手順書

> 対象システム: 予約管理システム (FastAPI + SQLite)
> 最終更新: 2026-03-19

---

## 目次

1. [構成の選択](#1-構成の選択)
2. [Render.com（無料・最も簡単）](#2-rendercom無料最も簡単)
3. [VPS（さくらVPS / ConoHa / Vultr）](#3-vpsさくらvps--conoha--vultr)
4. [独自ドメインとSSL](#4-独自ドメインとssl)
5. [LINE Messaging API 設定](#5-line-messaging-api-設定)
6. [本番用 .env 設定](#6-本番用-env-設定)
7. [バックアップ設定](#7-バックアップ設定)
8. [障害対応チェックリスト](#8-障害対応チェックリスト)

---

## 1. 構成の選択

| 方式 | 月額コスト | 難易度 | 推奨ケース |
|------|-----------|--------|-----------|
| **Render.com 無料** | 0円 | ★☆☆ | 試験運用・小規模 |
| **Render.com 有料** | 約1,500円 | ★☆☆ | 安定運用したい |
| **VPS (最小構成)** | 500〜1,000円 | ★★☆ | 長期・カスタマイズしたい |
| **VPS (標準構成)** | 1,000〜2,000円 | ★★★ | 複数店舗・本格運用 |

**無料プランの注意点:** Render.com 無料プランはアクセスがないと15分でスリープします。
最初のアクセスに30〜60秒かかります。有料プラン（$7/月≒約1,050円）で常時起動になります。

---

## 2. Render.com（無料・最も簡単）

### 2-1. GitHubにコードをアップロード

```bash
# GitHubアカウントを作成後、新しいリポジトリを作成

# ローカルで実行（reservation_system フォルダ内）
cd reservation_system
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/あなたのユーザー名/reservation-system.git
git push -u origin main
```

### 2-2. Render.com でデプロイ

1. https://render.com にアクセスして無料アカウント作成
2. ダッシュボードで **「New +」→「Web Service」** をクリック
3. GitHubリポジトリを選択して接続
4. 以下の設定を入力：

| 項目 | 設定値 |
|------|--------|
| Name | reservation-system（任意） |
| Region | Singapore（日本に最も近い） |
| Branch | main |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free（無料）|

5. **「Environment Variables」** に以下を追加：

```
SECRET_KEY         = （ランダムな32文字以上の文字列）
DATABASE_URL       = sqlite:///./reservation.db
BASE_URL           = https://あなたのサービス名.onrender.com
LINE_CHANNEL_TOKEN = （LINEのトークン、後で設定可）
LINE_CHANNEL_SECRET= （LINEのシークレット、後で設定可）
DEBUG              = false
```

6. **「Create Web Service」** をクリック → 3〜5分でデプロイ完了

### 2-3. 初期データ作成

デプロイ完了後、Render.com の **「Shell」タブ** で実行：

```bash
python seed_data.py
```

### 2-4. Render.com の永続ディスク設定（重要）

無料プランはデプロイのたびにDBが消えます。永続化するには：

1. Render.com ダッシュボード → サービスを選択
2. **「Disks」** タブ → **「Add a Disk」**
3. 設定：
   - Mount Path: `/data`
   - Size: 1 GB（無料）
4. `.env` の DATABASE_URL を変更：
   ```
   DATABASE_URL = sqlite:////data/reservation.db
   ```
5. 再デプロイ後に `python seed_data.py` を再実行

---

## 3. VPS（さくらVPS / ConoHa / Vultr）

**推奨スペック:** CPU 1コア / メモリ 1GB / SSD 25GB / 月額500〜1,000円

- さくらVPS: https://vps.sakura.ad.jp （月額643円〜）
- ConoHa VPS: https://www.conoha.jp （月額880円〜）
- Vultr: https://www.vultr.com （月額$6〜、カード必要）

### 3-1. サーバーの初期設定

```bash
# ローカルからSSH接続（IPアドレスはVPSの管理画面で確認）
ssh root@123.456.789.000

# システム更新
apt update && apt upgrade -y

# 必要なパッケージインストール
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx ufw

# ファイアウォール設定
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable

# アプリ用ユーザーを作成（rootで動かさない）
adduser --system --group --home /var/www/reservation appuser
```

### 3-2. アプリケーションのデプロイ

```bash
# アプリフォルダを作成
mkdir -p /var/www/reservation
cd /var/www/reservation

# GitHubからクローン（またはSFTPでファイルをアップロード）
git clone https://github.com/あなたのユーザー名/reservation-system.git .

# 仮想環境を作成してパッケージインストール
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .envファイルを作成
cp .env.example .env
nano .env   # 下記「本番用 .env 設定」を参照して編集

# 初期データ作成
python seed_data.py

# フォルダの所有者をappuserに変更
chown -R appuser:appuser /var/www/reservation
```

### 3-3. systemd サービス設定（自動起動）

```bash
# サービスファイルを作成
nano /etc/systemd/system/reservation.service
```

以下の内容を貼り付け：

```ini
[Unit]
Description=予約システム FastAPI
After=network.target

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/var/www/reservation
Environment="PATH=/var/www/reservation/venv/bin"
EnvironmentFile=/var/www/reservation/.env
ExecStart=/var/www/reservation/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# サービスを有効化・起動
systemctl daemon-reload
systemctl enable reservation
systemctl start reservation

# 起動確認
systemctl status reservation
# ● reservation.service - 予約システム FastAPI
#    Active: active (running) ← これが表示されればOK
```

### 3-4. Nginx リバースプロキシ設定

```bash
nano /etc/nginx/sites-available/reservation
```

以下の内容を貼り付け（ドメイン名を変更）：

```nginx
server {
    listen 80;
    server_name あなたのドメイン.com;   # ← ドメイン名に変更

    # ファイルサイズ上限（QRコード画像など）
    client_max_body_size 10M;

    # アクセスログ
    access_log /var/log/nginx/reservation_access.log;
    error_log  /var/log/nginx/reservation_error.log;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_redirect     off;

        # タイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;
    }

    # 静的ファイルはNginxが直接配信（高速化）
    location /static/ {
        alias /var/www/reservation/app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# 設定を有効化
ln -s /etc/nginx/sites-available/reservation /etc/nginx/sites-enabled/
nginx -t      # 設定チェック（successful が出ればOK）
systemctl restart nginx
```

---

## 4. 独自ドメインとSSL

### 4-1. ドメイン取得（任意）

- お名前.com: https://www.onamae.com（.com で年間1,500円程度）
- ムームードメイン: https://muumuu-domain.com
- Cloudflare: https://www.cloudflare.com/products/registrar（最安値）

### 4-2. DNSレコード設定

ドメインのDNS管理画面で以下を設定：

| タイプ | ホスト名 | 値 | TTL |
|--------|---------|-----|-----|
| A | @ | VPSのIPアドレス | 3600 |
| A | www | VPSのIPアドレス | 3600 |

変更反映まで最大24〜48時間かかります。

### 4-3. SSL証明書の取得（無料・Let's Encrypt）

```bash
# SSL証明書を取得（ドメイン名を変更）
certbot --nginx -d あなたのドメイン.com -d www.あなたのドメイン.com

# メールアドレスを入力 → 利用規約に同意（A） → ニュースレター（N）

# 自動更新の確認（certbotが自動設定するが念のため確認）
certbot renew --dry-run
# Congratulations, all simulated renewals succeeded. が出ればOK
```

Certbot が自動でNginx設定を書き換えてhttpsにリダイレクトします。

### 4-4. .env の BASE_URL を更新

```bash
nano /var/www/reservation/.env
# BASE_URL=https://あなたのドメイン.com に変更

# アプリを再起動
systemctl restart reservation
```

---

## 5. LINE Messaging API 設定

予約確定通知・QRコード送付に使用します。（設定しなくてもシステムは動作します）

### 5-1. LINE Developersでチャンネル作成

1. https://developers.line.biz にアクセスしてログイン
2. **「プロバイダー作成」** → 名前を入力（例: 予約システム）
3. **「チャンネル作成」→「Messaging API」** を選択
4. 入力項目：
   - チャンネル名: 例「○○予約」
   - チャンネル説明: 任意
   - 大業種・小業種: 適切なものを選択
5. 作成後、**「Messaging API 設定」タブ** へ

### 5-2. トークンとシークレットの取得

| 取得場所 | 値 |
|---------|-----|
| 「基本設定」タブ → チャンネルシークレット | `LINE_CHANNEL_SECRET` に設定 |
| 「Messaging API設定」タブ → チャンネルアクセストークン（長期）→「発行」 | `LINE_CHANNEL_TOKEN` に設定 |

### 5-3. Webhook設定

1. 「Messaging API設定」→ Webhook URL に入力：
   ```
   https://あなたのドメイン.com/line/webhook
   ```
2. 「Webhookの利用」をオン
3. 「検証」ボタンで接続確認

### 5-4. 店舗のLINEユーザーIDを確認

店舗側に通知を送るには、店舗担当者のLINEユーザーIDが必要です。

1. 担当者が上記Botを友達追加
2. 友達追加後にLINEのメッセージを1回送信
3. Webhook で受信したユーザーIDを `store.line_user_id` に設定

---

## 6. 本番用 .env 設定

```bash
# /var/www/reservation/.env （VPSの場合）

# ★ 必ず変更する項目 ★
SECRET_KEY=ここに32文字以上のランダムな文字列を入力

# DB（VPSの場合は絶対パス推奨）
DATABASE_URL=sqlite:////var/www/reservation/reservation.db

# 本番URLに変更
BASE_URL=https://あなたのドメイン.com

# LINE（取得した値を設定）
LINE_CHANNEL_TOKEN=あなたのLINEチャンネルアクセストークン
LINE_CHANNEL_SECRET=あなたのLINEチャンネルシークレット

# 本番はfalseに変更（SQLログを出さない）
DEBUG=false
```

**SECRET_KEY の生成方法（PowerShellで実行）:**
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 7. バックアップ設定

SQLite はファイル1つなので、コピーするだけでバックアップできます。

### 7-1. 自動バックアップ（cron）

```bash
# バックアップスクリプトを作成
nano /var/www/reservation/backup.sh
```

```bash
#!/bin/bash
# DBバックアップ（直近7日分を保持）
BACKUP_DIR="/var/www/reservation/backups"
DB_FILE="/var/www/reservation/reservation.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp $DB_FILE $BACKUP_DIR/reservation_$DATE.db

# 7日より古いバックアップを削除
find $BACKUP_DIR -name "*.db" -mtime +7 -delete

echo "✅ バックアップ完了: reservation_$DATE.db"
```

```bash
chmod +x /var/www/reservation/backup.sh

# cronに登録（毎日午前3時に実行）
crontab -e
# 以下を追加:
0 3 * * * /var/www/reservation/backup.sh >> /var/log/reservation_backup.log 2>&1
```

### 7-2. バックアップの手動取得

```bash
# いつでも手動でバックアップ可能
cp /var/www/reservation/reservation.db \
   /var/www/reservation/backups/reservation_manual_$(date +%Y%m%d).db
```

### 7-3. バックアップからの復元

```bash
# サービスを止めてDBを置き換え
systemctl stop reservation
cp /var/www/reservation/backups/reservation_20260101_030000.db \
   /var/www/reservation/reservation.db
systemctl start reservation
```

---

## 8. アップデート手順

コードを修正してサーバーに反映する手順です。

```bash
# サーバーにSSH接続後
cd /var/www/reservation

# GitHubから最新コードを取得
git pull origin main

# パッケージに変更があった場合
source venv/bin/activate
pip install -r requirements.txt

# アプリを再起動
systemctl restart reservation

# 起動確認
systemctl status reservation
```

---

## 9. 障害対応チェックリスト

### サイトに繋がらない

```bash
# 1. アプリが起動しているか確認
systemctl status reservation

# 停止している場合
systemctl start reservation
journalctl -u reservation -n 50  # エラーログを確認

# 2. Nginxが動いているか確認
systemctl status nginx
nginx -t && systemctl restart nginx

# 3. ファイアウォール確認
ufw status
```

### 500エラーが出る

```bash
# アプリのエラーログを確認（最新50行）
journalctl -u reservation -n 50

# Nginxのエラーログを確認
tail -50 /var/log/nginx/reservation_error.log
```

### DBが壊れた・データが消えた

```bash
# バックアップから復元
systemctl stop reservation
ls /var/www/reservation/backups/           # バックアップ一覧確認
cp /var/www/reservation/backups/最新のファイル.db \
   /var/www/reservation/reservation.db
systemctl start reservation
```

### 証明書の更新（手動）

```bash
# 通常は自動更新されるが、問題があった場合
certbot renew --force-renewal
systemctl restart nginx
```

---

## 10. 運用コスト早見表

| 項目 | 無料構成 | 低コスト構成 |
|------|---------|------------|
| サーバー | Render.com 無料 | さくらVPS 643円/月 |
| ドメイン | なし（.onrender.com） | お名前.com 125円/月〜 |
| SSL | 無料（自動） | 無料（Let's Encrypt） |
| DB | SQLiteファイル | SQLiteファイル |
| LINE | 無料プラン（月1,000通） | 無料プラン |
| **合計** | **0円/月** | **約770円/月** |

---

*このドキュメントは spec.md と合わせて管理してください。*
