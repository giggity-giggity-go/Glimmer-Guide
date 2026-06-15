"""Embedding 加载 — 缓存到本地"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from yantu.config import settings
from yantu.utils.logger import logger


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """单例:首次加载后缓存在内存 + 磁盘"""
    # 设置 HuggingFace 缓存到本地 models/ 目录
    os.environ.setdefault("HF_HOME", str(settings.embedding_cache_dir))
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(settings.embedding_cache_dir))

    cache = settings.embedding_cache_dir
    cache.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading embedding model: {settings.embedding_model}")
    logger.info(f"Cache dir: {cache}")

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
