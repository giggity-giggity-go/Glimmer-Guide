"""Chainlit Web UI — 对话 + 流式 + tool 可视化 + 用户画像编辑面板"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import chainlit as cl
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from yantu.data.user_profile import (
    get_profile,
    update_profile,
    export_markdown,
)
from yantu.graph.agent import build_agent
from yantu.utils.embedder import warmup
from yantu.utils.logger import logger


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
            "⚙️ 点左下角**Settings** 修改用户画像(分数/偏好/目标),立即生效。"
        ),
        author="萤火",
    ).send()


# ==================== 命令面板:修改用户画像 ====================

@cl.action_callback("edit_profile")
async def edit_profile(action: cl.Action) -> None:
    """打开编辑表单"""
    profile = get_profile()
    res = await cl.AskUserMessage(
        content=(
            "请粘贴要修改的 JSON(只填要改的字段):\n"
            "示例:`{\"scores\": {\"math\": 35}, \"preferences\": {\"avoid_math\": true}}`\n\n"
            f"当前:```\n{profile.model_dump_json(indent=2)}\n```"
        ),
        timeout=300,
    ).send()
    if res:
        try:
            import json
            patch = json.loads(res["output"])
            new = update_profile(patch)
            await cl.Message(content=f"✅ 已更新:\n```\n{new.model_dump_json(indent=2)}\n```").send()
        except Exception as e:
            await cl.Message(content=f"❌ JSON 解析失败: {e}").send()


# ==================== 主对话:LangGraph agent 流式 ====================

@cl.on_message
async def main(message: cl.Message) -> None:
    agent = cl.user_session.get("agent")
    thread_id = cl.user_session.get("thread_id")
    if not agent:
        await cl.Message(content="⚠️ agent 未初始化,请刷新页面").send()
        return

    config = {"configurable": {"thread_id": thread_id}}
    user_input = message.content
    inputs = {
        "user_query": user_input,
        "messages": [HumanMessage(content=user_input)],
    }

    # 流式处理
    final_text = ""
    tool_steps: dict[str, cl.Step] = {}

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

        # LLM 流式 token
        elif kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk and hasattr(chunk, "content") and isinstance(chunk.content, str):
                final_text += chunk.content
                # 累积到 msg(简化处理,UI 一次性输出)
        # 跳过其他事件

    # 输出最终回答
    if final_text:
        await cl.Message(content=final_text, author="萤火").send()
    else:
        await cl.Message(content="(无响应,请检查 LLM API key)", author="萤火").send()


# ==================== Chainlit 入口 ====================

def main() -> None:
    """CLI 入口:chainlit run src/yantu/ui/app.py"""
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)


if __name__ == "__main__":
    main()
