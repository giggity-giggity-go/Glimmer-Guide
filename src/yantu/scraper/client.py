"""HTTP 客户端 — httpx + 1-3s 随机间隔

为什么不用 Scrapling 0.4.x:
- Scrapling 0.4.9 强依赖 playwright(导入期 import)
- 用户已明确不需要 Playwright(无登录态)
- 研招网匿名页是静态 HTML,adaptive selector 不是必需的
- 改用 httpx + parsel,语义一致(发送请求 + CSS 选择器),零额外依赖
"""
from __future__ import annotations

import asyncio
import random
from functools import lru_cache
from typing import Optional

import httpx

from yantu.config import settings
from yantu.utils.logger import logger


DEFAULT_HEADERS = {
    "User-Agent": settings.scraper_user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": f"{settings.yanzhao_base_url}/zsml/",
}


@lru_cache(maxsize=1)
def _get_client() -> httpx.Client:
    return httpx.Client(
        headers=DEFAULT_HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )


async def polite_delay() -> None:
    """1-3s 随机间隔(防止 IP 限速)"""
    delay = random.uniform(settings.scraper_min_delay, settings.scraper_max_delay)
    logger.debug(f"Sleeping {delay:.2f}s")
    await asyncio.sleep(delay)


async def get(url: str, params: Optional[dict] = None) -> httpx.Response:
    """异步 GET,带 1-3s 间隔"""
    await polite_delay()
    client = _get_client()
    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        None, lambda: client.get(url, params=params)
    )
    logger.debug(f"GET {url} → {resp.status_code}")
    return resp


async def post(url: str, form: Optional[dict] = None) -> httpx.Response:
    """异步 POST(form-data),带 1-3s 间隔"""
    await polite_delay()
    client = _get_client()
    loop = asyncio.get_running_loop()
    resp = await loop.run_in_executor(
        None, lambda: client.post(url, data=form or {})
    )
    logger.debug(f"POST {url} → {resp.status_code}")
    return resp
