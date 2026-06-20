"""SessionManager 测试 — v0.3.0 多会话骨架

覆盖:
- thread_id 唯一性(并发创建不重复)
- list_sessions 默认排除 archived
- archive 后 list 不显示 / include_archived=True 显示
- rename 截断到 100 字符
- toggle_pin 翻转
- hard_delete_session 真删 Session 行 + checkpoint
- touch_session 增加 message_count + 更新 updated_at

用临时 SQLite(在 tmp_path fixture),不污染 yantu.db。
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from yantu.data import db as db_module
from yantu.data.models import Base
from yantu.session.manager import (
    archive_session,
    create_session,
    get_session,
    hard_delete_session,
    list_sessions,
    rename_session,
    toggle_pin,
    touch_session,
    unarchive_session,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """每个测试用独立 tmp SQLite,init_db + ensure_checkpointer_tables

    settings 是 frozen dataclass,不能 monkeypatch。
    改用替换 db_module._engine 指向 tmp db(模块加载时 settings.sqlite_path
    只用于初始化 engine,运行时换 engine 已足够隔离测试)。
    """
    db_path = tmp_path / "test.db"
    # 重置模块级 _checkpointer_tables_ready,避免泄漏
    from yantu.graph import agent as agent_mod
    agent_mod._checkpointer_tables_ready = False

    # 重建 engine 指向 tmp
    from sqlalchemy import create_engine as _ce
    test_engine = _ce(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    monkeypatch.setattr(db_module, "_engine", test_engine)
    Base.metadata.create_all(test_engine)
    # checkpointer 表(3 表)— 复用 tmp engine
    cm = __import__("langgraph.checkpoint.sqlite", fromlist=["SqliteSaver"]).SqliteSaver.from_conn_string(str(db_path))
    with cm as saver:
        saver.setup()
    agent_mod._checkpointer_tables_ready = True
    yield
    test_engine.dispose()


# ==================== thread_id 唯一性 ====================


class TestThreadId:
    def test_create_session_returns_8_char_id(self):
        tid = create_session()
        assert len(tid) == 8
        # 16 进制字符
        int(tid, 16)

    def test_thread_ids_unique(self):
        ids = {create_session() for _ in range(50)}
        assert len(ids) == 50, "并发创建 50 个 id 应全部唯一"


# ==================== CRUD 基本 ====================


class TestCRUD:
    def test_create_then_get(self):
        tid = create_session(title="选校")
        sess = get_session(tid)
        assert sess is not None
        assert sess["title"] == "选校"
        assert sess["is_pinned"] is False
        assert sess["is_archived"] is False
        assert sess["message_count"] == 0

    def test_get_nonexistent_returns_none(self):
        assert get_session("deadbeef") is None

    def test_rename_truncate_to_100(self):
        tid = create_session()
        long_title = "x" * 200
        rename_session(tid, long_title)
        assert len(get_session(tid)["title"]) == 100

    def test_rename_nonexistent_returns_false(self):
        assert rename_session("deadbeef", "新标题") is False


# ==================== archive / unarchive ====================


class TestArchive:
    def test_archive_hides_from_default_list(self):
        tid = create_session()
        archive_session(tid)
        # 默认 list 不显示 archived
        assert all(s["thread_id"] != tid for s in list_sessions())
        # include_archived=True 显示
        assert any(s["thread_id"] == tid for s in list_sessions(include_archived=True))

    def test_unarchive_restores_visibility(self):
        tid = create_session()
        archive_session(tid)
        unarchive_session(tid)
        assert any(s["thread_id"] == tid for s in list_sessions())


# ==================== toggle_pin ====================


class TestPin:
    def test_toggle_pin_flips(self):
        tid = create_session()
        assert toggle_pin(tid) is True  # False → True
        assert toggle_pin(tid) is False  # True → False
        assert toggle_pin(tid) is True

    def test_pinned_sorts_first(self):
        tid_normal = create_session(title="普通")
        # 让普通会话 updated_at 更早
        tid_pinned = create_session(title="固定")
        # 把普通会话的 updated_at 改到最新(模拟刚发消息)
        touch_session(tid_normal, 5)
        # 现在固定 pinned=True,正常=False
        toggle_pin(tid_pinned)
        sessions = list_sessions()
        # pinned 应排在 normal 前面
        pinned_idx = next(i for i, s in enumerate(sessions) if s["thread_id"] == tid_pinned)
        normal_idx = next(i for i, s in enumerate(sessions) if s["thread_id"] == tid_normal)
        assert pinned_idx < normal_idx, f"pinned 排序前 {pinned_idx} < normal 排序 {normal_idx}"

    def test_toggle_pin_nonexistent_returns_none(self):
        assert toggle_pin("deadbeef") is None


# ==================== touch_session ====================


class TestTouch:
    def test_touch_increments_message_count(self):
        tid = create_session()
        touch_session(tid, 3)
        touch_session(tid, 2)
        assert get_session(tid)["message_count"] == 5

    def test_touch_updates_updated_at(self):
        tid = create_session()
        sess_before = get_session(tid)
        import time
        time.sleep(0.01)
        touch_session(tid)
        sess_after = get_session(tid)
        assert sess_after["updated_at"] >= sess_before["updated_at"]


# ==================== hard_delete ====================


class TestHardDelete:
    def test_hard_delete_removes_session_row(self):
        tid = create_session()
        assert get_session(tid) is not None
        hard_delete_session(tid)
        assert get_session(tid) is None

    def test_hard_delete_removes_checkpoint_rows(self):
        # v0.3.0-beta:router 是 async,build_agent 用 SqliteSaver(同步),ainvoke 不支持
        # 改用 SqliteSaver.put 直接写一行 checkpoint(测的是 hard_delete 是否清表,不是 agent 流程)
        from langgraph.checkpoint.sqlite import SqliteSaver
        tid = create_session()
        cm = SqliteSaver.from_conn_string(str(db_module._engine.url.database))
        with cm as saver:
            # put_writes + put 都能写,简化为 put
            from langchain_core.runnables import RunnableConfig
            config: RunnableConfig = {"configurable": {"thread_id": tid, "checkpoint_ns": "", "checkpoint_id": "test-cp"}}
            # 用最低 API 写入一个空 checkpoint tuple
            try:
                saver.put(
                    config,
                    {"v": 1, "id": "test-cp", "ts": "2026-06-20T00:00:00Z",
                     "channel_values": {}, "channel_versions": {},
                     "versions_seen": {}, "pending_sends": [],
                     "updated_at": None},
                    {"source": "test", "step": 0, "writes": {}, "parents": {}},
                    {},
                )
            except Exception as e:
                # 写失败不影响 hard_delete 验证,只是没数据可删
                pass
        # 2. checkpoint 行应存在
        from yantu.data.db import _engine
        with _engine.connect() as conn:
            ck_count = conn.execute(
                text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :t"),
                {"t": tid},
            ).scalar()
        assert ck_count >= 1, f"应该有 checkpoint 行,实有 {ck_count}"

        # 3. hard_delete 后,checkpoint 行应清空
        hard_delete_session(tid)
        with _engine.connect() as conn:
            ck_count_after = conn.execute(
                text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :t"),
                {"t": tid},
            ).scalar()
        assert ck_count_after == 0

    def test_hard_delete_nonexistent_returns_false(self):
        assert hard_delete_session("deadbeef") is False


# ==================== 列表边界 ====================


class TestList:
    def test_list_empty_db(self):
        assert list_sessions() == []

    def test_list_limit(self):
        for i in range(5):
            create_session(title=f"会话 {i}")
        sessions = list_sessions(limit=3)
        assert len(sessions) == 3