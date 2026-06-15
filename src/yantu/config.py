"""配置加载 — 从 .env 读取"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

# 项目根目录(本文件 src/yantu/config.py → 上两级)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_temperature: float

    # 数据目录
    data_dir: Path
    seed_dir: Path
    chroma_dir: Path
    sqlite_path: Path

    # 爬虫
    yanzhao_base_url: str
    scraper_min_delay: float
    scraper_max_delay: float
    scraper_user_agent: str

    # Embedding
    embedding_model: str
    embedding_cache_dir: Path

    # Chainlit
    chainlit_host: str
    chainlit_port: int

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT


def load_settings() -> Settings:
    return Settings(
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.MiniMax.com/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "MiniMax-M3"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        data_dir=_path("DATA_DIR", "./data"),
        seed_dir=_path("SEED_DIR", "./seed"),
        chroma_dir=_path("CHROMA_DIR", "./data/chroma"),
        sqlite_path=_path("SQLITE_PATH", "./data/yanzhao.db"),
        yanzhao_base_url=os.getenv("YANZHAO_BASE_URL", "https://yz.chsi.com.cn"),
        scraper_min_delay=float(os.getenv("SCRAPER_MIN_DELAY", "1.5")),
        scraper_max_delay=float(os.getenv("SCRAPER_MAX_DELAY", "3.0")),
        scraper_user_agent=os.getenv(
            "SCRAPER_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
        embedding_cache_dir=_path("EMBEDDING_CACHE_DIR", "./models"),
        chainlit_host=os.getenv("CHAINLIT_HOST", "127.0.0.1"),
        chainlit_port=int(os.getenv("CHAINLIT_PORT", "8000")),
    )


settings = load_settings()
