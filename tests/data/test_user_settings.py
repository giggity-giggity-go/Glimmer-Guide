"""v0.3.0-beta user_settings helper 测试"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from yantu.data import db as db_module
from yantu.data.models import Base, UserSetting
from yantu.data.user_settings import (
    get_all_settings,
    get_setting,
    update_setting,
    update_settings,
)


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
    yield
    test_engine.dispose()


class TestUserSettings:
    def test_get_default_when_no_row(self):
        """表空时返回 default"""
        assert get_setting("context_window_tokens", 30000) == 30000
        # 副作用:调用后单行被创建
        with db_module.session_scope() as s:
            row = s.get(UserSetting, "default")
            assert row is not None
            assert row.context_window_tokens == 30000

    def test_update_then_get(self):
        """更新后读到新值"""
        update_setting("context_window_tokens", 50000)
        assert get_setting("context_window_tokens", 30000) == 50000

    def test_get_setting_returns_default_for_missing_attr(self):
        """get_setting 不存在的字段返回传入的 default(无异常)"""
        # get_setting 用 getattr,字段不存在返回 default
        # 这里测一个实际场景:从没设过的字段
        result = get_setting("never_set_field", "fallback")
        assert result == "fallback"

    def test_get_all_settings_keys(self):
        """get_all_settings 返回 6 个字段"""
        all_s = get_all_settings()
        expected = {
            "context_window_tokens",
            "context_keep_recent_messages",
            "memory_enabled",
            "memory_injection_count",
            "memory_extract_every_n_turns",
            "sidebar_default_view",
        }
        assert set(all_s.keys()) == expected

    def test_update_settings_batch(self):
        """批量更新"""
        update_settings(
            context_window_tokens=60000,
            context_keep_recent_messages=15,
            memory_enabled=False,
        )
        s = get_all_settings()
        assert s["context_window_tokens"] == 60000
        assert s["context_keep_recent_messages"] == 15
        assert s["memory_enabled"] is False

    def test_update_setting_validates_field(self):
        """update_setting 拒绝未声明的字段"""
        with pytest.raises(ValueError, match="no field"):
            update_setting("hack_field", 123)

    def test_default_values_after_ensure(self):
        """首次创建行后,所有字段都是模型声明的 default"""
        update_setting("context_window_tokens", 1)  # 触发 _ensure_row
        with db_module.session_scope() as s:
            row = s.get(UserSetting, "default")
            assert row.context_keep_recent_messages == 10  # model default
            assert row.memory_injection_count == 10
            assert row.memory_extract_every_n_turns == 3
            assert row.sidebar_default_view == "recent"
