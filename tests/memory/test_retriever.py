"""v0.3.0-beta retriever 测试

覆盖:
- retrieve_relevant_facts top-K 返回(memory_enabled 开关)
- where={"user_id", "is_deleted": False} 过滤
- 命中后 access_count + last_accessed_at 回写
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from yantu.data import db as db_module
from yantu.data import vector_repo
from yantu.data.models import Base, MemoryFact
from yantu.memory.retriever import retrieve_relevant_facts


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    from sqlalchemy import create_engine as _ce
    test_engine = _ce(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    monkeypatch.setattr(db_module, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    # 重置 vector_repo singleton
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


class TestRetrieveRelevantFacts:
    @pytest.mark.asyncio
    async def test_memory_disabled_returns_empty(self, monkeypatch):
        """memory_enabled=False 立即返回空 list"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": False}.get(k, d),
        )
        result = await retrieve_relevant_facts("清华分数线")
        assert result == []

    @pytest.mark.asyncio
    async def test_chroma_returns_facts(self, monkeypatch):
        """Chroma 检索有结果时,retriever 返回格式化 list"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 5}.get(k, d),
        )
        # Mock Chroma search 返回 1 条
        with patch.object(vector_repo, "search") as mock_search:
            mock_search.return_value = [
                {
                    "id": "fact-1",
                    "document": "用户数学较弱",
                    "metadata": {
                        "user_id": "default",
                        "fact_type": "user_attribute",
                        "subject": "数学",
                        "memory_facts_id": "1",
                        "source_thread": "abc",
                        "is_deleted": False,
                        "confidence": 0.9,
                    },
                    "distance": 0.1,
                },
            ]
            result = await retrieve_relevant_facts("数学")

        assert len(result) == 1
        assert result[0]["fact_type"] == "user_attribute"
        assert result[0]["text"] == "用户数学较弱"
        assert result[0]["memory_facts_id"] == 1

    @pytest.mark.asyncio
    async def test_chroma_empty_returns_empty(self, monkeypatch):
        """Chroma 无结果返回 []"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 5}.get(k, d),
        )
        with patch.object(vector_repo, "search", return_value=[]):
            result = await retrieve_relevant_facts("not in db")
        assert result == []

    @pytest.mark.asyncio
    async def test_access_count_increments(self, monkeypatch):
        """命中后回写 access_count + last_accessed_at"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 5}.get(k, d),
        )
        tid = "abc"
        fid = _add_fact(tid, "user_attribute", "用户数学较弱")

        with patch.object(vector_repo, "search") as mock_search:
            mock_search.return_value = [
                {
                    "id": f"fact-{fid}",
                    "document": "用户数学较弱",
                    "metadata": {
                        "user_id": "default",
                        "fact_type": "user_attribute",
                        "subject": "数学",
                        "memory_facts_id": str(fid),
                        "source_thread": tid,
                        "is_deleted": False,
                        "confidence": 0.9,
                    },
                    "distance": 0.1,
                },
            ]
            await retrieve_relevant_facts("数学")

        # 验证 access_count 增加了
        with db_module.session_scope() as s:
            f = s.get(MemoryFact, fid)
            assert f.access_count >= 1
            assert f.last_accessed_at is not None

    @pytest.mark.asyncio
    async def test_uses_default_k(self, monkeypatch):
        """k=None 时读 user_settings.memory_injection_count"""
        import yantu.memory.retriever as ret
        monkeypatch.setattr(
            ret, "get_setting",
            lambda k, d=None: {"memory_enabled": True, "memory_injection_count": 7}.get(k, d),
        )
        with patch.object(vector_repo, "search") as mock_search:
            mock_search.return_value = []
            await retrieve_relevant_facts("test")
        # 验证 k=7 传给 search(全部用 kwargs)
        kwargs = mock_search.call_args.kwargs
        assert kwargs["k"] == 7
