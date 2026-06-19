"""LangGraph 节点

v0.2.0 变更 (HB-03 + HB-09 + MB-05):
- HB-03: 两阶段 router — Intent classifier (no tools) → bind 1-2 tools per bucket
  - 删除 SYSTEM_PROMPT 中提到的 "fetch_web 工具"(不存在)
  - router temperature 0.7 → 0.2(降低 hallucination)
- HB-09: Synthesizer 用 Pydantic structured output + 剪裁 history + temperature=0
  - 强制 max_tokens 1500 + answer max_length 1500
  - 强制 grounding 声明,防止 LLM 编造
- MB-05: router temperature 降到 0.2
"""
from __future__ import annotations

import json
import operator
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from yantu.graph.state import AgentState
from yantu.graph.tools import ALL_TOOLS, search_local, get_school_info, get_recruitment_notices, get_disciplines, query_school_library
from yantu.utils.llm import get_llm, get_user_profile_prompt
from yantu.utils.logger import logger


SYSTEM_PROMPT = """你是研途萤火(yantu)——为考研人服务的个人助理。

[能力]
- 检索用户已摄入的本地资料(招生章程、专业目录、调研报告等)
- 实时查询研招网公开信息(院校库、专业库、招生简章)
- 综合本地 + 网络信息回答

[回答风格]
- 简洁准确,数字/分数线要明确标注
- 引用来源时给出文件名或学校名
- 不确定的明确说"不确定",不编造
- 不爬取任何成绩/调剂/录取/个人信息

[重要约束]
- 严禁编造未在工具结果中出现的数据(分数线/招生人数等)
- 如果工具未返回信息,必须诚实说"未找到"
- 综合节点以 grounded=True 输出,代表回答完全基于工具结果

"""


def _system_with_profile() -> str:
    """System prompt + 用户画像"""
    profile = get_user_profile_prompt()
    if profile:
        return SYSTEM_PROMPT + "\n" + profile + "\n"
    return SYSTEM_PROMPT


# ==================== HB-03: 两阶段 router — Intent 分类器 ====================

class Intent(BaseModel):
    """用户意图分类(Pydantic structured output)"""
    target: Literal["local", "yanzhao", "both", "chat"] = Field(
        ..., description="意图类别"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="置信度 0-1"
    )
    reasoning: str = Field(
        ..., max_length=200, description="分类理由(<=200字符)"
    )


INTENT_PROMPT = """分析用户问题属于哪一类:

- "local": 用户问的是已摄入资料(招生章程 PDF、专业目录等)
  例:"复试分数线多少"、"招生人数"、"专业课考什么"、"报录比"
- "yanzhao": 用户问的是研招网实时数据
  例:"院校库"、"招生简章列表"、"某校详情"
- "both": 两者结合
  例:"对比某校复试线和该校招生简章"
- "chat": 闲聊/感谢/无关问题,不调任何工具

用户问题:{query}

返回 JSON 格式 Intent。"""


# HB-03: 工具桶,每个意图只 bind 对应工具(降低 LLM 选错率)
TOOL_BUCKETS: dict[str, list] = {
    "local":   [search_local],
    "yanzhao": [query_school_library, get_school_info, get_disciplines, get_recruitment_notices],
    "both":    ALL_TOOLS,
    "chat":    [],
}


def _classify_intent(query: str) -> Intent:
    """阶段 1: 不带工具的 LLM,只做意图分类(用 structured output)"""
    llm = get_llm(temperature=0.2)  # MB-05: 低温度
    try:
        structured = llm.with_structured_output(Intent, method="json_schema", strict=True)
        return structured.invoke([
            SystemMessage(content=INTENT_PROMPT.format(query=query)),
        ])
    except Exception as e:
        logger.warning(f"Intent structured output failed: {e}, fallback to both")
        # 降级:返回 both 让 router 自选
        return Intent(target="both", confidence=0.5, reasoning=f"structured_failed: {e}")


def make_router_node():
    """router 节点:两阶段(Intent 分类 → bind 1-N tool)"""

    def router(state: AgentState) -> AgentState:
        query = state.get("user_query", "")
        intent = _classify_intent(query)
        logger.info(
            f"Intent: target={intent.target}, confidence={intent.confidence}, "
            f"reasoning={intent.reasoning[:80]}"
        )
        tools = TOOL_BUCKETS.get(intent.target, [])
        if not tools:
            # chat 路径:不调工具,直接 synthesizer
            logger.info(f"Router: chat intent, skip tool call")
            return {
                "messages": [],
                "intent": intent.target,
            }
        # 阶段 2: bind 该 intent 对应的工具,让 LLM 选择具体调用
        llm = get_llm(temperature=0.2)
        llm_with_tools = llm.bind_tools(tools)
        msgs = [SystemMessage(content=_system_with_profile())]
        if state.get("messages"):
            msgs.extend(state["messages"])
        msgs.append(HumanMessage(content=query))
        ai = llm_with_tools.invoke(msgs)
        logger.info(
            f"Router: target={intent.target}, "
            f"tool_calls={bool(ai.tool_calls)}, "
            f"tools_available={[t.name for t in tools]}"
        )
        return {
            "messages": [ai],
            "intent": intent.target,
        }

    return router


# ==================== HB-09: Synthesizer structured output ====================

class Citation(BaseModel):
    """回答引用的来源"""
    source: str = Field(..., max_length=100, description="文件名或学校名")
    snippet: str = Field(..., max_length=200, description="引用片段(<=200字符)")
    score: float = Field(0.0, ge=0.0, le=1.0, description="相关度 0-1")


class FinalAnswer(BaseModel):
    """Synthesizer 强制输出格式(HB-09)"""
    answer: str = Field(..., max_length=1500, description="最终回答(<=1500字符)")
    citations: list[Citation] = Field(
        default_factory=list, description="引用列表"
    )
    grounded: bool = Field(
        ..., description="回答是否完全基于工具结果(True)/ 编造了未出现的数据(False)"
    )


def _crop_history(messages):
    """HB-09: 只保留 human/tool/AI-with-tool_calls,丢弃中间 LLM 长文本"""
    out = []
    for m in messages:
        t = getattr(m, "type", "")
        if t == "human":
            out.append(m)
        elif t == "tool":
            out.append(m)
        elif t == "ai":
            # 只保留带 tool_calls 的 AI message(用于上下文)
            if getattr(m, "tool_calls", None):
                out.append(m)
    return out


def make_synthesizer_node():
    """综合节点:structured output + 剪裁 history + temperature=0(HB-09)"""

    def synthesizer(state: AgentState) -> AgentState:
        llm = get_llm(temperature=0.0)
        msgs = [SystemMessage(content=_system_with_profile() + (
            "\n[综合要求]\n"
            "- 必须基于工具结果回答,严禁编造未出现的数据\n"
            "- 引用来源时给出文件名或学校名\n"
            "- 数字/分数线要明确标注\n"
            "- 工具未返回时诚实说'未找到'\n"
            "- 输出 JSON,字段: answer / citations / grounded"
        ))]
        msgs.extend(_crop_history(state.get("messages", [])))
        msgs.append(HumanMessage(content=(
            f"请综合以上工具结果,回答用户原始问题:\n{state.get('user_query', '')}"
        )))
        try:
            structured = llm.with_structured_output(FinalAnswer, method="json_schema", strict=True)
            result = structured.invoke(msgs)
            response = result.answer
            citations = [c.model_dump() for c in result.citations]
            grounded = result.grounded
            logger.info(
                f"Synthesizer: answer_chars={len(response)}, "
                f"citations={len(citations)}, grounded={grounded}"
            )
            return {
                "messages": [],
                "response": response,
                "citations": citations,
                "grounded": grounded,
            }
        except Exception as e:
            logger.warning(f"Synthesizer structured output failed: {e}, fallback to plain text")
            ai = llm.invoke(msgs + [HumanMessage(content="请直接用 1-3 段话回答。")])
            response = ai.content if isinstance(ai.content, str) else str(ai.content)
            return {
                "messages": [ai],
                "response": response,
                "citations": [],
                "grounded": False,  # 兜底路径无法保证 grounded
            }

    return synthesizer


def make_tool_node():
    """工具执行节点(用 LangGraph 预置 ToolNode)"""
    return ToolNode(ALL_TOOLS)


# HB-01: 单次 query 最多调 5 个 tool(防止死循环 / LLM hallucination 重复调)
MAX_TOOL_ROUNDS = 5

# HB-01: astream_events 的 recursion_limit 上限(冗余保护,should_continue 已强制)
RECURSION_LIMIT = 10


def should_continue(state: AgentState) -> Literal["tools", "synthesize"]:
    """决定下一步:调工具还是综合输出

    v0.2.0 (HB-01): 加 ToolMessage 计数,避免 router→tools→router 死循环
    触发 GraphRecursionError 500。超过 MAX_TOOL_ROUNDS 强制走 synthesizer。
    """
    msgs = state.get("messages", [])
    if not msgs:
        return "synthesize"
    # HB-01: 历史 ToolMessage 数量超过 MAX_TOOL_ROUNDS → 强制 synthesize
    tool_msg_count = sum(
        1 for m in msgs if getattr(m, "type", "") == "tool"
    )
    if tool_msg_count >= MAX_TOOL_ROUNDS:
        logger.info(
            f"hit MAX_TOOL_ROUNDS={MAX_TOOL_ROUNDS} "
            f"(tool_msg_count={tool_msg_count}), force synthesize"
        )
        return "synthesize"
    last = msgs[-1]
    # AI 消息带 tool_calls → 执行
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "synthesize"