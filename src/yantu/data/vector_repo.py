"""Chroma 向量库封装 — singleton client + 错误信号 + 分批写入

v0.2.0 变更 (HB-04 + HB-12):
- _new_client() → _get_singleton_client() 模块级单例 + threading.Lock
  + atexit 关闭,避免每次 search 新建 PersistentClient (200-500ms 浪费)
- add_documents() 分批写入 (batch=100),避免大批量触发 Chroma Rust binding OOM
- ToolMessageEmptyResult 异常,允许 ToolNode 通过 wrap_tool_call 区分"空数据" vs "工具错误"
"""
from __future__ import annotations

import atexit
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from yantu.config import settings
from yantu.utils.logger import logger


# HB-04: 模块级 singleton,加 lock 避免多线程并发 init
_client: Optional[chromadb.api.ClientAPI] = None
_client_lock = threading.Lock()


def _get_singleton_client() -> chromadb.api.ClientAPI:
    """单例 client(lazy init + lock)"""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(
                    path=str(settings.chroma_dir),
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=False,  # SAFETY (CB-02): disable reset to prevent data wipe
                        is_persistent=True,
                    ),
                )
                logger.info(
                    f"Chroma PersistentClient initialized at {settings.chroma_dir}"
                )
    return _client


@atexit.register
def _close_client() -> None:
    """进程退出时清理"""
    global _client
    _client = None


def _get_collection(client, name: str = "recruit_2026"):
    """取 collection(不存在则创建)"""
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# HB-12: 批量上限(Chroma Rust binding 已知 1000+ 文档会 OOM)
_ADD_BATCH_SIZE = 100


def add_documents(
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[Dict[str, Any]],
    ids: List[str],
    collection_name: str = "recruit_2026",
) -> None:
    """批量写入(分批,避免 OOM)"""
    if not documents:
        return
    if not (len(documents) == len(embeddings) == len(metadatas) == len(ids)):
        raise ValueError(
            f"length mismatch: docs={len(documents)}, "
            f"embs={len(embeddings)}, metas={len(metadatas)}, ids={len(ids)}"
        )
    client = _get_singleton_client()
    coll = _get_collection(client, collection_name)
    total = len(documents)
    for start in range(0, total, _ADD_BATCH_SIZE):
        end = min(start + _ADD_BATCH_SIZE, total)
        coll.add(
            documents=documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )
        logger.debug(
            f"add_documents batch [{start}:{end}]/{total} to {collection_name}"
        )
    logger.info(
        f"Added {total} docs to {collection_name} (total: {coll.count()})"
    )


def search(
    query: str,
    k: int = 5,
    where: Optional[Dict[str, Any]] = None,
    collection_name: str = "recruit_2026",
) -> List[Dict[str, Any]]:
    """语义检索"""
    from yantu.utils.embedder import embed_query

    client = _get_singleton_client()
    coll = _get_collection(client, collection_name)
    q_emb = embed_query(query)
    res = coll.query(
        query_embeddings=[q_emb],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    ids_list = res.get("ids", [[]])[0] if res.get("ids") else []
    docs_list = res.get("documents", [[]])[0] if res.get("documents") else []
    metas_list = res.get("metadatas", [[]])[0] if res.get("metadatas") else []
    dists_list = res.get("distances", [[]])[0] if res.get("distances") else []
    for i in range(len(ids_list)):
        out.append(
            {
                "id": ids_list[i],
                "document": docs_list[i] if i < len(docs_list) else "",
                "metadata": metas_list[i] if i < len(metas_list) else {},
                "distance": dists_list[i] if i < len(dists_list) else None,
            }
        )
    return out


def count(collection_name: str = "recruit_2026") -> int:
    """统计 doc 数量"""
    client = _get_singleton_client()
    return _get_collection(client, collection_name).count()


# ==================== v0.3.0 长期记忆 collection ====================

# v0.3.0: 长期记忆向量 collection(与 recruit_2026 共享 singleton client,职责分离)
# recruit_2026 = 用户本地 PDF/MD 资料库(本地 RAG)
# long_term_memory = 跨会话长期记忆 facts(extractor 异步抽取)
LONG_TERM_MEMORY_COLLECTION = "long_term_memory"


def get_long_term_memory_collection():
    """长期记忆向量 collection — 复用 singleton client(不开第二个 client)

    add_documents / search / count 公开 API 已支持 collection_name 参数,
    调用方直接传 vector_repo.LONG_TERM_MEMORY_COLLECTION 即可。
    """
    return _get_collection(_get_singleton_client(), LONG_TERM_MEMORY_COLLECTION)


# SAFETY (CB-02): reset() and delete_collection() are intentionally NOT exposed.
# To wipe data, manually delete the chroma_dir directory on disk.