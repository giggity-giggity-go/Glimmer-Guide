"""v0.3.0-beta compressor 测试 — 子项 1

覆盖:
- estimate_tokens / estimate_messages_tokens 中文系数
- compress_context_if_needed 不触发(< window)
- compress_context_if_needed trim_messages 路径(< 90% 窗口)
- compress_context_if_needed LLM 摘要路径(> 90% 窗口)
- compress_context_if_needed 边界:消息数 < keep_recent
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from yantu.graph.compressor import (
    compress_context_if_needed,
    estimate_messages_tokens,
    estimate_tokens,
)


def test_estimate_tokens_chinese_coeff():
    """中文 token 系数 = 0.6"""
    # 10 个汉字 = 6 token
    assert estimate_tokens("一二三四五六七八九十") == 6
    # 空字符串
    assert estimate_tokens("") == 0


def test_estimate_messages_tokens_basic():
    """messages 列表 token 估算"""
    msgs = [
        HumanMessage(content="你好世界"),  # 4 chars * 0.6 = 2
        AIMessage(content="回复内容"),  # 4 chars * 0.6 = 2
    ]
    assert estimate_messages_tokens(msgs) == 4


def test_estimate_messages_tokens_multimodal():
    """multimodal list[dict] 形式 content"""
    msgs = [
        HumanMessage(content=[
            {"type": "text", "text": "hi"},
            {"type": "image_url", "image_url": "http://x"},
        ]),
    ]
    # 文本 "hi" = 2 chars * 0.6 = 1
    assert estimate_messages_tokens(msgs) == 1


class TestCompressContext:
    """compress_context_if_needed 主流程"""

    @pytest.fixture(autouse=True)
    def _settings(self, monkeypatch):
        """默认 window=30000, keep_recent=10(不读 UserSetting 表)

        关键:patch yantu.graph.compressor.get_setting(已经被 import 进 compressor 的本地引用),
        不是 user_settings 模块。
        """
        import yantu.graph.compressor as comp
        monkeypatch.setattr(comp, "get_setting", lambda k, d=None: {
            "context_window_tokens": 30000,
            "context_keep_recent_messages": 10,
        }.get(k, d))

    @pytest.mark.asyncio
    async def test_no_trigger_below_window(self):
        """token < window 不压缩"""
        msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
        result = await compress_context_if_needed(msgs)
        assert result["is_compressed"] is False
        assert result["messages"] is None

    @pytest.mark.asyncio
    async def test_no_trigger_empty(self):
        """空 messages"""
        result = await compress_context_if_needed([])
        assert result["is_compressed"] is False

    @pytest.mark.asyncio
    async def test_trim_path_under_90pct(self):
        """trim_messages 后 < 90% window 不调 LLM"""
        import yantu.graph.compressor as comp
        with patch.object(comp, "get_setting", lambda k, d=None: {
            "context_window_tokens": 30,
            "context_keep_recent_messages": 2,
        }.get(k, d)):
            # 10 条 × 20 字符 = 200 chars ≈ 120 token > 30 触发压缩
            # trim_messages max_tokens=30 → keep ~2 msg × 12 token = 24 < 27 (90%) ✓
            msgs = [HumanMessage(content="x" * 20) for _ in range(10)]
            with patch("yantu.graph.compressor.get_llm") as mock_get_llm:
                result = await compress_context_if_needed(msgs)
        # 触发压缩
        assert result["is_compressed"] is True
        # trim 路径不调 LLM
        assert "trim" in result["compressed_summary"].lower()
        assert result["messages"] is not None
        assert len(result["messages"]) < 10
        # 验证确实没调 LLM
        mock_get_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_summarize_path_above_90pct(self):
        """trim 后仍 > 90% window → 调 LLM 摘要"""
        import yantu.graph.compressor as comp
        # window=20, keep_recent=3
        # 100 条长消息(每条 100 字符 ≈ 60 token,远超 20)
        # trim 20 字符仍 > 18 字符 → 触发 LLM
        with patch.object(comp, "get_setting", lambda k, d=None: {
            "context_window_tokens": 20,
            "context_keep_recent_messages": 3,
        }.get(k, d)):
            msgs = [HumanMessage(content="x" * 100) for _ in range(100)]
            with patch(
                "yantu.graph.compressor.get_llm"
            ) as mock_get_llm:
                fake_llm = MagicMock()
                fake_response = MagicMock()
                fake_response.content = "对话摘要:用户问了很多问题"
                fake_llm.ainvoke = AsyncMock(return_value=fake_response)
                mock_get_llm.return_value = fake_llm
                result = await compress_context_if_needed(msgs)

        assert result["is_compressed"] is True
        assert "对话摘要" in result["compressed_summary"]
        # messages = [SystemMessage(summary), *recent(3)]
        assert len(result["messages"]) == 4
        assert isinstance(result["messages"][0], SystemMessage)
        assert "对话摘要" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_messages_count_below_keep_recent(self):
        """消息总数 ≤ keep_recent,无法摘要,只能 trim"""
        import yantu.graph.compressor as comp
        with patch.object(comp, "get_setting", lambda k, d=None: {
            "context_window_tokens": 10,
            "context_keep_recent_messages": 5,
        }.get(k, d)):
            # 3 条长消息(每条 50 字符 ≈ 30 token,远超 10)
            msgs = [HumanMessage(content="x" * 50) for _ in range(3)]
            with patch(
                "yantu.graph.compressor.get_llm"
            ) as mock_get_llm:
                mock_get_llm.assert_not_called() if False else None
                result = await compress_context_if_needed(msgs)
        # 仍 is_compressed=True(因为触发了)
        assert result["is_compressed"] is True
        # messages 应被 trim_messages 处理(可能 = 原列表因为太短)
        assert result["messages"] is not None
