"""
Database configuration.

Production targets Supabase Postgres. SQLite remains available for local tests.
"""
import os
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.env import load_app_env

load_app_env()


def _normalize_database_url(raw_url: Optional[str]) -> str:
    if not raw_url:
        return "sqlite:///./reservation.db"

    url = raw_url.strip()
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


RAW_DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL = _normalize_database_url(RAW_DATABASE_URL)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine_kwargs = {
    "echo": DEBUG,
    "pool_pre_ping": True,
}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
