// SessionSidebar.jsx
// v0.3.0 Day 8:豆包模式重构
// 视觉对齐豆包 sidebar(36px item 统一 + 隐藏滚动条 + Ctrl K 快捷键 + onboarding tooltip + 折叠按钮)
// 5 秒轮询 GET /api/sessions 拿列表
// 5 个 callAction 绑定:new_session / switch_session / rename_session / toggle_pin / delete_session
// 排序:pinned 在前 → updated_at DESC
// 双击重命名 → inline input → blur 触发 callAction
// 二次 confirm 删除
// 100% inline style(跟现有 3 个 JSX 一致)

// props 是 react-runner scope 里的全局变量,不是函数参数

import { useState, useEffect } from "react";

export default function SessionSidebar() {
  // react-runner 注入 props 为全局
  const initial = (props && props.initial) || [];
  const activeId = (props && props.activeId) || "";
  const [sessions, setSessions] = useState(initial);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [status, setStatus] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  // 5 秒轮询
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await fetch("/api/sessions", { cache: "no-store" });
        if (!cancelled && r.ok) {
          const data = await r.json();
          if (Array.isArray(data.sessions)) {
            setSessions(data.sessions);
          }
        }
      } catch (e) {
        // 静默失败,1 次轮询不报错
      }
    };
    const t = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  // 同步 initial(父组件传新值,如 on_chat_start)
  useEffect(() => {
    setSessions(initial);
  }, [initial.length, initial[0]?.thread_id]);

  // Ctrl+K / Cmd+K 唤起新会话(豆包风格)
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        e.stopPropagation();
        callAction({ name: "new_session", payload: {} });
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  // Onboarding tooltip 状态(sessionStorage 记忆)
  const [showTip, setShowTip] = useState(() => {
    try {
      return sessionStorage.getItem("sidebar_tip_dismissed") !== "1";
    } catch {
      return true;
    }
  });
  useEffect(() => {
    if (!showTip) return;
    const t = setTimeout(() => {
      setShowTip(false);
      try { sessionStorage.setItem("sidebar_tip_dismissed", "1"); } catch {}
    }, 3000);
    return () => clearTimeout(t);
  }, [showTip]);

  // 排序: pinned DESC → updated_at DESC
  const sorted = [...sessions].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return (b.updated_at || "").localeCompare(a.updated_at || "");
  });

  const handleNew = async () => {
    setStatus("+ 新会话...");
    try {
      await callAction({ name: "new_session", payload: {} });
      setStatus("✅ 已创建,等下一次刷新");
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus(`❌ 新建失败: ${e}`);
    }
  };

  const handleSwitch = async (tid) => {
    try {
      await callAction({ name: "switch_session", payload: { thread_id: tid } });
    } catch (e) {
      console.error("switch failed:", e);
    }
  };

  const handleStartRename = (s, e) => {
    e.stopPropagation();
    setEditingId(s.thread_id);
    setEditValue(s.title);
  };

  const handleFinishRename = async (tid) => {
    const newTitle = editValue.trim();
    if (!newTitle) {
      setEditingId(null);
      return;
    }
    try {
      await callAction({
        name: "rename_session",
        payload: { thread_id: tid, title: newTitle },
      });
      setSessions(
        sessions.map((s) =>
          s.thread_id === tid ? { ...s, title: newTitle } : s
        )
      );
    } catch (e) {
      console.error("rename failed:", e);
    }
    setEditingId(null);
  };

  const handleTogglePin = async (tid, e) => {
    e.stopPropagation();
    try {
      await callAction({ name: "toggle_pin", payload: { thread_id: tid } });
      setSessions(
        sessions.map((s) =>
          s.thread_id === tid ? { ...s, is_pinned: !s.is_pinned } : s
        )
      );
    } catch (e) {
      console.error("toggle_pin failed:", e);
    }
  };

  const handleDelete = async (s, e) => {
    e.stopPropagation();
    const msg = s.is_archived
      ? `永久删除会话 "${s.title}"?该操作会同时释放关联的记忆(部分硬删/部分保留)。`
      : `删除会话 "${s.title}"?\n(默认归档,30 天内可恢复;点确定为硬删)`;
    if (!confirm(msg)) return;
    try {
      await callAction({
        name: "delete_session",
        payload: { thread_id: s.thread_id, hard: true },
      });
      setSessions(sessions.filter((x) => x.thread_id !== s.thread_id));
    } catch (e) {
      console.error("delete failed:", e);
    }
  };

  const dismissTip = () => {
    setShowTip(false);
    try { sessionStorage.setItem("sidebar_tip_dismissed", "1"); } catch {}
  };

  // 样式 — 豆包风格
  const WIDTH = 280;
  const WIDTH_COLLAPSED = 60;
  const ITEM_HEIGHT = 36;
  const containerStyle = {
    width: collapsed ? WIDTH_COLLAPSED : WIDTH,
    minWidth: collapsed ? WIDTH_COLLAPSED : WIDTH,
    height: "100%",
    background: "#f6f8fa",
    borderRight: "1px solid #d0d7de",
    display: "flex",
    flexDirection: "column",
    fontSize: "14px",
    color: "#1f2328",
    fontFamily: "inherit",
    transition: "width 0.15s ease",
    overflow: "hidden",
  };
  const headerStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: collapsed ? "12px 0" : "12px 12px",
    borderBottom: "1px solid #d0d7de",
    flexShrink: 0,
  };
  const logoStyle = {
    fontWeight: 600,
    fontSize: "14px",
    color: "#1f2328",
    display: collapsed ? "none" : "block",
  };
  const collapseBtnStyle = {
    background: "transparent",
    border: "1px solid #d0d7de",
    borderRadius: "4px",
    cursor: "pointer",
    padding: "2px 6px",
    color: "#57606a",
    fontSize: "12px",
  };
  const newBtnWrapStyle = {
    position: "relative",
    padding: collapsed ? "8px 0" : "8px 8px",
    flexShrink: 0,
  };
  const newBtnStyle = {
    width: "100%",
    height: ITEM_HEIGHT,
    background: "transparent",
    border: "1px solid #d0d7de",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "14px",
    color: "#1f2328",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    padding: "0 8px",
  };
  const shortcutHintStyle = {
    fontSize: "11px",
    color: "#6e7781",
    background: "#eaeef2",
    border: "1px solid #d0d7de",
    borderRadius: "3px",
    padding: "1px 5px",
    marginLeft: "auto",
    flexShrink: 0,
  };
  const tooltipStyle = {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: collapsed ? -100 : 8,
    right: collapsed ? -100 : 8,
    background: "#fff8c5",
    border: "1px solid #d4a72c",
    borderRadius: "4px",
    padding: "6px 10px",
    fontSize: "12px",
    color: "#1f2328",
    boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
    zIndex: 10,
    whiteSpace: collapsed ? "normal" : "nowrap",
  };
  const listWrapStyle = {
    flex: 1,
    overflowY: "auto",
    padding: collapsed ? "8px 0" : "4px 8px",
    // 隐藏滚动条(豆包风格)— Firefox 不支持
    scrollbarWidth: "thin",
    scrollbarColor: "#d0d7de transparent",
  };
  const itemStyle = (active, pinned) => ({
    height: ITEM_HEIGHT,
    padding: "0 8px",
    margin: "2px 0",
    background: active ? "#ddf4ff" : "transparent",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "14px",
    color: "#1f2328",
    fontWeight: pinned ? 600 : 400,
  });
  const itemTextWrapStyle = {
    flex: 1,
    display: "flex",
    alignItems: "center",
    gap: "4px",
    overflow: "hidden",
    minWidth: 0,
  };
  const itemTextStyle = {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
    minWidth: 0,
  };
  const btnRowStyle = {
    display: "flex",
    gap: "2px",
    flexShrink: 0,
    marginLeft: "4px",
  };
  const btnStyle = {
    background: "transparent",
    border: "none",
    cursor: "pointer",
    color: "#57606a",
    fontSize: "12px",
    padding: "2px 4px",
    borderRadius: "3px",
  };
  const emptyStyle = {
    color: "#6e7781",
    padding: "12px 8px",
    textAlign: "center",
    fontSize: "13px",
  };
  const inputStyle = {
    flex: 1,
    padding: "2px 4px",
    border: "1px solid #0969da",
    borderRadius: "3px",
    fontSize: "13px",
  };
  const statusStyle = {
    padding: "4px 8px",
    fontSize: "11px",
    color: "#57606a",
    flexShrink: 0,
  };

  // 注入 CSS(隐藏滚动条,仅 hover 时显)— react-runner 共享 <head>
  useEffect(() => {
    const id = "session-sidebar-scrollbar-css";
    if (document.getElementById(id)) return;
    const style = document.createElement("style");
    style.id = id;
    style.textContent = `
      .session-sidebar-list::-webkit-scrollbar { width: 6px; }
      .session-sidebar-list::-webkit-scrollbar-track { background: transparent; }
      .session-sidebar-list::-webkit-scrollbar-thumb { background: transparent; border-radius: 3px; }
      .session-sidebar-list:hover::-webkit-scrollbar-thumb { background: #d0d7de; }
      .session-sidebar-list:hover::-webkit-scrollbar-thumb:hover { background: #afb8c1; }
      .session-sidebar-list { scrollbar-width: thin; scrollbar-color: #d0d7de transparent; }
    `;
    document.head.appendChild(style);
  }, []);

  return (
    <div style={containerStyle}>
      {/* Header: logo + 折叠按钮 */}
      <div style={headerStyle}>
        {!collapsed && <div style={logoStyle}>研途萤火</div>}
        <button
          onClick={() => setCollapsed(c => !c)}
          style={collapseBtnStyle}
          title={collapsed ? "展开" : "折叠"}
        >
          {collapsed ? "▶" : "◀"}
        </button>
      </div>

      {/* 新对话 按钮(豆包风格:文字 + Ctrl K 提示) */}
      <div style={newBtnWrapStyle}>
        <button
          onClick={handleNew}
          style={newBtnStyle}
          title="新建会话 (Ctrl+K)"
        >
          {collapsed ? "+" : (
            <>
              <span>＋ 新对话</span>
              <span style={shortcutHintStyle}>⌘K</span>
            </>
          )}
        </button>
        {/* Onboarding tooltip */}
        {showTip && !collapsed && (
          <div style={tooltipStyle} onClick={dismissTip}>
            💡 单击切换 · 双击重命名 · Ctrl K 新建
          </div>
        )}
      </div>

      {/* 会话列表 */}
      <div className="session-sidebar-list" style={listWrapStyle}>
        {sorted.length === 0 ? (
          !collapsed && <div style={emptyStyle}>暂无会话</div>
        ) : (
          sorted.map((s) => (
            <div
              key={s.thread_id}
              style={itemStyle(s.thread_id === activeId, s.is_pinned)}
              onClick={() => editingId !== s.thread_id && handleSwitch(s.thread_id)}
              onDoubleClick={(e) => handleStartRename(s, e)}
              title={collapsed ? s.title : "单击切换 · 双击重命名"}
            >
              {collapsed ? (
                // icon-only 态:title 首字符圆形
                <div style={{
                  width: 28, height: 28, borderRadius: "50%",
                  background: s.thread_id === activeId ? "#0969da" : "#d0d7de",
                  color: s.thread_id === activeId ? "white" : "#1f2328",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "12px", fontWeight: 600, margin: "0 auto",
                }}>
                  {(s.title || "?")[0]}
                </div>
              ) : (
                <>
                  <div style={itemTextWrapStyle}>
                    {editingId === s.thread_id ? (
                      <input
                        style={inputStyle}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => handleFinishRename(s.thread_id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleFinishRename(s.thread_id);
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <>
                        {s.is_pinned && <span style={{ fontSize: "12px" }}>📌</span>}
                        <span style={itemTextStyle}>
                          {s.title || "(无标题)"}
                        </span>
                      </>
                    )}
                  </div>
                  <div style={btnRowStyle}>
                    <button
                      onClick={(e) => handleTogglePin(s.thread_id, e)}
                      style={btnStyle}
                      title={s.is_pinned ? "取消固定" : "固定"}
                    >
                      {s.is_pinned ? "📍" : "📌"}
                    </button>
                    <button
                      onClick={(e) => handleDelete(s, e)}
                      style={btnStyle}
                      title="删除"
                    >
                      🗑
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      {status && <div style={statusStyle}>{status}</div>}
    </div>
  );
}
