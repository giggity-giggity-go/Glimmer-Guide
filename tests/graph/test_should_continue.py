"""should_continue 单元测试 — HB-01 max iterations"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from yantu.graph.nodes import MAX_TOOL_ROUNDS, should_continue


class TestHB01MaxToolRounds:
    """HB-01: should_continue 加 ToolMessage 计数,>MAX_TOOL_ROUNDS 强制 synthesize"""

    def test_no_messages_returns_synthesize(self):
        assert should_continue({"messages": []}) == "synthesize"

    def test_ai_with_tool_calls_returns_tools(self, fake_messages):
        """AI 带 tool_calls → tools"""
        state = {"messages": fake_messages(ai_with_tool_calls=True)}
        assert should_continue(state) == "tools"

    def test_under_limit_with_tool_calls_returns_tools(self, fake_messages):
        """tool_msg 数 < MAX 但 AI 还想调 tool → tools"""
        state = {"messages": fake_messages(
            ai_with_tool_calls=True,
            tool_count=MAX_TOOL_ROUNDS - 1,
        )}
        assert should_continue(state) == "tools"

    def test_at_limit_forces_synthesize(self, fake_messages):
        """tool_msg 数 ≥ MAX_TOOL_ROUNDS → 强制 synthesize,即使 AI 还想调"""
        state = {"messages": fake_messages(
            ai_with_tool_calls=True,
            tool_count=MAX_TOOL_ROUNDS,
        )}
        result = should_continue(state)
        assert result == "synthesize", (
            f"MAX_TOOL_ROUNDS={MAX_TOOL_ROUNDS} 应该强制 synthesize,got {result}"
        )

    def test_over_limit_forces_synthesize(self, fake_messages):
        """tool_msg 数 > MAX_TOOL_ROUNDS → 强制 synthesize"""
        state = {"messages": fake_messages(
            ai_with_tool_calls=True,
            tool_count=MAX_TOOL_ROUNDS + 3,
        )}
        assert should_continue(state) == "synthesize"

    def test_ai_without_tool_calls_returns_synthesize(self, fake_messages):
        """AI 没有 tool_calls(已给出最终回复) → synthesize"""
        state = {"messages": fake_messages(ai_content="我已经回答了")}
        assert should_continue(state) == "synthesize"

    def test_max_tool_rounds_constant(self):
        """MAX_TOOL_ROUNDS 必须 = 5(防止改坏)"""
        assert MAX_TOOL_ROUNDS == 5, (
            f"MAX_TOOL_ROUNDS 改了?当前={MAX_TOOL_ROUNDS},期望 5"
        )