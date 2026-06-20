"""v0.3.0-beta:上下文自动压缩

策略(spec 5.1 / 5.6 决策):
1. 估算 messages 累计 token(len*0.6 中文系数,避免 tiktoken 准确度坑)
2. < window 不压缩
3. 优先纯 token 裁剪(自实现,langchain trim_messages 在 v1.3 行为变了)
4. 仍 > 90% window → LLM 摘要老消息 + 保留最近 N 条原文,生成 1 条 SystemMessage

调用点:nodes.py router 内 `await compress_context_if_needed(state)`
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from yantu.data.user_settings import get_setting
from yantu.utils.llm import get_llm
from yantu.utils.logger import logger


# 中文 token 系数(避免 tiktoken 准确度坑,spec R-3 风险)
# 实测:中文 1 字符 ≈ 0.6 token(bge 嵌入维度 512 经验值)
_CN_TOKEN_COEFF = 0.6


def estimate_tokens(text: str) -> int:
    """估算字符串 token 数(中文系数)"""
    if not text:
        return 0
    return int(len(text) * _CN_TOKEN_COEFF)


def estimate_messages_tokens(messages: list[Any]) -> int:
    """估算 messages 列表总 token 数"""
    total = 0
    for m in messages:
        content = getattr(m, "content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # multimodal:list of dicts,sum text parts
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"])
    return total


def _trim_to_window(
    messages: list[Any],
    max_tokens: int,
) -> list[Any]:
    """自实现 token 裁剪:从尾部开始保留,直到 token 总和超过 max_tokens

    langchain 1.3.10 的 trim_messages 在测试中未正确裁剪
    (max_tokens=30,12 token/msg,实际未减少),改用自实现。

    Args:
        messages: 消息列表
        max_tokens: 目标 token 上限

    Returns:
        裁剪后的消息列表(可能是空列表如果都超长)
    """
    result = []
    cumulative = 0
    # 从尾部往前累计
    for m in reversed(messages):
        m_tokens = estimate_messages_tokens([m])
        if cumulative + m_tokens > max_tokens and result:
            # 已超,不再加
            break
        result.append(m)
        cumulative += m_tokens
    result.reverse()  # 恢复原序
    return result


async def _llm_summarize(
    old_messages: list[Any],
    keep_last_n: int,
) -> str:
    """调 LLM 摘要老消息,返回 summary 文本(200 字内)"""
    llm = get_llm(temperature=0.0)
    # 拼接老消息文本(避免 SystemMessage 模板导致 LLM 走 chat 路径)
    serialized = []
    for m in old_messages:
        role = getattr(m, "type", "unknown")
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        serialized.append(f"[{role}] {content}")
    conversation = "\n".join(serialized)[:8000]  # 限长避免 LLM 输入超限

    prompt = (
        "将以下对话压缩为不超过 200 字的中文摘要,保留关键事实、数字、决策、"
        "用户偏好。不要添加原对话没有的信息。\n\n"
        f"对话:\n{conversation}\n\n"
        "摘要(200 字内):"
    )
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    summary = result.content if hasattr(result, "content") else str(result)
    if isinstance(summary, list):
        summary = " ".join(
            p.get("text", "") for p in summary if isinstance(p, dict)
        )
    return summary.strip()[:500]  # 限长


async def compress_context_if_needed(
    messages: list[Any],
) -> dict[str, Any]:
    """主入口:超阈值则压缩,返回 state update dict

    Args:
        messages: 当前 state["messages"] 列表

    Returns:
        {
            "is_compressed": bool,
            "compressed_summary": str,  # 空 if not compressed
            "messages": list[Any] | None,  # None = 不改 messages
        }
    """
    if not messages:
        return {"is_compressed": False, "compressed_summary": "", "messages": None}

    window = int(get_setting("context_window_tokens", 30000))
    keep_recent = int(get_setting("context_keep_recent_messages", 10))

    total_tokens = estimate_messages_tokens(messages)
    if total_tokens <= window:
        return {"is_compressed": False, "compressed_summary": "", "messages": None}

    logger.info(
        f"Compressor: total={total_tokens} > window={window}, triggering compression"
    )

    # 阶段 1:纯 token 裁剪
    trimmed = _trim_to_window(messages, max_tokens=window)
    if len(trimmed) < len(messages) and estimate_messages_tokens(trimmed) <= window * 0.9:
        logger.info(
            f"Compressor: trim {len(messages)} → {len(trimmed)} msgs "
            f"({total_tokens} → {estimate_messages_tokens(trimmed)} tokens)"
        )
        return {
            "is_compressed": True,
            "compressed_summary": "[trim] 纯 token 裁剪,无 LLM 调用",
            "messages": trimmed,
        }

    # 阶段 2:LLM 摘要老消息 + 保留最近 N 条
    if len(messages) <= keep_recent:
        # 消息总数不超过 keep_recent,无法再删,只能 trim
        return {
            "is_compressed": True,
            "compressed_summary": "[trim_only] 消息数 < keep_recent,只能 trim",
            "messages": trimmed or messages,
        }

    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]
    summary = await _llm_summarize(old, keep_last_n=keep_recent)
    new_messages = [
        SystemMessage(content=f"[对话摘要]\n{summary}"),
        *recent,
    ]
    new_tokens = estimate_messages_tokens(new_messages)
    logger.info(
        f"Compressor: LLM summarized {len(old)} old msgs, "
        f"tokens {total_tokens} → {new_tokens}"
    )
    return {
        "is_compressed": True,
        "compressed_summary": summary,
        "messages": new_messages,
    }
