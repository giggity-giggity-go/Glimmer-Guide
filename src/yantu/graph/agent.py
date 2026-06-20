"""LangGraph Agent 编译 — AsyncSqliteSaver 持久化(多会话支撑 + 兼容 async router)

v0.3.0-alpha 变更:
- MemorySaver → SqliteSaver(sqlite3.Connection)
- 删 @lru_cache(maxsize=1):setup() 是副作用
- 每次 build_agent() 开新 SqliteSaver 实例(LangGraph 持有引用)
- checkpointer 表与 ORM 表共享同一 .db 文件

v0.3.0-beta 变更:
- router 改 async def 后,astream_events 调 aget_tuple → 需 AsyncSqliteSaver
- 从 langgraph.checkpoint.sqlite.aio 改用 AsyncSqliteSaver
- aiosqlite 已装,直接使用
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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
_saver_instance = None  # 模块级 saver 单例(keep context manager alive)


def ensure_checkpointer_tables() -> None:
    """v0.3.0-beta: 幂等触发 checkpointer 建表(AsyncSqliteSaver 版本)

    进入 from_conn_string 异步 contextmanager → setup() 建表,保持 saver 在模块级。
    在 init_db() 末尾调一次即可,后续 build_agent() 复用 _saver_instance。
    """
    global _checkpointer_tables_ready, _saver_instance
    if _checkpointer_tables_ready:
        return
    import asyncio

    async def _setup():
        global _saver_instance
        cm = AsyncSqliteSaver.from_conn_string(settings.sqlite_path)
        saver = await cm.__aenter__()
        await saver.setup()
        # 保持 cm 不退出 — 把 saver 存到模块级,程序退出时 GC 会清理
        _saver_instance = (cm, saver)
        return saver

    asyncio.run(_setup())
    _checkpointer_tables_ready = True
    logger.info(f"AsyncSqliteSaver tables ensured at {settings.sqlite_path}")


def _open_saver() -> AsyncSqliteSaver:
    """返回模块级 saver 单例(确保 contextmanager 保持 alive)"""
    if not _checkpointer_tables_ready:
        ensure_checkpointer_tables()
    return _saver_instance[1]


def build_agent():
    """编译并返回 LangGraph agent

    v0.3.0-beta: 用 AsyncSqliteSaver(兼容 async router)
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
    logger.info(f"LangGraph compiled (AsyncSqliteSaver, persistent checkpoint at {settings.sqlite_path})")
    return g.compile(checkpointer=saver)