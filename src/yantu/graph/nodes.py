"""LangGraph 节点"""
from __future__ import annotations

import json
import operator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from yantu.graph.state import AgentState
from yantu.graph.tools import ALL_TOOLS
from yantu.utils.llm import get_llm, get_user_profile_prompt
from yantu.utils.logger import logger


SYSTEM_PROMPT = """你是研途萤火(yantu)——为考研人服务的个人助理。

[能力]
- 检索用户已摄入的本地资料(招生章程、专业目录、调研报告等)
- 实时查询研招网公开信息(院校库、专业库、招生简章)
- 综合本地 + 网络信息回答

[回答风格]
- 简洁准确,数字/分数线要明确标注
- 引用来源时给出文件名
- 不确定的明确说"不确定",不编造
- 不爬取任何成绩/调剂/录取/个人信息

[可用工具]
调用工具前先判断:这是"已摄入资料"问题 → search_local;这是"研招网实时数据"问题 → fetch_web 工具。

"""


def _system_with_profile() -> str:
    """System prompt + 用户画像"""
    profile = get_user_profile_prompt()
    if profile:
        return SYSTEM_PROMPT + "\n" + profile + "\n"
    return SYSTEM_PROMPT


def make_router_node():
    """router 节点:把用户问题分类 + 选择工具"""

    def router(state: AgentState) -> AgentState:
        llm = get_llm()
        profile = get_user_profile_prompt()
        prompt = (
            _system_with_profile()
            + "\n\n[当前问题]\n"
            + state.get("user_query", "")
            + "\n\n请回答用户的最新问题。如果需要,使用工具。"
        )
        # 走带 tool 的 LLM
        llm_with_tools = llm.bind_tools(ALL_TOOLS)
        msgs = [SystemMessage(content=prompt)]
        if state.get("messages"):
            msgs.extend(state["messages"])
        ai = llm_with_tools.invoke(msgs)
        logger.info(f"Router emitted: tool_calls={bool(ai.tool_calls)}")
        return {"messages": [ai]}

    return router


def make_synthesizer_node():
    """综合节点:把工具结果合成自然语言回答"""

    def synthesizer(state: AgentState) -> AgentState:
        llm = get_llm()
        # 取最近一条 AI 消息 + 所有 ToolMessage
        msgs = [SystemMessage(content=_system_with_profile())]
        msgs.extend(state.get("messages", []))
        msgs.append(
            HumanMessage(
                content=(
                    "请基于以上工具结果,综合回答用户原始问题。"
                    "引用来源时给出文件名或学校名;数字/分数线要明确;若工具未返回信息则诚实说明。"
                )
            )
        )
        ai = llm.invoke(msgs)
        response = ai.content if isinstance(ai.content, str) else str(ai.content)
        logger.info(f"Synthesizer response length={len(response)}")
        return {"messages": [ai], "response": response}

    return synthesizer


def make_tool_node():
    """工具执行节点(用 LangGraph 预置 ToolNode)"""
    return ToolNode(ALL_TOOLS)


def should_continue(state: AgentState) -> Literal["tools", "synthesize"]:
    """决定下一步:调工具还是综合输出"""
    msgs = state.get("messages", [])
    if not msgs:
        return "synthesize"
    last = msgs[-1]
    # AI 消息带 tool_calls → 执行
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "synthesize"
