"""扫描 seed/ 目录,分发到对应 parser"""
from __future__ import annotations

from pathlib import Path
from typing import List

from yantu.config import settings
from yantu.ingest import md_parser, pdf_parser
from yantu.ingest.chunker import Chunk
from yantu.ingest.indexer import index_chunks
from yantu.utils.logger import logger


def scan_seed() -> List[Path]:
    """返回所有可解析的文件路径"""
    seed = settings.seed_dir
    if not seed.exists():
        logger.warning(f"seed directory not found: {seed}")
        return []
    files: List[Path] = []
    for path in seed.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".pdf", ".md", ".txt"}:
            if path.name == "user_profile.default.json":
                continue  # 不索引用户画像
            files.append(path)
    return sorted(files)


def parse_file(path: Path) -> List[Chunk]:
    """根据扩展名分发"""
    suf = path.suffix.lower()
    if suf == ".pdf":
        return pdf_parser.parse_pdf(path)
    elif suf == ".md":
        return md_parser.parse_markdown(path)
    elif suf == ".txt":
        return pdf_parser.parse_text(path)
    return []


def ingest_seed() -> dict:
    """主入口:扫描 + 解析 + 索引,返回统计"""
    files = scan_seed()
    logger.info(f"Found {len(files)} files in {settings.seed_dir}")
    stats = {"files": len(files), "chunks": 0, "by_file": {}}
    for f in files:
        chunks = parse_file(f)
        n = index_chunks(chunks)
        stats["chunks"] += n
        stats["by_file"][f.name] = n
        logger.info(f"  {f.name}: {n} chunks")
    return stats
