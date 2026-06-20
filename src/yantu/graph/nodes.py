"""LangGraph 节点

v0.2.0 变更 (HB-03 + HB-09 + MB-05):
- HB-03: 两阶段 router — Intent classifier (no tools) → bind 1-2 tools per bucket
  - 删除 SYSTEM_PROMPT 中提到的 "fetch_web 工具"(不存在)
  - router temperature 0.7 → 0.2(降低 hallucination)
- HB-09: Synthesizer 用 Pydantic structured output + 剪裁 history + temperature=0
  - 强制 max_tokens 1500 + answer max_length 1500
  - 强制 grounding 声明,防止 LLM 编造
- MB-05: router temperature 降到 0.2
- v0.2.0-alpha 同期: router + synthesizer 各调 extract_reasoning,把
  reasoning/reasoning_tokens 写入 state(用户画像 UI 的 CollapsibleReasoning 折叠块需要)

v0.2.1 变更 (chat JSON 泄漏统一修复):
- Intent classifier + Synthesizer 切到 method="function_calling"
  (json_schema + strict=True 在 glm-5.1 / M2.7 / M3 / o3-mini 4 个 vendor 上 100%
  抛异常 — LLM 把 JSON 裹在 ```json ... ``` fence 里,Pydantic strict 模式从 `<`
  开始 parse 失败;M3 还因 reasoning_split 被 OpenAI SDK 拒绝)
- 删 system prompt "- 输出 JSON,字段: answer / citations / grounded":
  function_calling 通过 tool_calls 协议自带 schema,LLM 不需要文字提示
- Fallback 路径加 _strip_fenced_json(): 即便主路径失败,也不会再泄漏 fence
"""
from __future__ import annotations

import json
import operator
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from yantu.graph.compressor import compress_context_if_needed
from yantu.graph.state import AgentState
from yantu.graph.tools import (
    ALL_TOOLS,
    search_local,
    get_school_info,
    get_recruitment_notices,
    get_disciplines,
    query_school_library,
)
from yantu.ui.reasoning import extract_reasoning
from yantu.utils.llm import get_llm, get_user_profile_prompt
from yantu.utils.logger import logger


# v0.2.1: fallback 路径 strip markdown code fence(```json ... ```)
# 任何 vendor 在 fallback 路径(无 schema)都可能输出 fence JSON,这里兜底
_FENCE_JSON_RE = re.compile(r"```(?:json)?\s*\n(\{.*?\})\n```", re.DOTALL)


def _strip_fenced_json(text: str) -> str:
    """如果 text 是 ```json\\n{...}\\n``` 包裹,提取 inner JSON;否则原样返回。

    v0.2.1: 防止 LLM 输出的 markdown fence 字符串泄漏到 Chainlit UI。
    用 \\{.*?\\} 非贪婪,只在 ```json...``` 包裹下生效,不会误吞其他内容。
    """
    if not text:
        return ""
    m = _FENCE_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


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
    """阶段 1: 不带工具的 LLM,只做意图分类(用 structured output)

    v0.2.1: method="function_calling" 替代 "json_schema" + strict=True
    (json_schema+strict 在 glm-5.1 / M2.7 / M3 / o3-mini 上 100% 抛异常:
    LLM 把 JSON 裹在 ```json ... ``` fence 里,Pydantic strict 模式从 `<` 开始 parse 失败)
    """
    llm = get_llm(temperature=0.2)  # MB-05: 低温度
    try:
        structured = llm.with_structured_output(Intent, method="function_calling")
        return structured.invoke([
            SystemMessage(content=INTENT_PROMPT.format(query=query)),
        ])
    except Exception as e:
        # Bug 修复: 错误消息本身可能 >200 字符,直接构造会触发 Pydantic 验证
        # 兜底:截断到 150 字符(留余量),target 默认 both 让 router 自选
        logger.warning(f"Intent structured output failed: {type(e).__name__}, fallback to both")
        err_short = (str(e)[:150] + "...") if len(str(e)) > 150 else str(e)
        try:
            return Intent(target="both", confidence=0.5, reasoning=f"fallback: {err_short}")
        except Exception as e2:
            # 万一 Pydantic 又校验失败,返回最简 Intent
            logger.error(f"Fallback Intent validation also failed: {e2}")
            return Intent(target="both", confidence=0.0, reasoning="fallback")


def make_router_node():
    """router 节点:两阶段(Intent 分类 → bind 1-N tool)

    v0.3.0-beta 改造:
    - async def router(可 await compressor / retriever)
    - 阶段 0:compress_context_if_needed 压缩历史
    - 阶段 0.5:retrieve_relevant_facts 注入长期记忆
    """

    async def router(state: AgentState) -> AgentState:
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

        # v0.3.0-beta 阶段 0:上下文压缩
        messages = state.get("messages", [])
        comp_result = await compress_context_if_needed(messages)
        if comp_result.get("is_compressed") and comp_result.get("messages"):
            messages = comp_result["messages"]
            logger.info(
                f"Router: compressed to {len(messages)} msgs "
                f"({comp_result.get('compressed_summary', '')[:60]}...)"
            )

        # v0.3.0-beta 阶段 0.5:长期记忆检索(注入 system prompt)
        long_term_block = ""
        facts = state.get("long_term_facts", [])
        if facts:
            long_term_block = "\n\n[长期记忆]\n" + _format_facts(facts)

        # 阶段 2: bind 该 intent 对应的工具,让 LLM 选择具体调用
        llm = get_llm(temperature=0.2)
        llm_with_tools = llm.bind_tools(tools)
        system_content = _system_with_profile() + long_term_block
        msgs = [SystemMessage(content=system_content)]
        if messages:
            msgs.extend(messages)
        msgs.append(HumanMessage(content=query))
        ai = llm_with_tools.invoke(msgs)
        # v0.2.0-alpha: 同时返回 reasoning 字段(供 CollapsibleReasoning UI)
        _r = extract_reasoning(ai)
        logger.info(
            f"Router: target={intent.target}, "
            f"tool_calls={bool(ai.tool_calls)}, "
            f"tools_available={[t.name for t in tools]}, "
            f"reasoning_chars={len(_r.text)}"
        )
        return {
            "messages": [ai] if not comp_result.get("is_compressed") else [ai],
            "intent": intent.target,
            "reasoning": _r.text + ("\n" if _r.text else ""),
            "reasoning_tokens": _r.tokens,
            "is_compressed": comp_result.get("is_compressed", False),
            "compressed_summary": comp_result.get("compressed_summary", ""),
        }

    return router


def _format_facts(facts: list[dict]) -> str:
    """格式化 facts 为可读文本(注入 system prompt)

    Args:
        facts: list of {fact_type, subject, text, confidence} dicts
    """
    lines = []
    for f in facts:
        ftype = f.get("fact_type", "")
        text = f.get("text", "") or f.get("fact_value", {}).get("text", "")
        subj = f.get("subject", "")
        conf = f.get("confidence", 1.0)
        prefix = f"[{ftype}]"
        if subj:
            prefix += f"({subj})"
        lines.append(f"- {prefix} {text} (conf={conf:.2f})")
    return "\n".join(lines)


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
            "- 工具未返回时诚实说'未找到'"
            # v0.2.1: 删 "输出 JSON,字段: answer / citations / grounded" — function_calling
            # 通过 tool_calls 协议自带 schema,LLM 不需要文字提示;保留反而让 fallback 路径
            # 的 LLM 看到矛盾指令,吐 fence JSON。
        ))]
        msgs.extend(_crop_history(state.get("messages", [])))
        msgs.append(HumanMessage(content=(
            f"请综合以上工具结果,回答用户原始问题:\n{state.get('user_query', '')}"
        )))
        try:
            # v0.2.1: function_calling 替代 json_schema + strict=True
            structured = llm.with_structured_output(FinalAnswer, method="function_calling")
            result = structured.invoke(msgs)
            response = result.answer
            citations = [c.model_dump() for c in result.citations]
            grounded = result.grounded
            logger.info(
                f"Synthesizer: answer_chars={len(response)}, "
                f"citations={len(citations)}, grounded={grounded}"
            )
            # v0.2.0-alpha: synthesizer 不再累积 reasoning(已在 router 中抓取)
            return {
                "messages": [],
                "response": response,
                "citations": citations,
                "grounded": grounded,
            }
        except Exception as e:
            logger.warning(f"Synthesizer structured output failed: {e}, fallback to plain text")
            ai = llm.invoke(msgs + [HumanMessage(content="请直接用 1-3 段话回答。")])
            content = ai.content if isinstance(ai.content, str) else str(ai.content)
            # v0.2.1: 双保险 — 即便 fallback 触发,strip ```json ... ``` fence
            # 不泄漏 markdown JSON 文本到 Chainlit UI
            response = _strip_fenced_json(content)
            _r = extract_reasoning(ai)
            return {
                "messages": [ai],
                "response": response,
                "citations": [],
                "grounded": False,  # 兜底路径无法保证 grounded
                "reasoning": _r.text,
                "reasoning_tokens": _r.tokens,
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