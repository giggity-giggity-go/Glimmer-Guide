"""v0.3.0-beta:会话删除时释放关联 memory_facts

按 fact_type 分类处理:
- HARD_DELETE:真删(Chroma 文档 + SQLite 行) — 不可逆
- SOFT_DELETE:is_deleted=True 标记,30 天 sweep — 可恢复窗口
- KEEP:跨会话保留,不动

设计决策(spec 2026-06-19 L-2 风险已采纳):软删 + 定期 vacuum 模式,
Chroma collection 不自动清 is_deleted 文档,需要 sweep job 物理删。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select, update

from yantu.data import vector_repo
from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.utils.logger import logger


# v0.3.0-beta 决策(spec 设计稿 6 种 fact_type 合并为 3 类处理)
# - user_attribute / preference / person_mention → KEEP(用户级属性,跨会话有用)
# - open_question / timeline_event → SOFT_DELETE(用户可能想回顾,30 天可恢复)
# - conversation_outcome → HARD_DELETE(会话私属,会话没了就没意义)
HARD_DELETE_FACTS: set[str] = {"conversation_outcome"}
SOFT_DELETE_FACTS: set[str] = {"open_question", "timeline_event"}
KEEP_FACTS: set[str] = {"user_attribute", "preference", "person_mention"}


def delete_session_with_memory(thread_id: str) -> dict:
    """删除会话 + 释放关联 memory_facts(3 类处理)

    跨 4 个存储:
    1. Chroma long_term_memory collection(where 级联,不可逆放最前)
    2. SQLite memory_facts 表(分类硬删/软删)
    3. LangGraph checkpoint 3 张表(已有 hard_delete_session 处理)
    4. Session 表行(已有)

    Returns:
        {"ok": True, "soft_deleted": int, "hard_deleted": int, "kept": int}
    """
    # 1) Chroma 先清(HARD_DELETE 类的 vector 文档不可逆,放最前)
    chroma_deleted = vector_repo.delete_facts_where({
        "source_thread": thread_id,
        "fact_type": {"$in": list(HARD_DELETE_FACTS)},
    })

    # 2) SQLite 软删(SOFT_DELETE 类)
    soft_count = 0
    with session_scope() as s:
        result = s.execute(
            update(MemoryFact)
            .where(
                MemoryFact.source_thread == thread_id,
                MemoryFact.fact_type.in_(SOFT_DELETE_FACTS),
                MemoryFact.is_deleted == False,  # noqa: E712
            )
            .values(is_deleted=True, deleted_at=datetime.utcnow())
        )
        soft_count = result.rowcount

    # 3) SQLite 硬删(HARD_DELETE 类)
    hard_count = 0
    with session_scope() as s:
        result = s.execute(
            delete(MemoryFact)
            .where(
                MemoryFact.source_thread == thread_id,
                MemoryFact.fact_type.in_(HARD_DELETE_FACTS),
            )
        )
        hard_count = result.rowcount

    # 4) KEEP 类不动,统计
    keep_count = 0
    with session_scope() as s:
        result = s.execute(
            select(MemoryFact)
            .where(
                MemoryFact.source_thread == thread_id,
                MemoryFact.fact_type.in_(KEEP_FACTS),
            )
        )
        keep_count = len(result.scalars().all())

    # 5) LangGraph checkpoint + Session 表(已有 hard_delete_session)
    from yantu.session.manager import hard_delete_session
    session_deleted = hard_delete_session(thread_id)

    logger.info(
        f"Session {thread_id} cleanup: "
        f"chroma_deleted={chroma_deleted}, "
        f"sqlite_soft={soft_count}, sqlite_hard={hard_count}, kept={keep_count}, "
        f"session_deleted={session_deleted}"
    )

    return {
        "ok": session_deleted,
        "soft_deleted": soft_count,
        "hard_deleted": hard_count,
        "kept": keep_count,
        "chroma_deleted": chroma_deleted,
    }


def sweep_soft_deleted_facts(older_than_days: int = 30) -> int:
    """物理删 30 天前的软删 fact

    on_startup 启动时调用一次(spec L-2:Chroma collection 不自动清
    is_deleted 文档 → 定期 vacuum)。

    Returns:
        物理删除的 fact 数
    """
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)

    # 1) 找出要物理删的 fact_id
    fact_ids: list[int] = []
    with session_scope() as s:
        old_facts = s.execute(
            select(MemoryFact)
            .where(
                MemoryFact.is_deleted == True,  # noqa: E712
                MemoryFact.deleted_at < cutoff,
            )
        ).scalars().all()
        fact_ids = [f.id for f in old_facts]

    if not fact_ids:
        logger.info("Sweep: no facts older than 30 days to delete")
        return 0

    # 2) Chroma 真删
    vector_repo.delete_facts_where({
        "memory_facts_id": {"$in": [str(fid) for fid in fact_ids]},
    })

    # 3) SQLite 真删
    with session_scope() as s:
        result = s.execute(
            delete(MemoryFact).where(MemoryFact.id.in_(fact_ids))
        )
        deleted_count = result.rowcount

    logger.info(
        f"Swept {deleted_count} soft-deleted facts older than {older_than_days} days"
    )
    return deleted_count
