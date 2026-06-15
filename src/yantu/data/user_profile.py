"""用户画像持久化 + 热更新

设计目标:
- 单行存储(SQLite JSON 列)
- 运行时修改,LangGraph agent 下一轮对话立即读取新值
- 提供 reset 回到默认值
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from yantu.config import settings
from yantu.data.db import get_engine, init_db, session_scope
from yantu.data.models import UserProfile as PydanticUserProfile
from yantu.data.models import UserProfileRecord

DEFAULT_PATH = settings.seed_dir / "user_profile.default.json"


def _load_default() -> PydanticUserProfile:
    if not DEFAULT_PATH.exists():
        logger.warning(f"Default profile not found: {DEFAULT_PATH}")
        return PydanticUserProfile()
    raw = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    return PydanticUserProfile.model_validate(raw)


def _ensure_row(s: Session) -> UserProfileRecord:
    """保证 user_profile 表里有一行(id=1)"""
    row = s.get(UserProfileRecord, 1)
    if row is None:
        default = _load_default()
        row = UserProfileRecord(id=1, profile_json=default.model_dump(), version=1)
        s.add(row)
        s.flush()
    return row


def init_profile() -> PydanticUserProfile:
    """初始化 user_profile 表(若空则写入默认值)"""
    init_db()
    with session_scope() as s:
        row = _ensure_row(s)
        return PydanticUserProfile.model_validate(row.profile_json)


def get_profile() -> PydanticUserProfile:
    """读取当前用户画像(若空则先初始化)"""
    init_db()
    with session_scope() as s:
        row = s.get(UserProfileRecord, 1)
        if row is None:
            row = _ensure_row(s)
        return PydanticUserProfile.model_validate(row.profile_json)


def update_profile(patch: dict[str, Any]) -> PydanticUserProfile:
    """部分更新(patch 按字段深度合并)"""
    init_db()
    with session_scope() as s:
        row = _ensure_row(s)
        current = PydanticUserProfile.model_validate(row.profile_json)
        merged = _deep_merge(current.model_dump(), patch)
        new_profile = PydanticUserProfile.model_validate(merged)
        row.profile_json = new_profile.model_dump()
        row.version = (row.version or 0) + 1
        s.flush()
        logger.info(f"Profile updated, version={row.version}")
        return new_profile


def reset_profile() -> PydanticUserProfile:
    """重置为默认值"""
    default = _load_default()
    init_db()
    with session_scope() as s:
        row = _ensure_row(s)
        row.profile_json = default.model_dump()
        row.version = (row.version or 0) + 1
        s.flush()
    return default


def export_markdown() -> str:
    """渲染为可读 markdown 报告"""
    p = get_profile()
    return p.to_prompt()


def _deep_merge(base: dict, patch: dict) -> dict:
    """深度合并,patch 覆盖 base"""
    out = dict(base)
    for k, v in patch.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
