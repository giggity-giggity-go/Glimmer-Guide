"""会话管理 — 侧边栏 CRUD + thread_id 切换

v0.3.0: thread_id = UUID4 hex 前 8 位(短,易识别)
首次 on_chat_start 调 create_session,后续 list_sessions 拉侧边栏,
patch / delete / switch 走 FastAPI / action_callback。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update

from yantu.data.db import session_scope
from yantu.data.models import Session
from yantu.utils.logger import logger


def _new_thread_id() -> str:
    """8 字符 thread_id(UUID4 hex 前 8 位,短到能进 UI)"""
    return uuid.uuid4().hex[:8]


def create_session(user_id: str = "default", title: str = "新会话") -> str:
    """新建会话,返回 thread_id"""
    thread_id = _new_thread_id()
    with session_scope() as s:
        s.add(Session(
            thread_id=thread_id,
            user_id=user_id,
            title=title,
        ))
    logger.info(f"Session created: thread_id={thread_id}, title={title!r}")
    return thread_id


def list_sessions(
    user_id: str = "default",
    include_archived: bool = False,
    limit: int = 100,
) -> list[dict]:
    """列出活跃会话(侧边栏用)

    排序:is_pinned DESC → updated_at DESC
    返回 dict 列表(JSON 可序列化)
    """
    with session_scope() as s:
        stmt = (
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.is_pinned.desc(), Session.updated_at.desc())
            .limit(limit)
        )
        if not include_archived:
            stmt = stmt.where(Session.is_archived == False)  # noqa
        rows = s.execute(stmt).scalars().all()
        out = []
        for r in rows:
            out.append({
                "thread_id": r.thread_id,
                "title": r.title,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "is_pinned": r.is_pinned,
                "is_archived": r.is_archived,
                "message_count": r.message_count,
                "last_tokens": r.last_tokens,
            })
        return out


def get_session(thread_id: str) -> Optional[dict]:
    """单条会话元数据(None 表示不存在)"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return None
        return {
            "thread_id": row.thread_id,
            "title": row.title,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "is_pinned": row.is_pinned,
            "is_archived": row.is_archived,
            "message_count": row.message_count,
            "last_tokens": row.last_tokens,
        }


def rename_session(thread_id: str, new_title: str) -> bool:
    """重命名(截断到 100 字符,匹配 schema)"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return False
        row.title = new_title[:100]
        return True


def toggle_pin(thread_id: str) -> Optional[bool]:
    """切换固定状态,返回切换后的 is_pinned;None 表示会话不存在"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return None
        row.is_pinned = not row.is_pinned
        return row.is_pinned


def archive_session(thread_id: str) -> bool:
    """归档(软删除,默认从侧边栏隐藏但保留 checkpoint)"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return False
        row.is_archived = True
        return True


def unarchive_session(thread_id: str) -> bool:
    """从归档恢复"""
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return False
        row.is_archived = False
        return True


def hard_delete_session(thread_id: str) -> bool:
    """v0.3.0: 硬删除 — 真删 Session 表行 + LangGraph checkpoint

    LangGraph SqliteSaver 不暴露公开 delete_thread API(v3.1),
    用原生 SQL 删 checkpoints / checkpoint_writes / checkpoint_blobs 三表中该 thread_id 行。
    """
    from yantu.data.db import _engine  # 私有 import,允许这里 hack
    from sqlalchemy import text as sql_text

    # 1. 删 Session 行
    with session_scope() as s:
        row = s.get(Session, thread_id)
        if row is None:
            return False
        s.delete(row)

    # 2. 删 LangGraph checkpoint 行(原生 SQL,跨 3 表)
    with _engine.begin() as conn:
        for tbl in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
            try:
                conn.execute(
                    sql_text(f"DELETE FROM {tbl} WHERE thread_id = :tid"),
                    {"tid": thread_id},
                )
            except Exception as e:
                # 表可能未建(checkpointer 未 setup),静默忽略
                logger.debug(f"hard_delete checkpoint table={tbl} skip: {e}")
    logger.info(f"Session hard deleted: thread_id={thread_id}")
    return True


def touch_session(thread_id: str, message_count_delta: int = 1) -> None:
    """每条消息后更新会话元数据(message_count + updated_at)"""
    with session_scope() as s:
        s.execute(
            update(Session)
            .where(Session.thread_id == thread_id)
            .values(
                updated_at=datetime.utcnow(),
                message_count=Session.message_count + message_count_delta,
            )
        )