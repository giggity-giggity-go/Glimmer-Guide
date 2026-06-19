"""HTTP 客户端 — httpx AsyncClient + status-aware throttle (v0.2.0 CB-01/HB-11)

为什么不用 Scrapling 0.4.x:
- Scrapling 0.4.9 强依赖 playwright(导入期 import)
- 用户已明确不需要 Playwright(无登录态)
- 研招网匿名页是静态 HTML,adaptive selector 不是必需的
- 改用 httpx + parsel,语义一致(发送请求 + CSS 选择器),零额外依赖

v0.2.0 变更 (CB-01 + HB-11):
- polite_delay 改成 status-aware:200 时 0-0.2s 抖动;429/503 时强制 1-3s 退避
- _get_client 用 httpx.AsyncClient 单例 + connection pool(替换 sync httpx.Client)
- get() 直接 await,删除 run_in_executor 桥接
- 模块状态 _throttled_until 全局记录,429 自动触发退避窗口
"""
from __future__ import annotations

import asyncio
import random
import time
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


# CB-01: status-aware throttle state
_throttled_until: float = 0.0
_last_status: int = 200


def _record_status(status: int) -> None:
    """记录响应状态,触发/解除退避窗口"""
    global _last_status, _throttled_until
    _last_status = status
    if status in (429, 503):
        # 触发退避窗口(默认 5s)
        _throttled_until = time.time() + settings.scraper_throttle_backoff
        logger.warning(
            f"Throttled (status={status}), backing off "
            f"until {_throttled_until:.1f}"
        )
    elif status == 200 and time.time() > _throttled_until:
        _throttled_until = 0.0


# Per-loop client cache: 解决 bench 用 asyncio.run() 多次创建新 loop 时
# lru_cache 把 AsyncClient 绑死第一个 loop → "Event loop is closed" 的问题
_clients_by_loop: dict[int, httpx.AsyncClient] = {}


def _get_client() -> httpx.AsyncClient:
    """异步 client 单例(按 event loop 缓存)— 带 connection pool,真正复用 keep-alive

    在同一个 event loop 内多次调用复用同一个 client 和连接池;
    跨 event loop 调用(如 bench 用 asyncio.run() 多次)各自新建 client。
    """
    loop = asyncio.get_running_loop()
    key = id(loop)
    if key not in _clients_by_loop:
        _clients_by_loop[key] = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )
    return _clients_by_loop[key]


async def polite_delay(force: bool = False) -> None:
    """status-aware 节流

    - 默认 (200 OK): 0-0.2s 随机抖动(防止突发请求)
    - 退避窗口内 (429/503 后): 强制 1-3s
    - force=True: 无视状态,强制 1-3s
    """
    now = time.time()
    if force or now < _throttled_until:
        delay = random.uniform(settings.scraper_min_delay, settings.scraper_max_delay)
    else:
        # 正常:小抖动
        delay = random.uniform(0.0, 0.2)
    if delay > 0:
        logger.debug(f"Sleeping {delay:.3f}s")
        await asyncio.sleep(delay)


async def get(url: str, params: Optional[dict] = None) -> httpx.Response:
    """异步 GET,带 status-aware 节流"""
    await polite_delay()
    client = _get_client()
    resp = await client.get(url, params=params)
    _record_status(resp.status_code)
    logger.debug(f"GET {url} → {resp.status_code}")
    return resp


async def post(url: str, form: Optional[dict] = None) -> httpx.Response:
    """异步 POST(form-data),带 status-aware 节流"""
    await polite_delay()
    client = _get_client()
    resp = await client.post(url, data=form or {})
    _record_status(resp.status_code)
    logger.debug(f"POST {url} → {resp.status_code}")
    return resp