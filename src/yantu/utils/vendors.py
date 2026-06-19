"""LLM 配置 — 3 层关注点:VENDOR(厂商) / MODEL(模型) / BEHAVIOR(行为)

用法:
  .env 里设 LLM_VENDOR=zhipu|minimax|openai        # 选厂商
  .env 里 (可选) LLM_MODEL=<具体模型>              # 选模型,缺省用 vendor default
  .env 里 (可选) LLM_MODEL_OVERRIDE=...           # 应急逃生口
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from yantu.utils.logger import logger


@dataclass(frozen=True)
class VendorConfig:
    """单个 LLM 厂商的元信息。model 是 resolve 时算出的(可能来自 LLM_MODEL override)。"""
    name: str
    base_url: str
    api_key_env: str
    model: str                          # resolve 后的模型(可能是 vendor default, 也可能是 LLM_MODEL)
    extra_model_kwargs: dict = field(default_factory=dict)


# Layer 1: 厂商列表 — 加新厂商就加一行(model 字段是该 vendor 的默认模型,会被 LLM_MODEL override)
VENDORS: dict[str, VendorConfig] = {
    "zhipu": VendorConfig(
        name="Zhipu GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key_env="LLM_API_KEY",
        model="glm-5.1",
    ),
    "minimax": VendorConfig(
        name="MiniMax",
        base_url="https://api.minimaxi.com/v1",
        api_key_env="LLM_API_KEY",
        model="MiniMax-M2.7",  # 速度优先(英文 thinking 范式 C)
    ),
    "openai": VendorConfig(
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model="o3-mini",
    ),
}

# Layer 3: 模型行为 — 按 model 名查 kwargs(加新模型就加一行)
MODEL_BEHAVIORS: dict[str, dict] = {
    "MiniMax-M3":     {"model_kwargs": {"reasoning_split": True}},  # 范式 B:中文 CoT
    "MiniMax-M2.7":   {"model_kwargs": {}},                         # 范式 C:英文 <think>
    "glm-5.1":        {"model_kwargs": {}},                         # 范式 A:隐藏
    "o3-mini":        {"model_kwargs": {}},                         # 范式 A
    # 以后加:"Qwen3-235B-A22B-Thinking-2507": {"model_kwargs": {"enable_thinking": True}},
}

DEFAULT_VENDOR = "zhipu"
_logged = False


def resolve_vendor() -> VendorConfig:
    """2 层解析:vendor → model → behavior。

    LLM_VENDOR 选厂商(必填,缺省 zhipu)
    LLM_MODEL 选具体模型(可选,缺省 = vendor 的 default_model)
    LLM_MODEL_OVERRIDE / LLM_BASE_URL_OVERRIDE / LLM_API_KEY_OVERRIDE 是逃生口
    """
    global _logged
    vendor_id = (os.getenv("LLM_VENDOR") or DEFAULT_VENDOR).strip().lower()
    if vendor_id not in VENDORS:
        raise ValueError(
            f"Unknown LLM_VENDOR={vendor_id!r}. "
            f"Choose one of: {', '.join(VENDORS)}"
        )
    v = VENDORS[vendor_id]

    # Layer 2: 选 model(LLM_MODEL_OVERRIDE > LLM_MODEL > vendor default)
    model = (
        os.getenv("LLM_MODEL_OVERRIDE")
        or os.getenv("LLM_MODEL")
        or v.model
    )

    # Layer 3: 查 model 行为(按 model 名查 kwargs)
    behavior = MODEL_BEHAVIORS.get(model, {"model_kwargs": {}})

    # Override(逃生口)
    base_url = os.getenv("LLM_BASE_URL_OVERRIDE") or v.base_url

    if not _logged:
        api_key_check = os.getenv("LLM_API_KEY_OVERRIDE") or os.getenv(v.api_key_env, "")
        logger.info(
            f"LLM resolved: vendor={vendor_id} ({v.name}) model={model} "
            f"base_url={base_url} key_present={bool(api_key_check)}"
        )
        _logged = True

    # 返回新的 VendorConfig,model 是 resolve 后的,kwargs 按 model 查
    return VendorConfig(
        name=v.name,
        base_url=base_url,
        api_key_env=v.api_key_env,
        model=model,
        extra_model_kwargs=behavior.get("model_kwargs", {}),
    )
