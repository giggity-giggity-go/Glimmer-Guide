"""PDF 解析 — 用 pypdf 按页提取

元数据提取(基于文件名启发式):
- 学校名:从路径推断(沈阳农业大学/华中师范大学)
- 文档类型:招生章程 / 招生专业目录 / 考试大纲 / 整合方案
- 年份:从文件名 2026 提取
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from pypdf import PdfReader

from yantu.ingest.chunker import Chunk, chunk_text
from yantu.utils.logger import logger


# 文件名关键词 → 文档类型
DOC_TYPE_PATTERNS = [
    (r"招生章程", "admission_charter"),
    (r"招生专业目录", "recruit_catalog"),
    (r"考试大纲", "exam_syllabus"),
    (r"考试科目整合", "subject_merge"),
    (r"参考书目", "reference_books"),
    (r"复试", "retest_rules"),
    (r"附表", "annex"),
]


def _guess_doc_type(filename: str) -> str:
    for pat, t in DOC_TYPE_PATTERNS:
        if re.search(pat, filename):
            return t
    return "unknown"


def _guess_year(filename: str) -> int:
    m = re.search(r"(\d{4})", filename)
    if m:
        return int(m.group(1))
    return 2026


def _guess_school(path: Path) -> str:
    """从父目录名猜学校"""
    p = path
    for _ in range(3):
        if p.parent:
            name = p.parent.name
            if "农业" in name or "华中" in name or "师范" in name or "大学" in name:
                return name
            p = p.parent
    return path.parent.name


def parse_pdf(path: Path) -> List[Chunk]:
    """解析单个 PDF,返回 Chunk 列表(按页切片)"""
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        return []

    doc_type = _guess_doc_type(path.name)
    year = _guess_year(path.name)
    school = _guess_school(path)

    logger.info(f"PDF {path.name}: {len(reader.pages)} pages, type={doc_type}, year={year}")

    chunks: List[Chunk] = []
    for page_idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning(f"Page {page_idx} extract failed: {e}")
            continue
        text = text.strip()
        if not text:
            continue
        title_path = f"[{school} {year} {doc_type}] p.{page_idx + 1}"
        # 单页可能短,直接合并
        page_chunks = chunk_text(
            text,
            title_path=title_path,
            source=str(path),
        )
        for c in page_chunks:
            c.page = page_idx + 1
            c.metadata = {
                "school": school,
                "year": year,
                "doc_type": doc_type,
                "page": page_idx + 1,
                "source_file": path.name,
            }
        chunks.extend(page_chunks)
    return chunks


def parse_text(path: Path) -> List[Chunk]:
    """解析已提取的纯文本(.txt)"""
    text = path.read_text(encoding="utf-8")
    doc_type = _guess_doc_type(path.name)
    year = _guess_year(path.name)
    school = _guess_school(path)
    title_path = f"[{school} {year} {doc_type}]"
    chunks = chunk_text(text, title_path=title_path, source=str(path))
    for c in chunks:
        c.metadata = {
            "school": school,
            "year": year,
            "doc_type": doc_type,
            "source_file": path.name,
        }
    return chunks
