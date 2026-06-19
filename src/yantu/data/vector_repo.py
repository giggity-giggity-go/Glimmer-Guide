"""Chroma 向量库封装(简化版:无锁,每次新建 client)

注:Chroma 1.5.x 的 Rust bindings 在多线程下崩溃,加锁又死锁。
**安全**: ChromaSettings 启用 `allow_reset=False`,且本模块不暴露 `reset()` / `delete_collection()`,
任何 prompt injection 或代码 bug 都无法清空数据(v0.2.0: CB-02 修复)。

我们的策略:每次新建 client,用完不显式关闭(让进程退出时 GC 清理)。
性能影响可忽略(Chroma client 是薄包装,数据在磁盘)。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from yantu.config import settings
from yantu.utils.logger import logger


def _new_client() -> chromadb.PersistentClient:
    """新建一个 PersistentClient"""
    Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=False,  # SAFETY (CB-02): disable reset to prevent data wipe
            is_persistent=True,
        ),
    )


def _get_collection(client, name: str = "recruit_2026"):
    """取 collection(不存在则创建)"""
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
    client = _new_client()
    coll = _get_collection(client, collection_name)
    coll.add(documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids)
    logger.info(
        f"Added {len(documents)} docs to {collection_name} (total: {coll.count()})"
    )
    # 不调 client.reset() —— 它会清空数据!


def search(
    query: str,
    k: int = 5,
    where: Optional[Dict[str, Any]] = None,
    collection_name: str = "recruit_2026",
) -> List[Dict[str, Any]]:
    """语义检索"""
    from yantu.utils.embedder import embed_query

    client = _new_client()
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
    client = _new_client()
    return _get_collection(client, collection_name).count()


# SAFETY (CB-02): reset() and delete_collection() are intentionally NOT exposed.
# To wipe data, manually delete the chroma_dir directory on disk.
