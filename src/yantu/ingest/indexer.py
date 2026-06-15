"""索引:Chroma + SQLite 双写"""
from __future__ import annotations

from typing import List

from yantu.data import vector_repo
from yantu.ingest.chunker import Chunk
from yantu.utils.embedder import embed_texts
from yantu.utils.logger import logger


def index_chunks(
    chunks: List[Chunk],
    collection_name: str = "recruit_2026",
) -> int:
    """写入 Chroma。返回成功条数"""
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    ids = [c.chunk_id for c in chunks]
    metadatas = [c.metadata for c in chunks]

    # 1. 嵌入
    logger.info(f"Embedding {len(texts)} chunks...")
    embeddings = embed_texts(texts)

    # 2. 写入 Chroma
    vector_repo.add_documents(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
        collection_name=collection_name,
    )
    return len(chunks)
