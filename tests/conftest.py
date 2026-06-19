"""Pytest 配置 + 全局 fixtures

v0.2.0: 测试基础设施(pytest + pytest-asyncio)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 把 src/ 加入 sys.path,所有测试可 import yantu.*
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
sys.path.insert(0, str(_SRC))


# ==================== 环境变量兜底(HB-15: HF_HUB_OFFLINE) ====================

@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """所有测试自动设 HF_HUB_OFFLINE=1,避免 embedder 启动时联网卡 60s"""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_HOME", str(_PROJECT_ROOT / "models"))


# ==================== fixtures ====================

@pytest.fixture
def fresh_vector_repo():
    """重置 vector_repo singleton,让 _get_singleton_client 重新初始化

    注:Settings 是 frozen,无法 monkeypatch chroma_dir。
    本 fixture 只重置 singleton,tests 应该避免写真实文档到 ./data/chroma。
    """
    from yantu.data import vector_repo
    vector_repo._client = None
    vector_repo._CLASSIFIER_CACHE = None  # type: ignore  # HB-05
    yield
    vector_repo._client = None
    vector_repo._CLASSIFIER_CACHE = None  # type: ignore


@pytest.fixture
def fake_messages():
    """构造假的 LangChain messages,用于 should_continue 测试

    真实场景: Human → AI(tool_calls) → Tool*N → AI(tool_calls, 再要一个) [should_continue 被调]
    末位永远是 AI message(tool_calls 或 content),这样 should_continue 才符合真实调用链
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    def _make(ai_with_tool_calls=False, ai_content="", tool_count=0):
        msgs = [HumanMessage(content="test query")]
        # 第一次 router 决定
        msgs.append(AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "r1"}]))
        # 已经跑过的 tool 结果
        for i in range(tool_count):
            msgs.append(ToolMessage(content="ok", tool_call_id=str(i)))
        # 最后一条是 router 的最新决定
        if ai_with_tool_calls:
            msgs.append(AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "r2"}]))
        elif ai_content:
            msgs.append(AIMessage(content=ai_content))
        else:
            # fallback: AI 给最终回复
            msgs.append(AIMessage(content="done"))
        return msgs
    return _make