"""文本切片 — 中文字符级 512 字 + 64 字 overlap

策略:
- 优先按段落/换行分
- 段落太长则按句号/问号切
- 单 chunk 控制在 [256, 768] 字符区间(避免太短碎片化和太长超过模型限制)
- 保留 title_path(在 md_parser 中维护)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    text: str
    title_path: str = ""  # e.g. "## 三、复试 > 3.1 复试分数线"
    source: str = ""
    page: int | None = None
    chunk_id: str = ""
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    title_path: str = "",
    source: str = "",
    min_size: int = 256,
    max_size: int = 768,
    overlap: int = 64,
) -> List[Chunk]:
    """通用切片(中文字符级)

    Args:
        text: 原文
        title_path: 标题路径(从 md_parser 传入)
        source: 来源文件路径
        min_size: 最小 chunk 字符数
        max_size: 最大 chunk 字符数
        overlap: 跨段重叠字符数
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_size:
        return [
            Chunk(text=text, title_path=title_path, source=source, chunk_id=_mk_id(source, title_path, 0))
        ]

    # 1. 先按段落切
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[Chunk] = []
    buffer = ""
    idx = 0
    for p in paragraphs:
        if not buffer:
            buffer = p
        elif len(buffer) + len(p) + 1 <= max_size:
            buffer = buffer + "\n" + p
        else:
            # flush buffer,start new
            if len(buffer) >= min_size:
                chunks.append(
                    _to_chunk(buffer, title_path, source, idx)
                )
                idx += 1
                # overlap: 取 buffer 末尾 overlap 字
                tail = buffer[-overlap:] if len(buffer) > overlap else ""
                buffer = tail + "\n" + p
            else:
                # buffer 还不够长,继续累积
                buffer = buffer + "\n" + p
        # 如果 buffer 已超 max_size,强制切
        if len(buffer) > max_size:
            for piece in _hard_split(buffer, max_size, overlap):
                chunks.append(_to_chunk(piece, title_path, source, idx))
                idx += 1
            buffer = ""
    if buffer.strip():
        chunks.append(_to_chunk(buffer, title_path, source, idx))
        idx += 1
    return chunks


def _hard_split(text: str, max_size: int, overlap: int) -> List[str]:
    """超长段落硬切"""
    out = []
    start = 0
    while start < len(text):
        end = min(start + max_size, len(text))
        out.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = end
        if end == len(text):
            break
    return out


def _to_chunk(text: str, title_path: str, source: str, idx: int) -> Chunk:
    return Chunk(
        text=text.strip(),
        title_path=title_path,
        source=source,
        chunk_id=_mk_id(source, title_path, idx),
    )


def _mk_id(source: str, title_path: str, idx: int) -> str:
    # 用 hash 简化
    import hashlib

    h = hashlib.md5(f"{source}|{title_path}|{idx}".encode("utf-8")).hexdigest()[:12]
    return h
