"""LangGraph AgentState

v0.2.0 变更:
- intent: Literal 改成 new ["local", "yanzhao", "both", "chat"]
- 加 citations: list[dict](synthesizer structured output 引用)
- 加 grounded: bool(synthesizer structured output grounding 标志)
- reasoning + reasoning_tokens: 推理过程提取(vendor 重构同期加入)
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


# v0.2.0 (HB-03): Intent 新增 4 类(原 5 类拆并)
IntentType = Literal["local", "yanzhao", "both", "chat"]


class AgentState(TypedDict, total=False):
    """LangGraph 状态 schema"""

    # 消息历史(add_messages 自动累加)
    messages: Annotated[list[AnyMessage], add_messages]

    # 当前用户问题
    user_query: str

    # 意图分类(HB-03)
    intent: IntentType

    # 工具调用计划
    tool_calls: list[dict]

    # 工具结果累积(add reducer)
    tool_results: Annotated[list[dict], operator.add]

    # 最终响应
    response: str

    # HB-09: synthesizer 引用列表
    citations: list[dict]

    # HB-09: 回答是否完全基于工具结果
    grounded: bool

    # 推理过程(router + synthesizer 拼接,operator.add reducer 自动累加)
    reasoning: Annotated[str, operator.add]
    reasoning_tokens: int

    # v0.3.0-beta:上下文压缩状态
    is_compressed: bool
    compressed_summary: str

    # v0.3.0-beta:长期记忆检索结果(retriever 写入,router 注入)
    long_term_facts: list[dict]