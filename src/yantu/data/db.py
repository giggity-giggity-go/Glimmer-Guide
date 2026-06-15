"""SQLite engine + session"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from yantu.config import settings
from yantu.data.models import Base

# SQLite engine — 同一 DB 供 LangGraph SqliteSaver 复用
_engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    echo=False,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, conn_record):
    """启用外键约束"""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def init_db() -> None:
    """初始化表结构"""
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_engine)


def get_engine():
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务会话上下文"""
    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
