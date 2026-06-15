"""Chroma 向量库封装

集合设计:
- recruit_2026: 招生相关(简章、专业目录、参考书目等)
- notice_2026: 招生简章(从研招网抓的)
- 未来可扩展
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from yantu.config import settings
from yantu.utils.logger import logger

_client: Optional[chromadb.PersistentClient] = None


def get_client() -> chromadb.PersistentClient:
    """单例 Chroma client"""
    global _client
    if _client is None:
        Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        logger.info(f"Chroma client initialized: {settings.chroma_dir}")
    return _client


def get_collection(name: str = "recruit_2026"):
    """取 collection(不存在则创建)"""
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[Dict[str, Any]],
    ids: List[str],
    collection_name: str = "recruit_2026",
) -> None:
    """批量写入"""
    if not documents:
        return
    coll = get_collection(collection_name)
    coll.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)
    logger.info(
        f"Added {len(documents)} docs to {collection_name} "
        f"(total: {coll.count()})"
    )


def search(
    query: str,
    k: int = 5,
    where: Optional[Dict[str, Any]] = None,
    collection_name: str = "recruit_2026",
) -> List[Dict[str, Any]]:
    """语义检索"""
    from yantu.utils.embedder import embed_query

    coll = get_collection(collection_name)
    q_emb = embed_query(query)
    res = coll.query(
        query_embeddings=[q_emb],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    # res 形如 {"ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]]}
    out = []
    for i in range(len(res["ids"][0])):
        out.append(
            {
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i] if res["metadatas"] else {},
                "distance": res["distances"][0][i] if res["distances"] else None,
            }
        )
    return out


def count(collection_name: str = "recruit_2026") -> int:
    """统计 doc 数量"""
    return get_collection(collection_name).count()


def reset(collection_name: str = "recruit_2026") -> None:
    """清空 collection(调试用)"""
    client = get_client()
    client.delete_collection(collection_name)
    logger.warning(f"Collection {collection_name} deleted")
