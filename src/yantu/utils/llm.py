"""LLM 封装 — ChatOpenAI 兼容(指向 MiniMax-M3 或其他 OpenAI 兼容服务)

v0.2.0 变更 (HB-13 + HB-14):
- cache key 从 float 改成 (model, base_url, api_key_prefix, temperature)
  四元组 — vendor 切换或 api_key 换了立即生效,不再误用旧实例
- api_key 日志显式 redact,任何 debug 调用都不会泄明文
"""
from __future__ import annotations

from typing import Tuple

from langchain_openai import ChatOpenAI

from yantu.config import settings
from yantu.utils.logger import logger


# HB-14: 永远不要 log 完整 api_key
def _redact_key(api_key: str) -> str:
    """只显示前 4 + 后 4 字符,中间 ***"""
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}***{api_key[-4:]}"


# HB-13: cache key 包含 vendor-identifying fields,热切换/换 key 立即生效
_LLM_CACHE: dict[Tuple[str, str, str, float], ChatOpenAI] = {}


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """单例 LLM(按 (model, base_url, api_key_prefix, temperature) 缓存)

    切换 .env 中的 LLM_MODEL / LLM_BASE_URL / LLM_API_KEY / LLM_TEMPERATURE
    后,下次调用会创建新实例,不再误用旧 vendor 的配置。
    """
    temp = temperature if temperature is not None else settings.llm_temperature
    key = (
        settings.llm_model,
        settings.llm_base_url,
        settings.llm_api_key[:8] if settings.llm_api_key else "",
        temp,
    )
    if key not in _LLM_CACHE:
        logger.info(
            f"Creating ChatOpenAI: model={settings.llm_model}, "
            f"base_url={settings.llm_base_url}, "
            f"api_key={_redact_key(settings.llm_api_key)}, "
            f"temperature={temp}"
        )
        _LLM_CACHE[key] = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=temp,
            timeout=60.0,
            max_retries=2,
        )
    return _LLM_CACHE[key]


def get_user_profile_prompt() -> str:
    """用户画像注入到 system prompt 顶部"""
    from yantu.data.user_profile import get_profile

    try:
        return get_profile().to_prompt()
    except Exception as e:
        logger.warning(f"Failed to load user profile: {e}")
        return ""