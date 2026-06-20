"""v0.3.0-beta LangMem InMemoryStore 桥接

路径 A' 决策:LangMem 接受 langgraph.store.base.BaseStore,
本模块封装 LangGraph InMemoryStore + 从 SQLite rehydrate 逻辑。

为什么不用 Chroma adapter:
- LangGraph BaseStore 接口 12 个方法,Chroma adapter 200-300 行
- Chroma 已独立用于 RAG 检索(vector_repo.search 走 where 过滤)
- LangMem 走 InMemoryStore 管 schema/extract/search 协议,数据真源在 SQLite

进程启动时:从 memory_facts 表读所有 facts → 写入 InMemoryStore
新 fact 抽取时:同时写 SQLite + Chroma + InMemoryStore
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.store.base import Item
from langgraph.store.memory import InMemoryStore

from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.utils.logger import logger


# 模块级单例(store 是 LangGraph 进程级)
_store: Optional[InMemoryStore] = None


def get_store() -> InMemoryStore:
    """获取 LangMem 用的 InMemoryStore(单例)"""
    global _store
    if _store is None:
        _store = InMemoryStore()
        rehydrate_from_db(_store)
    return _store


def reset_store() -> None:
    """重置 store(测试用)"""
    global _store
    _store = None


def rehydrate_from_db(store: InMemoryStore) -> int:
    """从 SQLite memory_facts 读所有 fact 写到 InMemoryStore

    v0.3.0-beta:进程启动时调一次
    Returns:写入的 fact 数
    """
    count = 0
    with session_scope() as s:
        all_facts = s.query(MemoryFact).filter(
            MemoryFact.is_deleted == False  # noqa: E712
        ).all()
        for f in all_facts:
            namespace = ("memories", f.user_id)
            key = f"fact-{f.id}"
            value = {
                "id": f.id,
                "fact_type": f.fact_type,
                "text": f.fact_value.get("text", ""),
                "subject": f.subject or "",
                "keywords": f.keywords or [],
                "confidence": f.confidence,
                "source_thread": f.source_thread or "",
            }
            store.put(namespace, key, value)
            count += 1
    logger.info(f"LangMem bridge: rehydrated {count} facts into InMemoryStore")
    return count


def add_fact_to_store(fact_id: int, user_id: str, fact_data: dict[str, Any]) -> None:
    """新增 fact 时同步写 InMemoryStore(让 LangMem 能用)"""
    store = get_store()
    namespace = ("memories", user_id)
    key = f"fact-{fact_id}"
    store.put(namespace, key, fact_data)


def remove_fact_from_store(fact_id: int, user_id: str) -> None:
    """删除 fact 时从 InMemoryStore 移除(cleanup service 调)"""
    store = get_store()
    namespace = ("memories", user_id)
    key = f"fact-{fact_id}"
    try:
        store.delete(namespace, key)
    except Exception as e:
        logger.debug(f"LangMem bridge: delete fact {fact_id} skip: {e}")


def list_facts_in_store(user_id: str = "default") -> list[Item]:
    """列出 InMemoryStore 里的所有 fact(供 LangMem manage_memory tool 用)"""
    store = get_store()
    namespace = ("memories", user_id)
    return list(store.search(namespace, limit=1000))
