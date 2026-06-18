"""跨厂商 reasoning 提取 — 统一 3 种范式

范式 A(智谱 GLM / OpenAI o-series):content 干净,只暴露 token 计数
范式 B(MiniMax-M3 + reasoning_split / DeepSeek / Qwen):reasoning 在 additional_kwargs
范式 C(M2.7 / 原始 M3):reasoning 嵌在 content 的 <think>...</think> 块
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.messages import AIMessage


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


@dataclass
class Reasoning:
    """统一表示,无关厂商。"""
    text: str       # 思考文本(可见时)
    tokens: int     # reasoning token 计数(0 = 未知)
    hidden: bool    # 文本不可见,只有 token 数


def extract_reasoning(ai: AIMessage) -> Reasoning:
    """从 AIMessage 抽 reasoning。3 范式都处理。"""
    # 1. token 计数(所有 OpenAI 兼容厂商都会暴露,字段名统一)
    usage = getattr(ai, "usage_metadata", None) or {}
    details = usage.get("output_token_details", {}) if isinstance(usage, dict) else {}
    tokens = int(details.get("reasoning", 0) or 0) if isinstance(details, dict) else 0

    # 2. 范式 C:content 里的 <think> 块
    content = ai.content if isinstance(ai.content, str) else ""
    m = _THINK_RE.search(content)
    inline = m.group(1).strip() if m else ""

    # 3. 范式 B:additional_kwargs.reasoning_content
    split = (ai.additional_kwargs or {}).get("reasoning_content", "").strip()

    # 4. 优先级:范式 B > 范式 C > 范式 A(仅 token)
    if split:
        return Reasoning(split, tokens, hidden=False)
    if inline:
        return Reasoning(inline, tokens, hidden=False)
    if tokens > 0:
        return Reasoning("", tokens, hidden=True)
    return Reasoning("", 0, hidden=False)
