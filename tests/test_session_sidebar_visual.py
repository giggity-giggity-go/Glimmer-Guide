"""v0.3.0 Day 8 SessionSidebar 视觉/行为测试

5 个核心验证:
1. Chainlit 默认 sidebar 隐藏(`default_sidebar_state = "hidden"`)
2. SessionSidebar.jsx 豆包模式(36px + Ctrl K + 折叠 + tooltip)
3. 5 秒轮询
4. pinned/双击重命名/删除/新会话(callAction)
5. JSX 副本同步
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ==================== 1. 配置文件测试 ====================


class TestChainlitConfig:
    """Chainlit config.toml 应该隐藏默认 sidebar"""

    def test_default_sidebar_state_is_hidden(self):
        """[UI] 段 default_sidebar_state = hidden"""
        import tomllib
        with open(_PROJECT_ROOT / ".chainlit" / "config.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["UI"].get("default_sidebar_state") == "hidden", (
            f"default_sidebar_state 应为 'hidden',实际 {config['UI'].get('default_sidebar_state')!r}"
        )

    def test_config_remembers_chat_profiles_name(self):
        """chat_profiles_section_name 保留(回退用)"""
        import tomllib
        with open(_PROJECT_ROOT / ".chainlit" / "config.toml", "rb") as f:
            config = tomllib.load(f)
        assert "chat_profiles_section_name" in config["UI"]


# ==================== 2. JSX 副本同步 ====================


class TestJSXSync:
    """主项目 JSX 和 chainlit 副本必须字节级一致"""

    def test_session_sidebar_identical(self):
        main = (_PROJECT_ROOT / "public" / "elements" / "SessionSidebar.jsx").read_bytes()
        chainlit = (_PROJECT_ROOT / "src" / "yantu" / "ui" / ".chainlit" / "public" / "elements" / "SessionSidebar.jsx").read_bytes()
        assert main == chainlit, "SessionSidebar.jsx 副本不一致"

    def test_memory_panel_identical(self):
        main = (_PROJECT_ROOT / "public" / "elements" / "MemoryPanel.jsx").read_bytes()
        chainlit = (_PROJECT_ROOT / "src" / "yantu" / "ui" / ".chainlit" / "public" / "elements" / "MemoryPanel.jsx").read_bytes()
        assert main == chainlit, "MemoryPanel.jsx 副本不一致"

    def test_profile_editor_identical(self):
        main = (_PROJECT_ROOT / "public" / "elements" / "ProfileEditor.jsx").read_bytes()
        chainlit = (_PROJECT_ROOT / "src" / "yantu" / "ui" / ".chainlit" / "public" / "elements" / "ProfileEditor.jsx").read_bytes()
        assert main == chainlit, "ProfileEditor.jsx 副本不一致"


# ==================== 3. JSX 静态分析(grep 关键模式) ====================


class TestSessionSidebarContent:
    """SessionSidebar.jsx 应该包含 Day 8 必备元素"""

    def setup_method(self):
        self.src = (_PROJECT_ROOT / "public" / "elements" / "SessionSidebar.jsx").read_text(encoding="utf-8")

    def test_has_doubao_logo(self):
        """顶部 logo 文字"""
        assert "研途萤火" in self.src

    def test_has_collapse_button(self):
        """折叠按钮 + collapsed state"""
        assert "setCollapsed" in self.src
        assert "◀" in self.src or "▶" in self.src

    def test_has_ctrl_k_shortcut(self):
        """Ctrl K 快捷键(豆包风格)"""
        assert "Ctrl" in self.src or "ctrl" in self.src
        assert 'key === "k"' in self.src or "key === 'k'" in self.src

    def test_has_onboarding_tooltip(self):
        """onboarding tooltip + sessionStorage 记忆"""
        assert "showTip" in self.src
        assert "sidebar_tip_dismissed" in self.src
        assert "setTimeout" in self.src  # 3s 自动消失

    def test_has_5_call_actions(self):
        """5 个 callAction 全在"""
        for action in ["new_session", "switch_session", "rename_session", "toggle_pin", "delete_session"]:
            assert f'"{action}"' in self.src, f"callAction {action} 缺失"

    def test_has_polling(self):
        """5 秒轮询 /api/sessions"""
        assert "setInterval" in self.src
        assert "5000" in self.src
        assert "/api/sessions" in self.src

    def test_has_pinned_sort(self):
        """pinned 在前 + updated_at DESC 排序"""
        assert "is_pinned" in self.src
        assert "updated_at" in self.src

    def test_has_double_click_rename(self):
        """双击重命名 → inline input"""
        assert "onDoubleClick" in self.src
        assert "editingId" in self.src
        assert "autoFocus" in self.src

    def test_has_delete_confirmation(self):
        """删除二次 confirm"""
        assert "confirm(" in self.src
        assert "delete_session" in self.src

    def test_has_props_global_access(self):
        """react-runner 全局 props(不要函数参数)"""
        # 不能用 (props = {}) 形式,要用 (props && props.xxx)
        assert "props && props" in self.src
        assert "= props.initial" not in self.src or "props && props.initial" in self.src

    def test_doubao_36px_item_height(self):
        """豆包规格 36px 高度"""
        assert "ITEM_HEIGHT = 36" in self.src

    def test_doubao_280px_width(self):
        """豆包规格 280px sidebar 宽"""
        assert "WIDTH = 280" in self.src

    def test_doubao_60px_collapsed(self):
        """Quivr 模式 60px 折叠宽"""
        assert "WIDTH_COLLAPSED = 60" in self.src

    def test_hide_scrollbar(self):
        """滚动条 hover 才显"""
        assert "session-sidebar-list" in self.src
        assert "::-webkit-scrollbar" in self.src
        assert "transparent" in self.src


# ==================== 4. 5 个 callAction action_callback 存在 ====================


class TestActionCallbacks:
    """app.py 必须有 5 个 session action_callback"""

    def test_all_callbacks_registered(self):
        import re
        app_path = _PROJECT_ROOT / "src" / "yantu" / "ui" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        for name in ["new_session_action", "switch_session_action",
                     "rename_session_action", "toggle_pin_action",
                     "delete_session_action"]:
            assert f"def {name}" in src, f"{name} 缺失"
            assert f'@cl.action_callback("{name.replace("_action", "")}")' in src, \
                f"{name} decorator 缺失"

    def test_delete_session_calls_cleanup(self):
        """delete_session 调 cleanup service(3 类 fact 处理)"""
        app_path = _PROJECT_ROOT / "src" / "yantu" / "ui" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        # delete_session_action 内部应 import delete_session_with_memory
        assert "delete_session_with_memory" in src


# ==================== 5. /api/sessions 端点 ====================


class TestAPISessions:
    """/api/sessions 端点存在"""

    def test_endpoint_exists(self):
        app_path = _PROJECT_ROOT / "src" / "yantu" / "ui" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        assert '@chainlit_app.get("/api/sessions")' in src
        assert "list_sessions" in src
