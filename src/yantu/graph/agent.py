"""LangGraph Agent 编译 — SqliteSaver 持久化(多会话支撑)

v0.3.0 变更:
- MemorySaver → SqliteSaver(sqlite3.Connection)
- 删 @lru_cache(maxsize=1):setup() 是副作用
- 每次 build_agent() 开新 SqliteSaver 实例(LangGraph 持有引用)
- checkpointer 表与 ORM 表共享同一 .db 文件

注意:langgraph-checkpoint-sqlite 3.x 的 SqliteSaver.from_conn_string()
返回 generator contextmanager,但 SqliteSaver(conn) 直接构造可用 — 我们用后者,
因为需要把 saver 实例交付给 LangGraph compile()。
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from yantu.config import settings
from yantu.graph.nodes import (
    make_router_node,
    make_synthesizer_node,
    make_tool_node,
    should_continue,
)
from yantu.graph.state import AgentState
from yantu.utils.logger import logger


_checkpointer_tables_ready: bool = False


def ensure_checkpointer_tables() -> None:
    """v0.3.0: 幂等触发 checkpointer 建表

    用 from_conn_string contextmanager 进入 → setup() → 退出。
    在 init_db() 末尾调一次即可,后续 build_agent() 直接 SqliteSaver(conn)。
    """
    global _checkpointer_tables_ready
    if _checkpointer_tables_ready:
        return
    cm = SqliteSaver.from_conn_string(settings.sqlite_path)
    with cm as saver:
        saver.setup()
    _checkpointer_tables_ready = True
    logger.info(f"SqliteSaver tables ensured at {settings.sqlite_path}")


def _open_saver() -> SqliteSaver:
    """开一个 SqliteSaver 实例(供 build_agent 使用)

    复用 db._engine 的底层 sqlite3 connection,确保 checkpointer 与 ORM 共用同一文件
    (避免双 conn 写同一 db 的潜在锁竞争)。
    SqliteSaver(conn) 直接构造,LangGraph 持有引用。
    """
    from yantu.data.db import _engine
    # SQLAlchemy engine.connect() 拿到的是 ConnectionProxy,SqliteSaver 要底层 sqlite3.Connection
    # 用 engine.raw_connection() 拿真实连接
    conn = _engine.raw_connection()
    return SqliteSaver(conn)


def build_agent():
    """编译并返回 LangGraph agent

    v0.3.0: 用 SqliteSaver(原 MemorySaver 重启即丢)
    """
    g = StateGraph(AgentState)

    g.add_node("router", make_router_node())
    g.add_node("tools", make_tool_node())
    g.add_node("synthesizer", make_synthesizer_node())

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        should_continue,
        {
            "tools": "tools",
            "synthesize": "synthesizer",
        },
    )
    g.add_edge("tools", "router")
    g.add_edge("synthesizer", END)

    saver = _open_saver()
    logger.info(f"LangGraph compiled (SqliteSaver, persistent checkpoint at {settings.sqlite_path})")
    return g.compile(checkpointer=saver)