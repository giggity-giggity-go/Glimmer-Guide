"""LLM 封装 — 委托厂商注册表 + cache key 含 vendor(HB-13)+ api_key redact(HB-14)

v0.2.0 (HB-13 + HB-14):
- cache key 从 float 改成 (vendor_name, model, temperature) 三元组
  vendor 切换或 model 切换立即生效,不再误用旧 vendor 实例
- api_key 日志显式 redact,任何 debug 调用都不会泄明文

v0.2.2 (vendor 私有参数透传):
- vendor-specific 私有参数(如 MiniMax-M3 的 reasoning_split)走
  ChatOpenAI(extra_body=...) 而不是 model_kwargs=... — LangChain 官方
  警告:model_kwargs 会被合并到 OpenAI SDK 的 create(**kwargs) 顶层签名
  参数,SDK 见非标准参数直接 TypeError。extra_body 走 HTTP body 透传,
  绕过签名校验。
- cache key 加上 frozen(extra_body),否则切 vendor/model 时若新 vendor
  的 extra_body 不同,缓存会返回旧实例导致配置错乱。

vendor registry 是 llm 配置的唯一真相源;`yantu.config.settings` 的
LLM_* 字段保留仅作向后兼容。
"""
from __future__ import annotations

import os
from typing import Tuple

from langchain_openai import ChatOpenAI

from yantu.utils.logger import logger
from yantu.utils.vendors import resolve_vendor


# HB-14: 永远不要 log 完整 api_key
def _redact_key(api_key: str) -> str:
    """只显示前 4 + 后 4 字符,中间 ***"""
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}***{api_key[-4:]}"


# HB-13 + v0.2.2: cache key 包含 vendor + model + temperature + extra_body,
# 切换 vendor/model 或 extra_body 时立即失效
_LLM_CACHE: dict[Tuple[str, str, float, frozenset], ChatOpenAI] = {}


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """单例 LLM(按 (vendor_name, model, temperature, extra_body) 缓存)

    切换 LLM_VENDOR/LLM_MODEL_OVERRIDE 或 MODEL_BEHAVIORS 中对应模型的
    extra_body 后,下次调用会创建新实例,不再误用旧 vendor 的配置。
    """
    v = resolve_vendor()
    t = (
        temperature
        if temperature is not None
        else float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    # v0.2.2: extra_body 加入 cache key — 同 vendor+model+temp 不同 extra_body
    # 也视为不同实例(虽然现在 MODEL_BEHAVIORS 里每 model 只有一份 extra_body,
    # 但未来可能加 model-specific 私有参数)
    body_key = frozenset((v.extra_body or {}).items())
    key = (v.name, v.model, t, body_key)
    if key not in _LLM_CACHE:
        api_key = os.getenv("LLM_API_KEY_OVERRIDE") or os.getenv(v.api_key_env, "")
        if not api_key:
            raise ValueError(
                f"API key missing for vendor {v.name!r}: "
                f"set env var {v.api_key_env} (or LLM_API_KEY_OVERRIDE)"
            )
        logger.info(
            f"Creating ChatOpenAI: vendor={v.name}, model={v.model}, "
            f"base_url={v.base_url}, api_key={_redact_key(api_key)}, "
            f"temperature={t}, extra_body={v.extra_body}"
        )
        _LLM_CACHE[key] = ChatOpenAI(
            model=v.model,
            api_key=api_key,
            base_url=v.base_url,
            temperature=t,
            timeout=60.0,
            max_retries=2,
            # v0.2.2: vendor 私有参数(reasoning_split 等)走 extra_body=
            # 绕过 OpenAI SDK 签名校验,而不是 model_kwargs=
            extra_body=v.extra_body or {},
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