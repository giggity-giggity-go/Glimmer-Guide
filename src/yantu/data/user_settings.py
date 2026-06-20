"""v0.3.0-beta:UserSetting 表 CRUD helper

单行 id="default",所有设置都集中在这行。
get_/update_ 函数都是同步(SQLAlchemy session_scope 已是同步),
不引入 async 复杂度。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from yantu.data.db import session_scope
from yantu.data.models import UserSetting
from yantu.utils.logger import logger


def _ensure_row() -> None:
    """确保单行 id="default" 存在(初次访问时创建)"""
    with session_scope() as s:
        existing = s.get(UserSetting, "default")
        if existing is None:
            s.add(UserSetting(id="default"))
            logger.info("Created default UserSetting row")


def get_all_settings() -> dict[str, Any]:
    """返回所有 UserSetting 字段(JSX 用)"""
    _ensure_row()
    with session_scope() as s:
        row = s.get(UserSetting, "default")
        return {
            "context_window_tokens": row.context_window_tokens,
            "context_keep_recent_messages": row.context_keep_recent_messages,
            "memory_enabled": row.memory_enabled,
            "memory_injection_count": row.memory_injection_count,
            "memory_extract_every_n_turns": row.memory_extract_every_n_turns,
            "sidebar_default_view": row.sidebar_default_view,
        }


def get_setting(key: str, default: Any = None) -> Any:
    """读单个设置,缺 key 返回 default

    Args:
        key: 字段名,如 "context_window_tokens"
        default: 表里没这行或字段为 None 时返回
    """
    _ensure_row()
    with session_scope() as s:
        row = s.get(UserSetting, "default")
        if row is None:
            return default
        value = getattr(row, key, None)
        return value if value is not None else default


def update_setting(key: str, value: Any) -> None:
    """更新单个设置

    Args:
        key: 字段名(必须存在于 UserSetting 模型)
        value: 新值
    """
    if not hasattr(UserSetting, key):
        raise ValueError(f"UserSetting has no field {key!r}")
    _ensure_row()
    with session_scope() as s:
        row = s.get(UserSetting, "default")
        setattr(row, key, value)
    logger.info(f"UserSetting.{key} = {value!r}")


def update_settings(**kwargs: Any) -> None:
    """批量更新(JSX 滑块一次保存多个字段)"""
    for k in kwargs:
        if not hasattr(UserSetting, k):
            raise ValueError(f"UserSetting has no field {k!r}")
    _ensure_row()
    with session_scope() as s:
        row = s.get(UserSetting, "default")
        for k, v in kwargs.items():
            setattr(row, k, v)
    logger.info(f"UserSetting updated: {kwargs}")
