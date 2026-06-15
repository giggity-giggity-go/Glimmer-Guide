"""LangGraph AgentState"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AgentState(TypedDict, total=False):
    """LangGraph 状态 schema"""

    # 消息历史(add_messages 自动累加)
    messages: Annotated[list[AnyMessage], add_messages]

    # 当前用户问题
    user_query: str

    # 意图分类
    intent: Literal["search_local", "fetch_web", "compare", "recommend", "chat"]

    # 工具调用计划
    tool_calls: list[dict]

    # 工具结果累积(add reducer)
    tool_results: Annotated[list[dict], operator.add]

    # 最终响应
    response: str
