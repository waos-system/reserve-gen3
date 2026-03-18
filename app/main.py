"""
予約システム FastAPI メインアプリケーション
spec.md 参照・更新ポイント: セクション1 技術スタック、セクション4 APIエンドポイント
"""
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import init_db
from app.routers import auth, store, customer

load_dotenv()

app = FastAPI(
    title="予約システム",
    description="店舗向け予約管理システム",
    version="1.0.0",
)

# セッションミドルウェア
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-please-change-in-production")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=86400,
    https_only=False,
    same_site="lax",
)

# 静的ファイル
static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ルーター登録
app.include_router(auth.router, prefix="/store", tags=["store-auth"])
app.include_router(store.router, prefix="/store", tags=["store-management"])
# 新規登録は /store/register で auth より後に登録（store.router に含まれる）
app.include_router(customer.router, prefix="/book", tags=["customer-booking"])

# 確認URLルーター（/confirm/{token}）
from app.routers.customer import confirm_reservation
app.add_api_route(
    "/confirm/{token}",
    confirm_reservation,
    methods=["GET"],
    response_class=HTMLResponse,
    tags=["customer-booking"],
)

# Jinja2グローバル関数を登録（テンプレートで enumerate/min/max が使えるように）
templates = Jinja2Templates(directory="app/templates")
templates.env.globals.update({
    "enumerate": enumerate,
    "min": min,
    "max": max,
    "zip": zip,
    "len": len,
})


@app.on_event("startup")
async def startup_event():
    """起動時にDBを初期化"""
    init_db()
    print("✅ データベース初期化完了")
    print(f"📋 spec.md を参照: {Path('spec.md').absolute()}")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse("/store/login", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
