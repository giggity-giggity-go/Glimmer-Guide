"""v0.3.0-beta cleanup service 测试 — 子项 4

覆盖:
- delete_session_with_memory 3 类 fact 处理(HARD/SOFT/KEEP)
- sweep_soft_deleted_facts 30 天物理删
- cleanup 事务顺序(Chroma 在最前,不可逆)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from yantu.data import db as db_module
from yantu.data.models import Base, MemoryFact, Session
from yantu.session.cleanup import (
    HARD_DELETE_FACTS,
    KEEP_FACTS,
    SOFT_DELETE_FACTS,
    delete_session_with_memory,
    sweep_soft_deleted_facts,
)
from yantu.session.manager import create_session, hard_delete_session


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """tmp SQLite,init_db 触发 deleted_at 迁移,checkpointer 建表"""
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
    # 触发 v0.3.0-beta deleted_at 迁移
    db_module._migrate_add_deleted_at()
    # checkpointer 表
    cm = __import__("langgraph.checkpoint.sqlite", fromlist=["SqliteSaver"]).SqliteSaver.from_conn_string(str(db_path))
    with cm as saver:
        saver.setup()
    agent_mod._checkpointer_tables_ready = True
    yield
    test_engine.dispose()


def _add_fact(thread_id: str, fact_type: str, text: str = "test", fact_value: dict | None = None) -> int:
    """helper:写一条 MemoryFact,返回 id"""
    with db_module.session_scope() as s:
        f = MemoryFact(
            user_id="default",
            fact_type=fact_type,
            fact_value=fact_value or {"text": text},
            source_thread=thread_id,
            confidence=0.9,
        )
        s.add(f)
        s.flush()
        return f.id


def _count_facts(thread_id: str) -> dict[str, int]:
    """统计某 thread 各 fact_type 数量(按 is_deleted 分)"""
    with db_module.session_scope() as s:
        rows = s.execute(
            select(MemoryFact).where(MemoryFact.source_thread == thread_id)
        ).scalars().all()
        out: dict[str, int] = {"active": 0, "deleted": 0}
        for f in rows:
            key = "deleted" if f.is_deleted else "active"
            out[key] = out.get(key, 0) + 1
        return out


# ==================== 3 类 fact 处理 ====================


class TestDeleteSessionWithMemory:
    """delete_session_with_memory 主流程"""

    def test_hard_delete_facts(self):
        """conversation_outcome 应被硬删"""
        tid = create_session()
        fid = _add_fact(tid, "conversation_outcome", "决定考清华")

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 1
            result = delete_session_with_memory(tid)

        assert result["ok"] is True
        assert result["hard_deleted"] == 1
        assert result["soft_deleted"] == 0
        assert result["kept"] == 0
        # Chroma 调了一次 where 级联(用 $and 包装)
        mock_vr.delete_facts_where.assert_called_once()
        call_args = mock_vr.delete_facts_where.call_args[0][0]
        # v0.3.0-beta hotfix: 多条件用 $and 包装
        assert "$and" in call_args
        conds = call_args["$and"]
        # 找到 source_thread 和 fact_type 两个条件
        cond_dict = {list(c.keys())[0]: list(c.values())[0] for c in conds}
        assert cond_dict.get("source_thread") == tid
        assert "conversation_outcome" in cond_dict.get("fact_type", {}).get("$in", [])

    def test_soft_delete_facts(self):
        """open_question / timeline_event 应被软删(is_deleted=True,deleted_at 不空)"""
        tid = create_session()
        fid_q = _add_fact(tid, "open_question", "下次继续问招生简章")
        fid_t = _add_fact(tid, "timeline_event", "10 月报名")

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 0
            result = delete_session_with_memory(tid)

        assert result["ok"] is True
        assert result["soft_deleted"] == 2
        assert result["hard_deleted"] == 0
        # 验证 SQLite 状态:soft 删的 fact 仍在(is_deleted=True),30 天后 sweep 物理删
        with db_module.session_scope() as s:
            for fid in [fid_q, fid_t]:
                f = s.get(MemoryFact, fid)
                assert f is not None
                assert f.is_deleted is True
                assert f.deleted_at is not None

    def test_keep_facts_preserved(self):
        """user_attribute / preference / person_mention 应保留"""
        tid = create_session()
        _add_fact(tid, "user_attribute", "数学不好")
        _add_fact(tid, "preference", "避开 985")
        _add_fact(tid, "person_mention", "提到清华")

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 0
            result = delete_session_with_memory(tid)

        assert result["ok"] is True
        assert result["kept"] == 3
        assert result["hard_deleted"] == 0
        assert result["soft_deleted"] == 0
        # KEEP 类的 fact 仍存在,只是 session 关联断了
        # (实际查询会因为 Session 没了而找不到 thread_id,需直接查所有 fact)
        with db_module.session_scope() as s:
            all_kept = s.execute(
                select(MemoryFact).where(
                    MemoryFact.fact_type.in_(KEEP_FACTS)
                )
            ).scalars().all()
        assert len(all_kept) == 3

    def test_mixed_fact_types(self):
        """混合 6 种 fact 一次性处理"""
        tid = create_session()
        _add_fact(tid, "user_attribute")
        _add_fact(tid, "preference")
        _add_fact(tid, "person_mention")
        _add_fact(tid, "open_question")
        _add_fact(tid, "timeline_event")
        _add_fact(tid, "conversation_outcome")

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 1
            result = delete_session_with_memory(tid)

        assert result["hard_deleted"] == 1
        assert result["soft_deleted"] == 2
        assert result["kept"] == 3
        assert result["ok"] is True

    def test_nonexistent_session_returns_false(self):
        """删不存在的会话返回 ok=False"""
        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            result = delete_session_with_memory("deadbeef")
        assert result["ok"] is False

    def test_chroma_called_before_sqlite(self):
        """Chroma 级联先于 SQLite(不可逆放最前)"""
        tid = create_session()
        _add_fact(tid, "conversation_outcome")

        call_order = []
        def mock_chroma_delete(*args, **kwargs):
            call_order.append("chroma")
            return 1
        def mock_sess_delete(*args, **kwargs):
            call_order.append("session")
            return True
        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.side_effect = mock_chroma_delete
            # hard_delete_session 是在函数里 import,patch 它的真正定义模块
            with patch("yantu.session.manager.hard_delete_session", side_effect=mock_sess_delete):
                delete_session_with_memory(tid)
        assert call_order[0] == "chroma"
        assert "session" in call_order

    def test_constants_partition_6_fact_types(self):
        """3 类集合恰好覆盖所有 6 种 fact_type,无遗漏无重复"""
        all_typed = HARD_DELETE_FACTS | SOFT_DELETE_FACTS | KEEP_FACTS
        expected = {
            "user_attribute", "preference", "person_mention",
            "open_question", "timeline_event", "conversation_outcome",
        }
        assert all_typed == expected
        # 无重叠
        assert HARD_DELETE_FACTS.isdisjoint(SOFT_DELETE_FACTS)
        assert HARD_DELETE_FACTS.isdisjoint(KEEP_FACTS)
        assert SOFT_DELETE_FACTS.isdisjoint(KEEP_FACTS)


# ==================== sweep job ====================


class TestSweepSoftDeleted:
    def test_sweep_old_facts(self):
        """30 天前的软删 fact 应被物理删"""
        tid = create_session()
        # 写 3 条,人为改 deleted_at
        ids = [_add_fact(tid, "open_question") for _ in range(3)]
        old_cutoff = datetime.utcnow() - timedelta(days=31)
        with db_module.session_scope() as s:
            for fid in ids:
                f = s.get(MemoryFact, fid)
                f.is_deleted = True
                f.deleted_at = old_cutoff

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 3
            deleted = sweep_soft_deleted_facts(older_than_days=30)

        assert deleted == 3
        # SQLite 物理删
        with db_module.session_scope() as s:
            remaining = s.execute(
                select(MemoryFact).where(MemoryFact.id.in_(ids))
            ).scalars().all()
        assert len(remaining) == 0

    def test_sweep_skips_recent_soft_deleted(self):
        """7 天内的软删 fact 不应被 sweep(在 30 天可恢复窗口内)"""
        tid = create_session()
        fid = _add_fact(tid, "open_question")
        with db_module.session_scope() as s:
            f = s.get(MemoryFact, fid)
            f.is_deleted = True
            f.deleted_at = datetime.utcnow() - timedelta(days=7)

        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            mock_vr.delete_facts_where.return_value = 0
            deleted = sweep_soft_deleted_facts(older_than_days=30)

        assert deleted == 0
        # fact 仍在(仅 is_deleted=True)
        with db_module.session_scope() as s:
            f = s.get(MemoryFact, fid)
            assert f is not None
            assert f.is_deleted is True

    def test_sweep_empty_db_noop(self):
        """空库 sweep 不报错"""
        with patch("yantu.session.cleanup.vector_repo") as mock_vr:
            deleted = sweep_soft_deleted_facts(older_than_days=30)
        assert deleted == 0
        mock_vr.delete_facts_where.assert_not_called()
