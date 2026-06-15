"""Markdown 解析 — 按 # 标题分层切片

策略:
- 维护一个标题栈(`#`/`##`/`###` 等)
- 每段内容归属到最近的标题路径
- 标题路径形如: `# 用户画像 > ## 核心结论 > ### 已知分数`
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from yantu.ingest.chunker import Chunk, chunk_text
from yantu.utils.logger import logger


HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def parse_markdown(path: Path) -> List[Chunk]:
    """解析 markdown,按标题切片"""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []

    # 1. 找到所有 header 位置
    matches = list(HEADER_RE.finditer(text))

    if not matches:
        # 无标题,整体作为一段
        return chunk_text(
            text,
            title_path=path.stem,
            source=str(path),
        )

    # 2. 维护标题栈,逐段处理
    chunks: List[Chunk] = []
    header_stack: List[Tuple[int, str]] = []  # (level, title)

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if not section_text:
            continue

        level = len(m.group(1))
        title = m.group(2).strip()

        # 维护栈:弹出 >= 当前 level 的
        while header_stack and header_stack[-1][0] >= level:
            header_stack.pop()
        header_stack.append((level, title))

        title_path = " > ".join(t for _, t in header_stack)

        sec_chunks = chunk_text(
            section_text,
            title_path=title_path,
            source=str(path),
        )
        for c in sec_chunks:
            c.metadata = {
                "title_path": title_path,
                "source_file": path.name,
                "doc_type": "markdown",
            }
        chunks.extend(sec_chunks)

    logger.info(f"MD {path.name}: {len(matches)} headers → {len(chunks)} chunks")
    return chunks
