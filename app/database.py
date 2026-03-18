"""
データベース設定・セッション管理
spec.md セクション2参照
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reservation.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("DEBUG", "false").lower() == "true",
)

# SQLite外部キー有効化
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI依存性注入用DBセッション取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """DBテーブル作成（初回起動時）"""
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
