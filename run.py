#!/usr/bin/env python
"""
予約システム起動スクリプト
使用方法: python run.py
"""
import os
import shutil
from pathlib import Path

def setup():
    """初回セットアップ"""
    # .envファイルがなければ作成
    env_file = Path(".env")
    if not env_file.exists():
        shutil.copy(".env.example", ".env")
        print("✅ .env ファイルを作成しました。内容を確認・編集してください。")

    # 静的ディレクトリ作成
    Path("app/static/css").mkdir(parents=True, exist_ok=True)
    Path("app/static/js").mkdir(parents=True, exist_ok=True)

    print("✅ セットアップ完了")
    print("📋 spec.md を参照してシステム仕様を確認してください")


if __name__ == "__main__":
    import sys
    setup()

    import uvicorn
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "true").lower() == "true"
    
    print(f"\n🚀 サーバー起動中... http://localhost:{port}")
    print(f"   店舗管理: http://localhost:{port}/store/login")
    print(f"   予約ページ例: http://localhost:{port}/book/1\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
    )
