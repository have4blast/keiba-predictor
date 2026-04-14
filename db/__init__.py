"""データベース接続・セッション管理"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/keiba.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """全テーブルを作成する（初回起動時）"""
    from db.models import Base
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """セッションを返す"""
    return SessionLocal()
