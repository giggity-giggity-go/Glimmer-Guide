"""入口脚本:扫描 seed/ → 解析 → 索引"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 src/ 加到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yantu.ingest.seed_loader import ingest_seed
from yantu.data.vector_repo import count
from yantu.utils.logger import logger


def main() -> None:
    logger.info("=== 启动数据摄入 ===")
    stats = ingest_seed()
    logger.info(f"=== 摄入完成: {stats['files']} 文件, {stats['chunks']} 切片 ===")
    logger.info(f"=== Chroma 中现存 doc 数: {count()} ===")
    for fname, n in stats["by_file"].items():
        print(f"  {fname}: {n} chunks")


if __name__ == "__main__":
    main()
