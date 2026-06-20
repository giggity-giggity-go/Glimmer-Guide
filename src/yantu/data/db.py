"""SQLite engine + session"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, text
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
    """初始化表结构

    v0.3.0: 加 PRAGMA WAL + checkpointer.setup()
    - WAL 模式允许并发读写不互锁,extractor 后台 task 写 long_term_memory 时不阻塞 LangGraph checkpoint
    - busy_timeout=5000ms 应对短时锁竞争

    v0.3.0-beta: 加轻量迁移
    - memory_facts.deleted_at 列(SQLite ALTER TABLE)
    - Base.metadata.create_all 不加列到已存在的表
    """
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_engine)
    # v0.3.0-beta: 轻量迁移(memory_facts.deleted_at)
    _migrate_add_deleted_at()
    # v0.3.0: WAL + busy_timeout(单 connection 触发,持久化在 -wal 文件)
    with _engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
        conn.commit()
    # v0.3.0: 触发 LangGraph checkpointer 建表(checkpoints / checkpoint_writes / checkpoint_blobs)
    # lazy import 避免循环:yantu.graph.agent → yantu.data.db
    try:
        from yantu.graph.agent import ensure_checkpointer_tables
        ensure_checkpointer_tables()
    except Exception as e:
        # 不阻塞 ORM 初始化,允许 checkpointer 失败时数据层仍可用
        from yantu.utils.logger import logger
        logger.warning(f"checkpointer.setup() 跳过(可能未安装 langgraph-checkpoint-sqlite): {e}")


def _migrate_add_deleted_at() -> None:
    """v0.3.0-beta 轻量迁移:memory_facts 表加 deleted_at 列

    Base.metadata.create_all 不向已存在表加列。
    检查 information_schema,缺则 ALTER TABLE。
    """
    with _engine.connect() as conn:
        # SQLite 查列是否存在
        result = conn.execute(text(
            "SELECT name FROM pragma_table_info('memory_facts') WHERE name='deleted_at'"
        ))
        if result.fetchone() is None:
            conn.execute(text(
                "ALTER TABLE memory_facts ADD COLUMN deleted_at DATETIME"
            ))
            conn.commit()
            from yantu.utils.logger import logger
            logger.info("Migration: added memory_facts.deleted_at column")


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
