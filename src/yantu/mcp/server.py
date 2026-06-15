"""yanzhao-mcp server — 5 个 tool 全部匿名可达

5 个 tool:
1. query_school_library — 院校库列表
2. get_school_info — 院校详情
3. get_disciplines — 专业库顶层门类
4. get_recruitment_notices — 全国招生简章
5. search_local — 本地语义检索
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from yantu.scraper import endpoints
from yantu.utils.logger import logger


app = Server("yanzhao-mcp")


TOOL_DEFINITIONS = [
    Tool(
        name="query_school_library",
        description=(
            "查询研招网院校库(yz.chsi.com.cn/sch/)。返回院校列表(分页 20/页),"
            "含学校名、学校 ID、所在地、主管部门、院校特性(双一流/研究生院/自划线)、"
            "详情页 URL。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1, "description": "页码"},
            },
        },
    ),
    Tool(
        name="get_school_info",
        description=(
            "查询院校详情(从 /sch/schoolInfo--schId-{id}.dhtml 匿名获取)。"
            "返回学校名、所在地、主管部门、院校特性、招生简章链接列表、调剂办法链接列表。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "school_id": {"type": "string", "description": "院校 ID(schId)"},
            },
            "required": ["school_id"],
        },
    ),
    Tool(
        name="get_disciplines",
        description=(
            "查询研招网专业库顶层(yz.chsi.com.cn/zyk/)。"
            "返回 14 个学科门类(哲学/经济学/法学/教育学/文学/历史学/理学/工学/农学/医学/军事学/管理学/艺术学/交叉学科)。"
            "详细专业代码字典由本地 Chroma 覆盖。"
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_recruitment_notices",
        description=(
            "查询全国招生简章列表(yz.chsi.com.cn/kyzx/zsjz/)。"
            "分页 80/页,返回标题/URL/日期。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "default": 1, "description": "页码"},
            },
        },
    ),
    Tool(
        name="search_local",
        description=(
            "本地资料语义检索(Chroma 向量库)。"
            "覆盖用户已摄入的招生章程、专业目录、参考书目、冲稳保推荐、调研报告等。"
            "返回 top-k 相似文档片段 + 来源元数据。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询文本"},
                "k": {"type": "integer", "default": 5, "description": "返回 top-k"},
            },
            "required": ["query"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_DEFINITIONS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "query_school_library":
            result = await endpoints.query_school_library(**arguments)
        elif name == "get_school_info":
            result = await endpoints.get_school_info(**arguments)
        elif name == "get_disciplines":
            result = await endpoints.get_disciplines(**arguments)
        elif name == "get_recruitment_notices":
            result = await endpoints.get_recruitment_notices(**arguments)
        elif name == "search_local":
            result = await endpoints.search_local(**arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return [TextContent(type="text", text=text)]
    except Exception as e:
        logger.error(f"Tool {name} error: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def main() -> None:
    """启动 MCP server(stdio transport)"""
    from mcp.server.stdio import stdio_server

    logger.info("yanzhao-mcp starting on stdio...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
