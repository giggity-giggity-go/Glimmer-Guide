"""LangGraph 节点用的工具集

复用 yanzhao-mcp 5 个 tool 的 endpoint 实现 + LangChain Tool 包装

v0.2.0 变更 (HB-02):
- 5 个 tool 全部改成 async def + await ep.xxx(...)
- 删除 asyncio.run() 桥接(LangChain ToolNode 可直接 await async tool)
- 补 Google-style docstring(Args/Returns),改善 router LLM 选择精度
"""
from __future__ import annotations

from langchain_core.tools import tool

from yantu.scraper import endpoints as ep


@tool
async def query_school_library(page: int = 1) -> list[dict]:
    """查询研招网院校库列表(分页 20/页)。

    适用场景:用户问"全国有哪些学校"、"X 省有哪些 211"、"查询院校库第 N 页"。
    返回学校名、ID、城市、主管部门、院校特性(985/211/研究生院)。

    Args:
        page: 页码(从 1 开始;每页 20 所;超出范围返回空列表)

    Returns:
        列表,每项含 school_id / name / city / department /
        is_211 / is_985 / is_yanjiusheng_yuan / info_url
    """
    return await ep.query_school_library(page=page)


@tool
async def get_school_info(school_id: str) -> dict:
    """查询院校详情。访问 /sch/schoolInfo--schId-{id}.dhtml。

    适用场景:用户问"某校的招生简章"、"某校的调剂办法"、"X 是 985 吗"、
    "X 在哪个城市"、"X 归谁管"。

    Args:
        school_id: 研招网 schId 数字字符串(从 query_school_library 返回的 school_id 字段)

    Returns:
        dict 含 school_id / name / city / department / badges /
        admission_notices(招生简章链接列表)/ adjust_methods(调剂办法链接列表)
        HTTP 失败时返回 {\"error\": \"status=XXX\"}
    """
    return await ep.get_school_info(school_id=school_id)


@tool
async def get_disciplines() -> list[dict]:
    """查询 14 个学科门类(哲学/经济学/法学/教育学/文学/历史学/理学/工学/农学/医学/军事学/管理学/艺术学/交叉学科)。

    适用场景:用户问"学科门类有哪些"、"专业大类"、"考研学科分类"。
    注:这是硬编码的 14 门类(研招网 /zyk/ 是 Vue SPA),不是实时数据。

    Returns:
        列表,每项含 category(门类名) / code(代码 01-14)
    """
    return await ep.get_disciplines()


@tool
async def get_recruitment_notices(page: int = 1) -> list[dict]:
    """查询全国招生简章列表(分页 80/页)。

    适用场景:用户问"最近哪些学校发了简章"、"2026 全国招生简章"、"X 月新出的简章"。

    Args:
        page: 页码(从 1 开始;每页 80 条;超出范围返回空列表)

    Returns:
        列表,每项含 title / url(完整链接)/ date(原始字符串)/
        date_parsed(ISO 格式日期,可能为 None)
    """
    return await ep.get_recruitment_notices(page=page)


@tool
async def search_local(query: str, k: int = 5) -> list[dict]:
    """本地资料语义检索(Chroma 向量库)。

    适用场景:用户问"复试分数线"、"招生人数"、"报录比"、"X 学校历年分数线"、
    "专业课考什么"。覆盖用户已摄入的 PDF / Markdown / TXT 资料。

    Args:
        query: 中文查询关键词
        k: 返回 top-k(默认 5,最大建议 20)

    Returns:
        列表,每项含 id / document / metadata / distance(cosine distance,越小越相似)
    """
    return await ep.search_local(query=query, k=k)


ALL_TOOLS = [
    query_school_library,
    get_school_info,
    get_disciplines,
    get_recruitment_notices,
    search_local,
]