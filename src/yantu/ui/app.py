"""Chainlit Web UI — 对话 + 流式 + tool 可视化 + 用户画像编辑面板"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import chainlit as cl
from chainlit.server import app as chainlit_app
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from yantu.data.user_profile import (
    get_profile,
    update_profile,
    export_markdown,
)
from yantu.graph.agent import build_agent
from yantu.graph.nodes import RECURSION_LIMIT
from yantu.ui.reasoning import extract_reasoning
from yantu.utils.embedder import warmup
from yantu.utils.logger import logger


# ==================== 设置页 HTML 模板路径 ====================
SETTINGS_HTML = Path(__file__).parent / "templates" / "settings.html"


# ==================== 推理模型 think 块过滤 ====================
# MiniMax-M3 / DeepSeek-R1 等推理模型会在 content 里吐 <think>...</think>
# 这里在 app 层兜底过滤(避免 Chainlit cot=full 渲染不出来时直接泄露原文)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think(text: str) -> str:
    """去掉 <think>...</think> 思考块,首尾空白顺手 trim"""
    if not text:
        return ""
    cleaned = _THINK_RE.sub("", text)
    return cleaned.strip()


# ==================== 启动时:预热模型 ====================

@cl.on_chat_start
async def start() -> None:
    """每个新会话触发:warmup + 显示用户画像 + 初始化 agent"""
    try:
        warmup()
    except Exception as e:
        logger.warning(f"warmup failed: {e}")

    agent = build_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("thread_id", str(uuid.uuid4())[:8])

    profile = export_markdown()
    await cl.Message(
        content=(
            "👋 你好!我是**研途萤火**,你的个人考研助理。\n\n"
            f"**当前用户画像:**\n```\n{profile}\n```\n"
            "你可以问我:\n"
            "- `CCNU 复试分数线多少?`\n"
            "- `云南农大 招生人数`\n"
            "- `哪些学校避数学?`\n"
            "- `北京大学 信息公开`\n\n"
            "⚙️ 点右上角 **⚙️ 设置** 打开设置页面(分数/偏好/地区/时间轴),改完自动生效。"
        ),
        author="萤火",
    ).send()


# ==================== 命令面板:修改用户画像 ====================

@cl.action_callback("edit_profile")
async def edit_profile(action: cl.Action) -> None:
    """打开编辑表单(ProfileEditor JSX)"""
    profile = get_profile()
    await cl.Message(
        content="**✏️ 编辑用户画像** — 改完点 **💾 保存**:",
        elements=[
            cl.CustomElement(
                name="ProfileEditor",
                props={"initial": profile.model_dump()},
                display="inline",
            )
        ],
        author="设置",
    ).send()


@cl.action_callback("save_profile")
async def save_profile(action: cl.Action) -> None:
    """接收 ProfileEditor 表单提交"""
    try:
        new = update_profile(action.payload or {})
        await cl.Message(
            content=f"✅ 已更新:\n```json\n{new.model_dump_json(indent=2)}\n```"
        ).send()
    except Exception as e:
        await cl.Message(content=f"❌ 保存失败: {e}").send()


@cl.action_callback("reset_profile")
async def reset_profile(action: cl.Action) -> None:
    """重置 profile 到默认值"""
    try:
        from yantu.data.user_profile import reset_profile as _reset

        new = _reset()
        await cl.Message(
            content=f"↩️ 已重置为默认值:\n```json\n{new.model_dump_json(indent=2)}\n```"
        ).send()
    except Exception as e:
        await cl.Message(content=f"❌ 重置失败: {e}").send()


@cl.action_callback("settings")
async def open_settings(action: cl.Action) -> None:
    """chainlit.md [[buttons]] fallback:发送设置页面链接(action 不能直接 navigate)"""
    await cl.Message(
        content=(
            "🔧 **打开设置页面**\n\n"
            "👉 [点这里跳转到 /settings](/settings)\n\n"
            "或者直接点页面右上角的 **⚙️ 设置** 图标。"
        ),
        author="设置",
    ).send()


# ==================== 主对话:LangGraph agent 流式 ====================

@cl.on_message
async def main(message: cl.Message) -> None:
    agent = cl.user_session.get("agent")
    thread_id = cl.user_session.get("thread_id")
    if not agent:
        await cl.Message(content="⚠️ agent 未初始化,请刷新页面").send()
        return

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,  # HB-01: 显式上限,防 GraphRecursionError 500
    }
    user_input = message.content
    inputs = {
        "user_query": user_input,
        "messages": [HumanMessage(content=user_input)],
    }

    # 流式处理 — 只处理 tool step,不累积 LLM token
    # (避免 router 的思考块污染最终输出;synthesizer 的回复从最终 state 读)
    tool_steps: dict[str, cl.Step] = {}

    # HB-17: 包 try/except,LLM 异常时不再 UI 空白,改为显式报错消息
    try:
        async for event in agent.astream_events(inputs, config=config, version="v2"):
        kind = event["event"]
        name = event.get("name", "")
        data = event.get("data", {})

        # Tool 启动:开 step
        if kind == "on_tool_start":
            step = cl.Step(name=name, type="tool")
            step.input = str(data.get("input", {}))
            await step.__aenter__()
            tool_steps[name] = step

        # Tool 结束:写输出,关 step
        elif kind == "on_tool_end":
            step = tool_steps.get(name)
            if step:
                output = str(data.get("output", ""))[:1500]
                step.output = output
                await step.__aexit__(None, None, None)

        # LLM 流式 token:不再累积,统一从 final state 取
        # (旧逻辑会把 router + synthesizer 两个 LLM 的 token 拼一起,
        #  导致 <think> 泄露 + 看起来"回复两次")
    except Exception as e:
        # HB-17: router/synthesizer LLM 失败时显式报错,不再 UI 空白
        logger.exception(f"astream_events failed: {e}")
        await cl.Message(
            content=(
                f"⚠️ 处理失败({type(e).__name__}): {e}\n\n"
                "可能原因:LLM API 限流/超时/内容审查。请稍后重试或检查 .env 配置。"
            ),
            author="萤火",
        ).send()
        return

    # 从最终 state 读 synthesizer 已经存好的 response + reasoning 字段
    final_snapshot = await agent.aget_state(config)
    state_values = final_snapshot.values or {}

    # 渲染推理块 + 答案(cl.CustomElement 必须附属到 message.elements)
    reasoning_text = (state_values.get("reasoning", "") or "").strip()
    reasoning_tokens = state_values.get("reasoning_tokens", 0) or 0
    response_text = _strip_think(state_values.get("response", "") or "")

    # 构建 elements(附属到答案 message)
    elements = []
    if reasoning_text or reasoning_tokens > 0:
        header = f" · 消耗 {reasoning_tokens} tokens" if reasoning_tokens else ""
        elements.append(
            cl.CustomElement(
                name="CollapsibleReasoning",
                props={
                    "title": f"🧠 推理过程{header}",
                    "content": reasoning_text or f"💭 [推理已隐藏,消耗 {reasoning_tokens} tokens]",
                    "defaultOpen": False,
                },
                display="inline",
            )
        )

    # 答案 message(带 reasoning 折叠 element)
    if response_text:
        msg = cl.Message(content=response_text, elements=elements, author="萤火")
        await msg.send()
    else:
        await cl.Message(content="(无响应,请检查 LLM API key)", author="萤火").send()


# ==================== /settings 独立设置页面(挂在 Chainlit FastAPI app) ====================

@chainlit_app.get("/settings")
async def settings_page() -> HTMLResponse:
    """渲染设置表单(预填当前 profile)"""
    profile = get_profile().model_dump()
    html = SETTINGS_HTML.read_text(encoding="utf-8")
    # 占位符放在 <script type="application/json"> 里,前端 parse 出来预填
    html = html.replace("__PROFILE_JSON__", json.dumps(profile, ensure_ascii=False))
    return HTMLResponse(html)


@chainlit_app.post("/settings/save")
async def settings_save(request: Request) -> RedirectResponse:
    """保存表单提交,303 跳回 / 让前端下次 export_markdown() 自然读到新值"""
    payload = await request.json()
    update_profile(payload)
    logger.info(f"Profile updated via /settings/save, payload keys={list(payload.keys())}")
    return RedirectResponse(url="/", status_code=303)


# ==================== 路由优先级修复 ====================
# Chainlit 的 catch-all `/{full_path:path}` 是在 app.include_router(router) 阶段注册的,
# 而我们 `@chainlit_app.get/post` 是在模块加载阶段注册的(更晚)——FastAPI 按注册顺序匹配,
# catch-all 会先匹配上 /settings。手动把我们的路由挪到 _IncludedRouter 前面(FastAPI 的
# routes 是 property,只能 in-place 修改底层 router.routes 列表)。
def _reorder_routes() -> None:
    """把 /settings 路由挪到 Chainlit catch-all 前面

    v0.2.0 (HB-18): 包 try/except + isinstance 检查,Chainlit 升级改名 _IncludedRouter
    也不会让整个 UI 启动崩溃。
    """
    try:
        routes = chainlit_app.router.routes  # 真正的 list
    except AttributeError:
        logger.warning("chainlit_app.router.routes not accessible, skip route reorder")
        return
    settings_routes = [
        r for r in routes
        if isinstance(getattr(r, "path", None), str) and r.path.startswith("/settings")
    ]
    if not settings_routes:
        return
    new_order = []
    inserted = False
    for r in routes:
        # HB-18: 用 isinstance 检查类型,不依赖类名(类名是 Chainlit 内部实现细节)
        if not inserted and type(r).__name__ == "_IncludedRouter":
            new_order.extend(settings_routes)
            inserted = True
        if r not in settings_routes:
            new_order.append(r)
    if not inserted:
        new_order = settings_routes + new_order
    # in-place 重排
    try:
        routes.clear()
        routes.extend(new_order)
    except Exception as e:
        logger.warning(f"route reorder failed (non-fatal): {e}")


_reorder_routes()


# ==================== Chainlit 入口 ====================

def main() -> None:
    """CLI 入口:chainlit run src/yantu/ui/app.py"""
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)


if __name__ == "__main__":
    main()
