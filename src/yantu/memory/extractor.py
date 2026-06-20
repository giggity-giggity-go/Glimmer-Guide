"""v0.3.0-beta 长期记忆 extractor

每 N 轮对话后(app.py on_message 触发),调 LLM 抽 facts:
1. 调 LLM with structured output(6 种 fact_type schema)
2. 过滤 confidence < 0.7
3. 隐私正则黑名单(身份证/手机号/银行卡)
4. 写 SQLite memory_facts + Chroma long_term_memory + LangMem InMemoryStore

Fire-and-forget:asyncio.create_task,失败只 log warning。
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from yantu.data import vector_repo
from yantu.data.db import session_scope
from yantu.data.models import MemoryFact
from yantu.data.user_settings import get_setting
from yantu.memory.langmem_bridge import add_fact_to_store
from yantu.memory.schemas import (
    MIN_CONFIDENCE,
    FactType,
)
from yantu.utils.embedder import embed_texts
from yantu.utils.llm import get_llm
from yantu.utils.logger import logger


# 隐私黑名单(身份证/手机号/银行卡)— 命中即丢弃
PRIVACY_RE = re.compile(
    r"(?:"  # 非捕获组
    r"\b\d{17}[\dXx]\b"  # 18 位身份证
    r"|"
    r"\b1[3-9]\d{9}\b"  # 11 位手机号
    r"|"
    r"\b\d{16,19}\b"  # 16-19 位银行卡
    r")"
)


_EXTRACT_PROMPT = """你是一个长期记忆抽取助手。从以下对话中提取用户提到的关键事实,返回 JSON list。

每条 fact 必含:
- fact_type:6 种之一
  - user_attribute: 用户固有属性(数学不好 / 目标清华 / 本科 985)
  - preference: 偏好(避开 985 / 喜欢看表格)
  - conversation_outcome: 对话结论(决定考清华)
  - open_question: 未解决问题(下次继续问)
  - person_mention: 提到的人/校/专业
  - timeline_event: 时间事件(10 月报名 / 12 月初试)
- subject:涉及的人/校/专业(可选,空字符串表示无)
- text:自然语言描述,不超过 200 字,保留关键数字和事实
- keywords:3-5 个检索关键词
- confidence:0-1,你的把握度

**重要规则**:
1. 只抽取用户明确表达的事实,不要推测
2. 数字、人名、校名要精确,不要模糊化
3. 同一事实不要重复抽取
4. 隐私信息(身份证号、手机号、银行卡号)直接丢弃,不要抽取
5. 如果对话里没有值得记忆的事实,返回空 list []

**对话**:
{conversation}

**返回格式**:JSON list,例:
[{{"fact_type": "user_attribute", "subject": "数学", "text": "用户数学较弱,自评 60-70 分", "keywords": ["数学", "成绩"], "confidence": 0.9}}]
"""


def _serialize_messages(messages: list[Any]) -> str:
    """messages 列表 → 文本(限长避免 LLM 输入超限)"""
    parts = []
    for m in messages[-10:]:  # 只看最近 10 条
        role = getattr(m, "type", "unknown")
        content = getattr(m, "content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict)
            )
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)[:4000]


def _filter_privacy(text: str) -> bool:
    """命中隐私正则 → True(应丢弃)"""
    return bool(PRIVACY_RE.search(text))


def _parse_llm_output(raw: str) -> list[dict[str, Any]]:
    """解 LLM 输出的 JSON,处理 ```json ... ``` fence(v0.2.1 教训)"""
    if not raw:
        return []
    # 剥 markdown fence
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "facts" in data:
            return data["facts"]
    except json.JSONDecodeError as e:
        logger.warning(f"extractor: JSON parse failed: {e}, raw={raw[:200]!r}")
    return []


async def extract_facts_async(
    thread_id: str,
    messages: list[Any],
    user_id: str = "default",
) -> list[int]:
    """抽 facts,写 SQLite + Chroma + LangMem store,返回写入的 fact_ids

    Args:
        thread_id: 当前会话 thread_id
        messages: 最近 N 条对话(由 app.py 传入)
        user_id: 用户隔离

    Returns:
        写入的 fact id 列表(供 app.py 调试 log)
    """
    if not messages:
        return []
    # 检查总开关
    if not get_setting("memory_enabled", True):
        return []

    serialized = _serialize_messages(messages)
    if not serialized.strip():
        return []

    prompt = _EXTRACT_PROMPT.format(conversation=serialized)
    try:
        llm = get_llm(temperature=0.0)
        result = await llm.ainvoke([HumanMessage(content=prompt)])
    except Exception as e:
        logger.warning(f"extractor: LLM call failed: {e}")
        return []

    raw_output = result.content if hasattr(result, "content") else str(result)
    if isinstance(raw_output, list):
        raw_output = " ".join(
            p.get("text", "") for p in raw_output if isinstance(p, dict)
        )
    facts_raw = _parse_llm_output(raw_output)

    written_ids: list[int] = []
    for f in facts_raw:
        try:
            # 验证 fact_type
            ftype = f.get("fact_type", "")
            if ftype not in (
                "user_attribute", "preference", "conversation_outcome",
                "open_question", "person_mention", "timeline_event",
            ):
                logger.debug(f"extractor: unknown fact_type {ftype!r}, skip")
                continue
            # confidence 过滤
            conf = float(f.get("confidence", 0.5))
            if conf < MIN_CONFIDENCE:
                logger.debug(f"extractor: low confidence {conf}, skip")
                continue
            text = f.get("text", "").strip()
            if not text or _filter_privacy(text):
                logger.debug(f"extractor: privacy or empty text, skip")
                continue

            subject = f.get("subject", "").strip()
            keywords = f.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []

            # 1) 写 SQLite
            with session_scope() as s:
                fact = MemoryFact(
                    user_id=user_id,
                    fact_type=ftype,
                    fact_value={"text": text, "keywords": keywords},
                    subject=subject or None,
                    keywords=keywords,
                    confidence=conf,
                    source_thread=thread_id,
                )
                s.add(fact)
                s.flush()
                fid = fact.id
            written_ids.append(fid)

            # 2) 写 Chroma
            try:
                emb = embed_texts([text])[0]
                vector_repo.add_documents(
                    documents=[text],
                    embeddings=[emb],
                    metadatas=[{
                        "user_id": user_id,
                        "fact_type": ftype,
                        "subject": subject,
                        "memory_facts_id": str(fid),
                        "source_thread": thread_id,
                        "is_deleted": False,
                        "confidence": conf,
                    }],
                    ids=[f"fact-{fid}"],
                    collection_name=vector_repo.LONG_TERM_MEMORY_COLLECTION,
                )
            except Exception as e:
                logger.warning(f"extractor: Chroma write failed for fact {fid}: {e}")

            # 3) 写 LangMem InMemoryStore
            try:
                add_fact_to_store(fid, user_id, {
                    "id": fid,
                    "fact_type": ftype,
                    "text": text,
                    "subject": subject,
                    "keywords": keywords,
                    "confidence": conf,
                    "source_thread": thread_id,
                })
            except Exception as e:
                logger.warning(f"extractor: LangMem store write failed for fact {fid}: {e}")

        except Exception as e:
            logger.warning(f"extractor: fact write failed: {e}, fact={f}")
            continue

    logger.info(
        f"extractor: {len(written_ids)}/{len(facts_raw)} facts written for thread={thread_id}"
    )
    return written_ids


def should_extract(message_count: int) -> bool:
    """判断是否触发抽取(每 N 轮)"""
    n = int(get_setting("memory_extract_every_n_turns", 3))
    if n <= 0:
        return False
    return message_count > 0 and message_count % n == 0
