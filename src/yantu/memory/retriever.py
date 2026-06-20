"""v0.3.0-beta 长期记忆 retriever

路径 A':retrieval 走 Chroma(跟现有 RAG 一致),不走 LangMem。
这样:
- 复用现有 bge embedding + vector_repo
- top-K 走 metadata where 过滤(user_id + is_deleted=False)
- 命中后回写 access_count + last_accessed_at 到 SQLite
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import update

from yantu.data import vector_repo
from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.data.user_settings import get_setting
from yantu.utils.embedder import embed_query
from yantu.utils.logger import logger


async def retrieve_relevant_facts(
    query: str,
    user_id: str = "default",
    k: int | None = None,
) -> list[dict]:
    """语义检索 top-K 长期记忆

    Args:
        query: 用户当前问题
        user_id: 用户隔离(单用户本地写死 "default")
        k: top-K,默认读 user_settings.memory_injection_count

    Returns:
        list of {fact_type, subject, text, confidence, source_thread, memory_facts_id}
        按相似度倒序
    """
    if k is None:
        k = int(get_setting("memory_injection_count", 10))

    if not get_setting("memory_enabled", True):
        return []

    # Chroma 检索 — 多条件必须用 $and 包装(API 限制 1 个 operator)
    where_filter = {
        "$and": [
            {"user_id": user_id},
            {"is_deleted": False},
        ]
    }
    results = vector_repo.search(
        query=query,
        k=k,
        where=where_filter,
        collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION,
    )

    if not results:
        return []

    # 提取 fact_ids 并回写访问统计
    fact_ids = []
    facts = []
    for r in results:
        meta = r.get("metadata", {})
        fid = meta.get("memory_facts_id")
        if fid is None:
            continue
        try:
            fid_int = int(fid)
            fact_ids.append(fid_int)
        except (ValueError, TypeError):
            continue
        facts.append({
            "memory_facts_id": fid_int,
            "fact_type": meta.get("fact_type", ""),
            "subject": meta.get("subject", ""),
            "text": r.get("document", ""),
            "confidence": meta.get("confidence", 1.0),
            "source_thread": meta.get("source_thread", ""),
            "distance": r.get("distance"),
        })

    # 更新 access_count + last_accessed_at
    if fact_ids:
        with session_scope() as s:
            s.execute(
                update(MemoryFact)
                .where(MemoryFact.id.in_(fact_ids))
                .values(
                    access_count=MemoryFact.access_count + 1,
                    last_accessed_at=datetime.utcnow(),
                )
            )

    logger.info(f"Retriever: {len(facts)} facts for query={query[:50]!r}")
    return facts
