"""Embedding 加载 — 缓存到本地

v0.2.0 变更 (HB-15):
- 模块 import 时立刻 setdefault HF_HUB_OFFLINE=1 + TRANSFORMERS_OFFLINE=1,
  确保 SentenceTransformer 在 lru_cache 触发前不会再尝试联网 metadata check
  (老代码在 _get_model 函数内 setdefault,如果用户没传 env var 进来会卡 60s+)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

# HB-15: 必须在 import 任何 sentence_transformers 之前 setdefault,
# 否则 _get_model() 触发时 SentenceTransformer 构造函数会先尝试 HEAD 联网检查
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", str(_PROJECT_ROOT / "models"))
os.environ.setdefault(
    "SENTENCE_TRANSFORMERS_HOME",
    str(_PROJECT_ROOT / "models"),
)

from sentence_transformers import SentenceTransformer

from yantu.config import settings
from yantu.utils.logger import logger


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """单例:首次加载后缓存在内存 + 磁盘"""
    cache = settings.embedding_cache_dir
    cache.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading embedding model: {settings.embedding_model}")
    logger.info(f"Cache dir: {cache}")
    logger.debug(
        f"HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE')}, "
        f"TRANSFORMERS_OFFLINE={os.environ.get('TRANSFORMERS_OFFLINE')}"
    )

    model = SentenceTransformer(
        settings.embedding_model,
        cache_folder=str(cache),
        device="cpu",  # bge-small CPU 跑得动,GPU 没必要
    )
    logger.info(f"Model loaded, dim={model.get_embedding_dimension()}")
    return model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量编码"""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(query: str) -> List[float]:
    """单查询编码(与 embed_texts 一致语义)"""
    return embed_texts([query])[0]


def warmup() -> None:
    """预热(Phase 1 验证时调用,确保模型加载成功)"""
    _get_model()