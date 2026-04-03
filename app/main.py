"""
FastAPI application entrypoint.
"""
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.env import load_app_env
from app.routers import auth, customer, store

load_app_env()

app = FastAPI(
    title="Reservation System",
    description="Store reservation management system",
    version="1.0.0",
)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-please-change-in-production")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=86400,
    https_only=False,
    same_site="lax",
)

static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router, prefix="/store", tags=["store-auth"])
app.include_router(store.router, prefix="/store", tags=["store-management"])
app.include_router(customer.router, prefix="/book", tags=["customer-booking"])

from app.routers.customer import confirm_reservation

app.add_api_route(
    "/confirm/{token}",
    confirm_reservation,
    methods=["GET"],
    response_class=HTMLResponse,
    tags=["customer-booking"],
)

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
    """Initialize the database when enabled."""
    if os.getenv("AUTO_INIT_DB", "true").lower() == "true":
        init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse("/store/login", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
