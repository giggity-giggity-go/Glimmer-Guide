"""v0.3.0-beta 端到端集成测试

覆盖 plan 验收清单的 4 个 E2E prompt 场景(Python 层):
1. 35 轮对话 → 触发压缩
2. 跨会话召回(retrieve_relevant_facts)
3. 删除会话 → cleanup service 跑通(3 类 fact 处理)
4. preference 跨会话保留(KEEP 类不被删)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select

from yantu.data import db as db_module
from yantu.data import vector_repo
from yantu.data.models import Base, MemoryFact, Session
from yantu.graph.compressor import compress_context_if_needed
from yantu.memory.retriever import retrieve_relevant_facts
from yantu.session.cleanup import delete_session_with_memory
from yantu.session.manager import create_session


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    from yantu.graph import agent as agent_mod
    agent_mod._checkpointer_tables_ready = False

    from sqlalchemy import create_engine as _ce
    test_engine = _ce(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    monkeypatch.setattr(db_module, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    db_module._migrate_add_deleted_at()
    # checkpointer 3 表
    cm = __import__("langgraph.checkpoint.sqlite", fromlist=["SqliteSaver"]).SqliteSaver.from_conn_string(str(db_path))
    with cm as saver:
        saver.setup()
    agent_mod._checkpointer_tables_ready = True
    # 重置 vector_repo singleton(用真实 chroma 但走 tmp dir 不实际)
    from yantu.data import vector_repo as vr
    vr._client = None
    yield
    test_engine.dispose()
    vr._client = None


def _add_fact(thread_id: str, fact_type: str, text: str, confidence: float = 0.9) -> int:
    with db_module.session_scope() as s:
        f = MemoryFact(
            user_id="default",
            fact_type=fact_type,
            fact_value={"text": text},
            subject=text[:50] if text else None,
            confidence=confidence,
            source_thread=thread_id,
        )
        s.add(f)
        s.flush()
        return f.id


# ==================== E2E #1: 35 轮对话触发压缩 ====================


class TestE2ECompressionTrigger:
    @pytest.mark.asyncio
    async def test_35_rounds_trigger_compression(self, monkeypatch):
        """35 轮对话后,messages 累计 token 超过 window 触发压缩"""
        import yantu.graph.compressor as comp
        # 调小 window 让 35 轮容易触发
        monkeypatch.setattr(
            comp, "get_setting",
            lambda k, d=None: {"context_window_tokens": 200, "context_keep_recent_messages": 5}.get(k, d),
        )
        # 模拟 35 轮对话(每轮 1 个 human + 1 个 ai = 70 条)
        msgs = []
        for i in range(35):
            msgs.append(HumanMessage(content=f"问题 {i}" + "x" * 10))
            msgs.append(AIMessage(content=f"回答 {i}" + "y" * 10))

        result = await compress_context_if_needed(msgs)
        # 应触发压缩
        assert result["is_compressed"] is True
        # 保留最近 5 条原文 + 1 条 summary
        assert result["messages"] is not None
        assert len(result["messages"]) == 6  # 1 SystemMessage + 5 recent


# ==================== E2E #2: 跨会话召回 ====================


class TestE2ECrossSessionRecall:
    @pytest.mark.asyncio
    async def test_recall_fact_from_different_session(self, monkeypatch):
        """会话 A 写了 fact,会话 B 的 query 能召回"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 5}.get(k, d),
        )

        # 会话 A 写一条 user_attribute fact
        tid_a = "session-aaa"
        fid = _add_fact(tid_a, "user_attribute", "用户想去清华读研", confidence=0.95)

        # Mock Chroma search 返回这条 fact
        with patch.object(vector_repo, "search") as mock_search:
            mock_search.return_value = [
                {
                    "id": f"fact-{fid}",
                    "document": "用户想去清华读研",
                    "metadata": {
                        "user_id": "default",
                        "fact_type": "user_attribute",
                        "subject": "清华",
                        "memory_facts_id": str(fid),
                        "source_thread": tid_a,  # 跨会话来源
                        "is_deleted": False,
                        "confidence": 0.95,
                    },
                    "distance": 0.1,
                },
            ]
            # 会话 B 问"我之前说想去哪里"
            facts = await retrieve_relevant_facts("我之前说想去哪里读研")

        assert len(facts) == 1
        assert facts[0]["source_thread"] == tid_a
        assert facts[0]["text"] == "用户想去清华读研"


# ==================== E2E #3: 删除会话 → cleanup 跑通 ====================


class TestE2EDeleteSessionCleanup:
    def test_delete_session_processes_3_fact_classes(self, monkeypatch):
        """删除会话时,3 类 fact 按规则处理"""
        tid = create_session()
        # 写 6 条(每种 fact_type 1 条)
        for ftype in [
            "user_attribute", "preference", "person_mention",
            "open_question", "timeline_event", "conversation_outcome",
        ]:
            _add_fact(tid, ftype, f"测试 {ftype}")

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 1
            result = delete_session_with_memory(tid)

        # 3 类处理:HARD=1, SOFT=2, KEEP=3
        assert result["hard_deleted"] == 1
        assert result["soft_deleted"] == 2
        assert result["kept"] == 3
        assert result["ok"] is True

        # session 没了
        with db_module.session_scope() as s:
            from sqlalchemy import select as sel
            row = s.execute(sel(Session).where(Session.thread_id == tid)).scalar_one_or_none()
            assert row is None


# ==================== E2E #4: preference 跨会话保留 ====================


class TestE2EPreferenceCrossSession:
    def test_preference_preserved_across_session_delete(self, monkeypatch):
        """删会话 A 后,preference fact 仍存在(可被会话 B 召回)"""
        tid_a = "session-pref"
        tid_b = "session-other"
        fid_pref = _add_fact(tid_a, "preference", "用户希望避开 985", confidence=0.9)
        fid_attr = _add_fact(tid_a, "user_attribute", "用户数学较弱", confidence=0.9)
        fid_outcome = _add_fact(tid_a, "conversation_outcome", "用户决定考清华", confidence=0.9)

        # 删会话 A
        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 1
            delete_session_with_memory(tid_a)

        # KEEP 类 2 条(preference + user_attribute)应仍存在
        with db_module.session_scope() as s:
            pref = s.get(MemoryFact, fid_pref)
            attr = s.get(MemoryFact, fid_attr)
            outcome = s.get(MemoryFact, fid_outcome)
        assert pref is not None
        assert attr is not None
        assert pref.is_deleted is False  # preference 不动
        assert attr.is_deleted is False  # user_attribute 不动
        # conversation_outcome 真删了
        assert outcome is None

        # 验证 KEEP 类可被未来会话 B 检索到
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 5}.get(k, d),
        )
        with patch.object(vector_repo, "search") as mock_search:
            mock_search.return_value = [
                {
                    "id": f"fact-{fid_pref}",
                    "document": "用户希望避开 985",
                    "metadata": {
                        "user_id": "default",
                        "fact_type": "preference",
                        "subject": "985",
                        "memory_facts_id": str(fid_pref),
                        "source_thread": tid_a,
                        "is_deleted": False,
                        "confidence": 0.9,
                    },
                    "distance": 0.05,
                },
            ]
            facts = await_retrieve = AsyncMock()
            # 用 await 而不是 AsyncMock 直接
            import asyncio
            facts_result = asyncio.run(retrieve_relevant_facts("我应该避开哪些学校"))
        assert len(facts_result) == 1
        assert facts_result[0]["fact_type"] == "preference"
        assert facts_result[0]["text"] == "用户希望避开 985"
