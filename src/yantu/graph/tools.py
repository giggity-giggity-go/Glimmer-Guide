"""LangGraph 节点用的工具集

复用 yanzhao-mcp 5 个 tool 的 endpoint 实现 + LangChain Tool 包装
"""
from __future__ import annotations

from langchain_core.tools import tool

from yantu.scraper import endpoints as ep


@tool
def query_school_library(page: int = 1) -> list[dict]:
    """查询研招网院校库列表(分页 20/页)。返回学校名、ID、城市、主管部门、院校特性。"""
    import asyncio
    return asyncio.run(ep.query_school_library(page=page))


@tool
def get_school_info(school_id: str) -> dict:
    """查询院校详情。从 /sch/schoolInfo--schId-{id}.dhtml 匿名获取。

    Args:
        school_id: 院校 ID(schId)
    """
    import asyncio
    return asyncio.run(ep.get_school_info(school_id=school_id))


@tool
def get_disciplines() -> list[dict]:
    """查询 14 个学科门类(哲学/经济学/.../交叉学科)。返回门类名 + 代码。"""
    import asyncio
    return asyncio.run(ep.get_disciplines())


@tool
def get_recruitment_notices(page: int = 1) -> list[dict]:
    """查询全国招生简章列表(分页 80/页)。返回标题/URL/日期。"""
    import asyncio
    return asyncio.run(ep.get_recruitment_notices(page=page))


@tool
def search_local(query: str, k: int = 5) -> list[dict]:
    """本地资料语义检索(Chroma 向量库)。覆盖用户已摄入的 PDF / Markdown 资料。

    Args:
        query: 中文查询
        k: 返回 top-k
    """
    import asyncio
    return asyncio.run(ep.search_local(query=query, k=k))


ALL_TOOLS = [
    query_school_library,
    get_school_info,
    get_disciplines,
    get_recruitment_notices,
    search_local,
]
