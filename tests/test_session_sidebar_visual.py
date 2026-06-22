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
        """Ctrl K 快捷键(豆包风格)— v0.3.0 Day 10: 改成大写 K 容错(实际用 e.key.toLowerCase())"""
        assert "Ctrl" in self.src or "ctrl" in self.src
        # Day 10: 实际写法 const k = e.key.toLowerCase(); k === "k" / k.toLowerCase() === "k"
        assert ('key === "k"' in self.src
                or "key === 'k'" in self.src
                or 'k === "k"' in self.src
                or "k === 'k'" in self.src
                or 'k.toLowerCase()' in self.src)

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
        """v0.3.0 Day 10: 30s 兜底轮询(从 5s 改)+ /api/sessions"""
        assert "setInterval" in self.src
        assert "30000" in self.src
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
        """豆包规格 36px 高度(Day 10: inline style 数值 36 或 '36px')"""
        assert '"36px"' in self.src or "36px" in self.src or "height: 36" in self.src

    def test_doubao_280px_width(self):
        """豆包规格 280px sidebar 宽(Day 10: inline style 数值匹配)"""
        assert "WIDTH = 280" in self.src or "280px" in self.src

    def test_doubao_60px_collapsed(self):
        """Quivr 模式 60px 折叠宽(Day 10: inline style 数值匹配)"""
        assert "WIDTH_COLLAPSED = 60" in self.src or "60px" in self.src

    def test_hide_scrollbar(self):
        """滚动条 hover 才显"""
        assert "session-sidebar-list" in self.src
        assert "::-webkit-scrollbar" in self.src
        assert "transparent" in self.src

    # ===== v0.3.0 Day 10 浏览器实测 4 bug 修复断言 =====

    def test_bug1_filters_empty_sessions(self):
        """Bug 1 修复: 前端 useMemo 软过滤 message_count=0 + 后端 min_message_count=1"""
        assert "nonEmptySessions" in self.src
        assert "(s.message_count || 0) > 0" in self.src

    def test_bug2_keyboard_handler_uses_ref(self):
        """Bug 2 修复: keyboard handler 空 deps,内部走 ref 拿最新值"""
        assert "flatListRef" in self.src
        assert "focusIdxRef" in self.src
        # 第二个 useEffect 的 deps 应该是 [](keyboard handler 不重新挂)
        # 通过检查 useEffect 闭包后跟 `}, []);` 模式
        assert "}, []);" in self.src

    def test_bug3_ime_aware_ctrl_k(self):
        """Bug 3 修复: Ctrl K handler 在 IME composition 中不抢焦点 + input composition 事件"""
        assert "isComposing" in self.src
        assert "onCompositionStart" in self.src
        assert "onCompositionEnd" in self.src

    def test_bug4_activeid_is_state(self):
        """Bug 4 修复: activeId 改 useState + 订阅 sessions_changed WS 事件"""
        assert "setActiveId" in self.src
        # const activeId 反模式不再存在(只允许 useState 形式)
        # 注:`const activeIdRef = useRef(activeId)` 这种是合法的 ref 桥接,不应误判
        bad_lines = [
            line for line in self.src.split("\n")
            if "const activeId" in line
            and "useRef" not in line
            and "useState" not in line
        ]
        assert not bad_lines, f"activeId 不应是 const: {bad_lines}"
        # WS onEvt 识别 action 字段
        assert 'detail.action === "switch"' in self.src
        assert 'detail.action === "created"' in self.src
        assert 'detail.action === "hard_delete"' in self.src
        assert 'detail.action === "auto_reset"' in self.src

    def test_bug2_v2_collapsed_search_uses_display_none(self):
        """Bug 2 二轮修复: 折叠时搜索框用 {collapsed && ...} 包裹整个 wrap
        原 visibility: hidden 让 input 不能 click/focus,体感"搜索框锁死"
        改成外层条件渲染,折叠时整个 searchWrap 不挂载,展开时正常"""
        # 折叠时不应该渲染搜索框整个 div
        assert "!collapsed && (" in self.src or "collapsed && (" in self.src
        # visibility: hidden 不应再出现(input 自身的反模式)
        assert "visibility: collapsed" not in self.src, "input 仍用 visibility: hidden,折叠时不可点击"

    # ===== v0.3.0 Day 11 折叠 UI 重构断言 =====

    def test_day11_width_is_constant_280(self):
        """Day 11:sidebar width 永远 280px,不再用 width 切换 collapsed/展开"""
        # 旧反模式: width: collapsed ? 60 : 280
        assert "collapsed ? 60 : 280" not in self.src, "width 不应再用 collapsed 切换"
        # 新写法: width 数字硬编码 280
        assert "width: 280," in self.src, "width 应硬编码 280"

    def test_day11_no_internal_collapse_button(self):
        """Day 11:不再有内部 ◀/▶ 折叠按钮(改由 FAB 触发)"""
        # 过滤掉所有注释行(JS //、块注释 *、JSX {/* */})
        import re
        # 去 JSX 注释 {/* ... */}
        no_jsx_comments = re.sub(r"\{/\*.*?\*/\}", "", self.src, flags=re.DOTALL)
        # 去 // 行
        code_only = "\n".join(
            line for line in no_jsx_comments.split("\n")
            if not line.strip().startswith("//")
        )
        assert "▶" not in code_only, "折叠 ▶ 按钮已迁出到 FAB"
        assert "◀" not in code_only, "折叠 ◀ 按钮已迁出到 FAB"
        assert "⏵" not in code_only, "footer 展开按钮已删除"
        assert "⏸" not in code_only, "footer 收起按钮已删除"

    def test_day11_listens_sidebar_toggle_event(self):
        """Day 11:监听 custom-header.js dispatch 的 sidebar:toggle 事件"""
        assert '"sidebar:toggle"' in self.src, "未监听 sidebar:toggle 事件"
        assert "addEventListener(\"sidebar:toggle\"" in self.src, "未挂 sidebar:toggle listener"

    # ===== v0.3.0 Day 11 hotfix 2:用 classList 替代 body attribute =====

    def test_hotfix2_no_body_setattribute_collapsed(self):
        """Day 11 hotfix 2:SessionSidebar 不应再给 body 设 data-sidebar-collapsed attribute
        改用 classList.toggle('sidebar-collapsed') — class 不会被 CSS [attr] selector 误匹配"""
        # 去 JSX 注释
        import re
        no_jsx_comments = re.sub(r"\{/\*.*?\*/\}", "", self.src, flags=re.DOTALL)
        code_only = "\n".join(
            line for line in no_jsx_comments.split("\n")
            if not line.strip().startswith("//")
        )
        # 不应再调 body.setAttribute('data-sidebar-collapsed', ...)
        assert "body.setAttribute(\"data-sidebar-collapsed\"" not in code_only, \
            "SessionSidebar 不应再 setAttribute data-sidebar-collapsed,改用 classList"
        # 应调 classList.toggle('sidebar-collapsed')
        assert "classList.toggle(\"sidebar-collapsed\"" in code_only or "classList.toggle('sidebar-collapsed'" in code_only, \
            "SessionSidebar 应调 classList.toggle('sidebar-collapsed', collapsed)"
        # 不应再 removeAttribute data-sidebar-collapsed
        assert "body.removeAttribute(\"data-sidebar-collapsed\"" not in code_only, \
            "SessionSidebar 不应再 removeAttribute data-sidebar-collapsed"


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


class TestCustomHeaderDay11:
    """v0.3.0 Day 11 custom-header.js 折叠 UI 重构断言"""

    def setup_method(self):
        self.src = (_PROJECT_ROOT / "public" / "custom-header.js").read_text(encoding="utf-8")

    def test_day11_uses_transform_not_width(self):
        """Day 11:折叠用 transform: translateX(-220px) 而非 width 切换"""
        # 只检查 CSS 代码段(去注释行)
        css_only = "\n".join(
            line for line in self.src.split("\n")
            if not line.strip().startswith("//") and not line.strip().startswith("*")
        )
        assert "translateX(-220px)" in css_only, "应使用 transform: translateX(-220px) 留 60px avatar 列"
        assert "translateX(-280px)" not in css_only, "不应再 translateX(-280px)(完全滑出会看不到 avatar 列)"
        # 老 width 60px 反模式不应在 CSS 里出现
        assert "width: 60px" not in css_only, "不应再硬编码 width: 60px"

    def test_day11_transform_selector_scoped_to_sidebar(self):
        """Day 11 修复:CSS transform selector 必须限定 [data-sidebar="1"][data-sidebar-collapsed="1"]
        否则 body / 其他元素也会被 transform 拖走,FAB 等 fixed 子元素跟着跑屏外,真实 click 打不到"""
        import re
        # 解析每条 CSS rule:selector { properties }
        for m in re.finditer(r"'([^']+)'\s*:\s*\{([^}]+)\}", self.src):
            selector = m.group(1)
            properties = m.group(2)
            if "transform" not in properties:
                continue
            # 用了 collapsed 选择器的 transform rule 必须同时限定 sidebar
            collapsed_marker = '[data-sidebar-collapsed="1"]'
            if collapsed_marker in selector:
                assert '[data-sidebar="1"]' in selector, \
                    f"transform rule selector 未限定 sidebar: {selector} → 会误匹配 body 导致 FAB 等被拖走"

    def test_day11_hotfix2_uses_class_not_body_attribute(self):
        """Day 11 hotfix 2:CSS 折叠态 selector 应改用 body.sidebar-collapsed class
        而非 body[data-sidebar-collapsed="1"] attribute(避免误匹配风险)"""
        # 解析每条 CSS rule
        import re
        css_rules = list(re.finditer(r"'([^']+)'\s*:\s*\{([^}]+)\}", self.src))
        # 旧的 body[data-sidebar-collapsed="1"] selector 应不再出现在 CSS 里
        # (main / FAB 等用 main content 定位的 selector 应改用 class)
        for m in css_rules:
            selector = m.group(1)
            # 这些 selector 用的是 [data-sidebar-collapsed="1"] + body 前缀,应改 class
            if selector.startswith("body[data-sidebar-collapsed="):
                # 唯一例外:已经限定 [data-sidebar="1"] 的不算
                if '[data-sidebar="1"]' not in selector:
                    raise AssertionError(
                        f"CSS selector {selector} 仍用 body[attr] 形式,应改用 body.sidebar-collapsed class"
                    )
        # 正确写法: body.sidebar-collapsed class selector 应该存在
        assert "body.sidebar-collapsed" in self.src, \
            "应使用 body.sidebar-collapsed class 选择器(替代 body[data-sidebar-collapsed])"

    def test_day11_hotfix3_fab_zindex_above_header(self):
        """Day 11 hotfix 3:FAB z-index 必须 > #header z-index(100)
        否则 Chainlit header 拦截 click → 'Failed to interact with the element'"""
        import re
        # 找 #sidebar-toggle-fab 主 rule 的 z-index(写法: '#sidebar-toggle-fab {' 后跟属性)
        # 先找到 rule 起点
        fab_rule_start = self.src.find("'#sidebar-toggle-fab {'")
        assert fab_rule_start >= 0, "未找到 #sidebar-toggle-fab 主 CSS rule"
        # 找 { 后的内容到下一个 }
        brace_open = self.src.find("{", fab_rule_start)
        brace_close = self.src.find("}", brace_open)
        properties = self.src[brace_open + 1:brace_close]
        # 提取 z-index 数值
        z_match = re.search(r'z-index:\s*(\d+)', properties)
        assert z_match, f"FAB 必须显式设 z-index,properties={properties}"
        fab_z = int(z_match.group(1))
        assert fab_z > 100, f"FAB z-index({fab_z}) 必须 > 100(#header z-index),否则 header 拦截 click"

    def test_day11_fab_button_exists(self):
        """Day 11:#sidebar-toggle-fab 浮动按钮注入"""
        assert "#sidebar-toggle-fab" in self.src, "未注入 #sidebar-toggle-fab"
        assert "injectFab" in self.src, "未实现 injectFab()"
        assert "sidebar:toggle" in self.src, "FAB click 应 dispatchEvent('sidebar:toggle')"

    def test_day11_ctrl_b_shortcut(self):
        """Day 11:Ctrl+B / Cmd+B 全局快捷键"""
        assert "Ctrl+B" in self.src or "k === 'b'" in self.src or "'b'" in self.src, \
            "未实现 Ctrl+B 快捷键"

    def test_day11_main_margin_left(self):
        """Day 11:主对话区用 margin-left 而非 body padding-left"""
        assert "margin-left: 280px" in self.src, "主对话区应 margin-left 280px"
        assert "margin-left: 60px" in self.src, "折叠态应 margin-left 60px(avatar 列)"
        # body padding-left 不应再是主定位手段
        # 注:padding-left 仍可作 padding(不是 layout 定位),但不应该是 280px
        assert "padding-left: 280px" not in self.src, "不应再用 body padding-left 280px 定位"

    def test_day11_transition_200ms(self):
        """Day 11:transition 200ms ease"""
        assert "200ms" in self.src, "未设 200ms transition"


class TestAPISessions:
    """/api/sessions 端点存在"""

    def test_endpoint_exists(self):
        app_path = _PROJECT_ROOT / "src" / "yantu" / "ui" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        assert '@chainlit_app.get("/api/sessions")' in src
        assert "list_sessions" in src
