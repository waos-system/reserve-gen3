"""
店舗認証ルーター（ログイン・ログアウト）
bcrypt を直接使用（passlib非依存）
"""
import bcrypt
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Store

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def get_current_store(request: Request, db: Session = Depends(get_db)):
    store_id = request.session.get("store_id")
    if not store_id:
        return None
    try:
        store_id = int(store_id)
    except (ValueError, TypeError):
        return None
    return db.query(Store).filter(Store.id == store_id).first()


def require_store(request: Request, db: Session = Depends(get_db)):
    store = get_current_store(request, db)
    if not store:
        raise HTTPException(status_code=302, headers={"Location": "/store/login"})
    return store


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("store_id"):
        return RedirectResponse("/store/dashboard", status_code=302)
    return templates.TemplateResponse("store/login.html", {
        "request": request, "error": None,
    })


@router.post("/login")
async def login_post(
    request: Request,
    phone_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.phone_number == phone_number).first()
    if not store or not verify_password(password, store.password_hash):
        return templates.TemplateResponse("store/login.html", {
            "request": request,
            "error": "電話番号またはパスワードが違います",
        })
    request.session["store_id"] = str(store.id)
    request.session["store_name"] = store.store_name
    return RedirectResponse("/store/dashboard", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/store/login", status_code=302)
