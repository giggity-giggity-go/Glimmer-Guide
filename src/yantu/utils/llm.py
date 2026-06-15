"""LLM 封装 — ChatOpenAI 兼容(指向 MiniMax-M3 或其他 OpenAI 兼容服务)"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from yantu.config import settings
from yantu.utils.logger import logger


@lru_cache(maxsize=1)
def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """单例 LLM(可按 temperature 区分)"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        timeout=60.0,
        max_retries=2,
    )


def get_user_profile_prompt() -> str:
    """用户画像注入到 system prompt 顶部"""
    from yantu.data.user_profile import get_profile

    try:
        return get_profile().to_prompt()
    except Exception as e:
        logger.warning(f"Failed to load user profile: {e}")
        return ""
