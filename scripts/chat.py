"""CLI 烟雾测试入口 — 跟 LangGraph agent 对话"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yantu.graph.agent import build_agent
from yantu.utils.logger import logger


def main() -> None:
    print("=== 研途萤火 CLI 烟雾测试 ===")
    print("输入 'exit' 或 'quit' 退出\n")

    agent = build_agent()
    thread_id = str(uuid.uuid4())[:8]
    config = {"configurable": {"thread_id": thread_id}}
    print(f"thread_id: {thread_id}\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        inputs = {
            "user_query": user_input,
            "messages": [("user", user_input)],
        }
        try:
            for event in agent.stream(inputs, config=config, stream_mode="values"):
                # 打印最近事件
                if "messages" in event and event["messages"]:
                    last = event["messages"][-1]
                    if hasattr(last, "content") and last.content and not getattr(last, "tool_calls", None):
                        print(f"\n萤火: {last.content}\n")
        except Exception as e:
            logger.error(f"Stream error: {e}")
            print(f"\n[错误] {e}\n")


if __name__ == "__main__":
    main()
