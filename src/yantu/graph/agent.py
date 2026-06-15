"""LangGraph Agent 编译"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

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


@lru_cache(maxsize=1)
def build_agent():
    """编译并返回 LangGraph agent(checkpointing enabled)"""
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
    g.add_edge("tools", "router")  # 工具结果回到 router(可循环)
    g.add_edge("synthesizer", END)

    # 用 SqliteSaver 持久化(供 Chainlit 多会话)
    import os
    os.makedirs(settings.data_dir, exist_ok=True)
    # SqliteSaver 需要 sqlite3 连接(SqliteSaver.from_conn_string 是 context manager,不便长期持有)
    conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    logger.info(f"LangGraph compiled, checkpoint DB: {settings.sqlite_path}")
    return g.compile(checkpointer=checkpointer)
