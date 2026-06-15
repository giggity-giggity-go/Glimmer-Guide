"""LangGraph Agent 编译"""
from __future__ import annotations

import os
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

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
    """编译并返回 LangGraph agent

    Checkpoint: 内存 MemorySaver(自用场景,重启 Chainlit 会丢会话历史)
    如需持久化,可改为 AsyncSqliteSaver(需要 lifespan 管理 context manager)
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

    os.makedirs(settings.data_dir, exist_ok=True)
    checkpointer = MemorySaver()
    logger.info("LangGraph compiled (MemorySaver, in-memory checkpoint)")
    return g.compile(checkpointer=checkpointer)
