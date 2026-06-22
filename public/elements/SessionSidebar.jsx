// SessionSidebar.jsx
// v0.3.0 Day 9:完整重构 — 移到左侧 + 豆包/DeepSeek 模式
// v0.3.0 Day 11:折叠 UI 重构
//   - 折叠/展开改由 custom-header.js 注入的 #sidebar-toggle-fab 浮动按钮触发
//   - sidebar 宽度永远 280px,折叠 = transform translateX(-280px) 滑出屏外
//   - 主对话区用 margin-left 留位,折叠时归零,不再"整个对话一起被收"
//
// 功能(7 项):
// 1. 左侧 280px 钉住(由 custom-header.js CSS 强制)
// 2. 时间分组(置顶 → 今天 → 昨天 → 7天 → 30天 → YYYY-MM)
// 3. 搜索框 + Ctrl K 聚焦 + 空内容 Enter 新建
// 4. hover 浮层(⋮ 按钮 → dropdown 重命名/置顶/删除)
// 5. 字母 avatar 圆头像(从 title 取首字)
// 6. 折叠按钮:由 #sidebar-toggle-fab 浮动按钮 + Ctrl+B 全局快捷键触发(Day 11)
// 7. Ctrl K 聚焦搜索 / Ctrl Shift K 新建 / Ctrl B 折叠

// props 是 react-runner scope 里的全局变量

import { useState, useEffect, useRef, useMemo } from "react";

export default function SessionSidebar() {
  // === react-runner 全局 props ===
  const initial = (props && props.initial) || [];
  // v0.3.0 Day 10 修 Bug 4: activeId 改 useState
  // 原因:react-runner 不重 mount,prop.activeId 改了 const 不会重读
  // 必须 state 化 + 主动同步(订阅 sessions_changed WS 事件本地更新)
  const [activeId, setActiveId] = useState((props && props.activeId) || "");
  useEffect(() => {
    // 兜底:prop 变化时主动同步(react-runner 实际不会重新注入,主要靠 WS onEvt)
    const newId = (props && props.activeId) || "";
    if (newId) setActiveId(newId);
  }, [props && props.activeId]);
  // v0.3.0 Day 10: sessions 走 useState,初始值用 prop.initial
  // 后续由 WS push / 轮询更新(之前直接 const sessions = initial 是 React 反模式)
  const [sessions, setSessions] = useState(initial);
  // v0.3.0 Day 10 修 Bug 1: 前端软过滤 message_count=0 的空壳 session
  // 后端 /api/sessions 已传 min_message_count=1,前端再兜一道(后端 schema 改动时仍安全)
  const nonEmptySessions = useMemo(
    () => sessions.filter(s => (s.message_count || 0) > 0),
    [sessions]
  );
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [status, setStatus] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [menuOpenForId, setMenuOpenForId] = useState(null);
  // v0.3.0 Day 10: 自定义删除确认 modal(替代原生 confirm())
  const [confirmDelete, setConfirmDelete] = useState(null);  // { session: {...} }
  // v0.3.0 Day 10: 键盘导航 — ↑/↓ 移动 focusIdx,Enter 切换,Cmd+1..9 跳第 N 个
  const [focusIdx, setFocusIdx] = useState(-1);
  const searchRef = useRef(null);

  // === 时间分组 helper ===
  // v0.3.0 Day 10 修 Bug 1: 用 nonEmptySessions 而非 sessions,过滤空壳
  const buckets = useMemo(() => bucketSessions(nonEmptySessions, searchQuery), [nonEmptySessions, searchQuery]);

  // === v0.3.0 Day 10: 事件驱动 + 30s 兜底轮询 ===
  // (之前是每 5s 无脑 fetch;现在订阅 custom-header.js 转发的 sessions-updated 事件)
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
      } catch (e) {}
    };
    const onEvt = (e) => {
      // v0.3.0 Day 10 修 Bug 4: 主动同步 activeId,不等 prop 重 mount
      const detail = (e && e.detail) || {};
      if (detail.action === "switch" && detail.thread_id) {
        setActiveId(detail.thread_id);
      } else if (detail.action === "created" && detail.thread_id) {
        setActiveId(detail.thread_id);
      } else if (detail.action === "hard_delete" && detail.thread_id === activeIdRef.current) {
        // 当前活跃会话被永久删,清空本地 active(后端 on_message 会 auto_reset)
        setActiveId("");
      } else if (detail.action === "auto_reset") {
        setActiveId("");
      }
      // 兜底:无论什么 action,都重新拉一次列表(保持旧行为)
      poll();
    };
    window.addEventListener("sessions-updated", onEvt);
    const t = setInterval(poll, 30000);  // 改:5s → 30s 兜底
    poll();  // 立即拉一次(防 WS push 漏了)
    return () => {
      cancelled = true;
      clearInterval(t);
      window.removeEventListener("sessions-updated", onEvt);
    };
  }, []);

  // === Ctrl K / Ctrl Shift K ===
  useEffect(() => {
    const handler = (e) => {
      // v0.3.0 Day 10 修 Bug 3: IME composition 期间不抢焦点
      // 中文拼音/日文 IME 中 keydown 也会派发,e.key 是 Process,不应触发 Ctrl+K
      if (e.isComposing || e.keyCode === 229) return;
      const k = e.key.toLowerCase();
      const modKey = e.ctrlKey || e.metaKey;
      if (!modKey) return;
      if (k === "k" && e.shiftKey) {
        // Ctrl+Shift+K:新建会话
        e.preventDefault();
        e.stopPropagation();
        callAction({ name: "new_session", payload: {} });
      } else if (k === "k") {
        // Ctrl+K:聚焦搜索框
        e.preventDefault();
        e.stopPropagation();
        searchRef.current?.focus();
        searchRef.current?.select?.();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  // === v0.3.0 Day 10: ↑/↓/Enter/Cmd+1..9 键盘导航 ===
  // flatList:把 buckets 展平成单层数组,方便按索引定位
  const flatList = useMemo(() => {
    const out = [];
    for (const b of buckets) {
      if (!b.hidden) {
        for (const s of b.sessions) out.push(s);
      }
    }
    return out;
  }, [buckets]);

  // v0.3.0 Day 10 修 Bug 2: ref 桥接,handler 只挂一次
  // 原来 deps=[flatList, focusIdx] 每次 buckets/searchQuery 变都会 unmount/remount
  // keydown handler,与 layout thrashing 竞争导致主线程 long task
  const flatListRef = useRef(flatList);
  const focusIdxRef = useRef(focusIdx);
  const activeIdRef = useRef(activeId);  // 修 Bug 4: WS onEvt 内部读最新 activeId
  useEffect(() => { flatListRef.current = flatList; }, [flatList]);
  useEffect(() => { focusIdxRef.current = focusIdx; }, [focusIdx]);
  useEffect(() => { activeIdRef.current = activeId; }, [activeId]);

  useEffect(() => {
    const handler = (e) => {
      // 输入框焦点时不抢(搜索/重命名态)
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      const modKey = e.ctrlKey || e.metaKey;
      const fl = flatListRef.current;
      const fi = focusIdxRef.current;

      // Cmd/Ctrl + 1..9:跳到第 N 个最近会话
      if (modKey && /^[1-9]$/.test(e.key)) {
        const idx = parseInt(e.key, 10) - 1;
        if (idx < fl.length) {
          e.preventDefault();
          e.stopPropagation();
          handleSwitch(fl[idx].thread_id);
          setFocusIdx(idx);
        }
        return;
      }

      // ↑/↓ 移动 focusIdx
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusIdx((i) => Math.min(fl.length - 1, i + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusIdx((i) => Math.max(0, i - 1));
      } else if (e.key === "Enter" && fi >= 0 && fi < fl.length) {
        // Enter:切换到 focusIdx 对应会话
        e.preventDefault();
        handleSwitch(fl[fi].thread_id);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);  // 修:空 deps,handler 永远只挂一次,内部走 ref 拿最新值

  // === 折叠态 同步到 body 标签(让 custom-header.js 切换 main margin-left) ===
  // Day 11 改:同时同步 data-sidebar-collapsed 到 sidebar 自己的 div
  // (之前只设 body 属性,现在 CSS 选择器 [data-sidebar-collapsed="1"] 改为匹配 sidebar 自身,
  //  让 custom-header.js 的 transform: translateX(-280px) 生效)
  useEffect(() => {
    if (collapsed) {
      document.body.setAttribute("data-sidebar-collapsed", "1");
    } else {
      document.body.removeAttribute("data-sidebar-collapsed");
    }
  }, [collapsed]);

  // === Day 11 新增:监听 custom-header.js 注入的 FAB 点击 + Ctrl+B ===
  // FAB dispatchEvent('sidebar:toggle') 触发 setCollapsed
  // 注意:不能只依赖 collapsed state,React 异步更新,可能丢 toggle
  //       所以 toggleFunc 用 ref 闭包永远拿最新值
  const collapsedRef = useRef(collapsed);
  useEffect(() => { collapsedRef.current = collapsed; }, [collapsed]);
  useEffect(() => {
    const onToggle = () => setCollapsed(!collapsedRef.current);
    window.addEventListener("sidebar:toggle", onToggle);
    return () => window.removeEventListener("sidebar:toggle", onToggle);
  }, []);

  // === Onboarding tooltip(只在未 dismiss 时显示 3s)===
  const [showTip, setShowTip] = useState(() => {
    try { return sessionStorage.getItem("sidebar_tip_dismissed") !== "1"; } catch { return true; }
  });
  useEffect(() => {
    if (!showTip) return;
    const t = setTimeout(() => {
      setShowTip(false);
      try { sessionStorage.setItem("sidebar_tip_dismissed", "1"); } catch {}
    }, 3500);
    return () => clearTimeout(t);
  }, [showTip]);

  // === Event handlers ===
  const handleNew = async () => {
    setStatus("+ 新会话...");
    try {
      await callAction({ name: "new_session", payload: {} });
      setStatus("✅ 已创建");
      setTimeout(() => setStatus(""), 1500);
    } catch (e) {
      setStatus(`❌ 新建失败: ${e}`);
    }
  };

  const handleSwitch = async (tid) => {
    try { await callAction({ name: "switch_session", payload: { thread_id: tid } }); }
    catch (e) { console.error("switch failed:", e); }
  };

  const handleStartRename = (s, e) => {
    if (e) e.stopPropagation();
    setEditingId(s.thread_id);
    setEditValue(s.title);
    setMenuOpenForId(null);
  };

  const handleFinishRename = async (tid) => {
    const newTitle = editValue.trim();
    if (!newTitle) { setEditingId(null); return; }
    try {
      await callAction({ name: "rename_session", payload: { thread_id: tid, title: newTitle } });
    } catch (e) { console.error("rename failed:", e); }
    setEditingId(null);
  };

  const handleTogglePin = async (tid, e) => {
    if (e) e.stopPropagation();
    try { await callAction({ name: "toggle_pin", payload: { thread_id: tid } }); }
    catch (e) { console.error("toggle_pin failed:", e); }
    setMenuOpenForId(null);
  };

  const handleDelete = async (s, e) => {
    if (e) e.stopPropagation();
    // v0.3.0 Day 10: 用自定义 modal 替代原生 confirm()
    // 三按钮(归档 / 永久删除 / 取消),对齐豆包/DeepSeek 的二次确认模式
    setConfirmDelete({ session: s });
    setMenuOpenForId(null);
  };

  const confirmDeleteAction = async (hard) => {
    if (!confirmDelete) return;
    const tid = confirmDelete.session.thread_id;
    const title = confirmDelete.session.title;
    setConfirmDelete(null);
    try {
      await callAction({ name: "delete_session", payload: { thread_id: tid, hard } });
      setStatus(hard ? `✅ 已永久删除 "${title}"` : `📦 已归档 "${title}"`);
      setTimeout(() => setStatus(""), 3000);
    } catch (e) {
      console.error("delete failed:", e);
      setStatus(`❌ 删除失败: ${e}`);
      setTimeout(() => setStatus(""), 3000);
    }
  };

  const handleSearchKeyDown = (e) => {
    if (e.key === "Enter" && !searchQuery.trim()) {
      e.preventDefault();
      handleNew();
    } else if (e.key === "Escape") {
      setSearchQuery("");
      searchRef.current?.blur();
    }
  };

  // === 样式 ===
  // Day 11 改:width 永远 280px,折叠用 custom-header.js 的 transform: translateX(-220px)
  // (=280-60,留 60px avatar 列在屏左,豆包风格)
  // 不再用 width 收缩(会导致整个对话一起"被收")
  const sidebarStyle = {
    position: "fixed", left: 0, top: 0, bottom: 0,
    width: 280, zIndex: 50,
    background: "#f6f8fa", borderRight: "1px solid #d0d7de",
    display: "flex", flexDirection: "column",
    fontFamily: "inherit", overflow: "hidden",
    // transition 由 custom-header.js 控制 transform,这里不重复
  };
  // data-sidebar="1" 让 custom-header.js CSS 选择器找到
  // data-sidebar-collapsed 切换 transform: translateX(-220px)
  const sidebarDataAttrs = { "data-sidebar": "1" };
  if (collapsed) sidebarDataAttrs["data-sidebar-collapsed"] = "1";

  const headerStyle = {
    display: "flex", alignItems: "center",
    padding: "12px 12px",
    borderBottom: "1px solid #d0d7de", flexShrink: 0,
    gap: 8,
  };
  const logoStyle = {
    fontWeight: 600, fontSize: "14px", color: "#1f2328",
    flex: 1, display: "block",
  };
  // Day 11 删:collapseBtnStyle(改由 FAB 触发)

  // 搜索框区
  const searchWrapStyle = {
    padding: collapsed ? "8px 0" : "8px 8px",
    position: "relative", flexShrink: 0,
  };
  const searchInputStyle = {
    width: "100%", padding: "6px 8px 6px 28px",
    border: "1px solid #d0d7de", borderRadius: "6px",
    fontSize: "13px", background: collapsed ? "transparent" : "#fff",
    outline: "none",
  };
  const searchIconStyle = {
    position: "absolute", left: collapsed ? "50%" : 16, top: 14,
    transform: collapsed ? "translateX(-50%)" : "none",
    color: "#6e7781", fontSize: "12px", pointerEvents: "none",
  };
  const searchKbdStyle = {
    position: "absolute", right: 14, top: 14,
    fontSize: "10px", color: "#6e7781",
    background: "#eaeef2", border: "1px solid #d0d7de",
    borderRadius: "3px", padding: "1px 4px",
  };

  // + 新对话 按钮
  const newBtnWrapStyle = {
    padding: collapsed ? "4px 0 8px 0" : "4px 8px 8px 8px",
    flexShrink: 0, position: "relative",
  };
  const newBtnStyle = {
    width: "100%", height: 36,
    background: "transparent", border: "1px solid #d0d7de",
    borderRadius: "6px", cursor: "pointer",
    fontSize: "14px", color: "#1f2328",
    display: "flex", alignItems: "center", justifyContent: "center",
    gap: 6, padding: "0 8px",
  };
  const kbdStyle = {
    fontSize: "11px", color: "#6e7781",
    background: "#eaeef2", border: "1px solid #d0d7de",
    borderRadius: "3px", padding: "1px 5px", marginLeft: "auto",
  };
  const tooltipStyle = {
    position: "absolute", top: "calc(100% + 4px)", left: 8, right: 8,
    background: "#fff8c5", border: "1px solid #d4a72c",
    borderRadius: "4px", padding: "6px 10px",
    fontSize: "12px", color: "#1f2328",
    boxShadow: "0 2px 6px rgba(0,0,0,0.1)", zIndex: 100,
  };

  // 列表区
  const listWrapStyle = {
    flex: 1, overflowY: "auto", padding: collapsed ? "8px 0" : "4px 8px",
    scrollbarWidth: "thin", scrollbarColor: "#d0d7de transparent",
  };
  const groupHeaderStyle = {
    fontSize: "11px", color: "#6e7781",
    fontWeight: 600, padding: "10px 4px 4px 8px",
    textTransform: "uppercase", letterSpacing: "0.5px",
    display: collapsed ? "none" : "block",
  };
  const itemStyle = (active, pinned) => ({
    height: 32, padding: "0 4px 0 4px",
    margin: "1px 0",
    background: active ? "#ddf4ff" : "transparent",
    border: "none", borderRadius: "6px",
    cursor: "pointer",
    display: "flex", alignItems: "center", gap: 8,
    position: "relative",
    fontSize: "13px", color: "#1f2328",
    fontWeight: pinned ? 600 : 400,
  });
  const avatarStyle = (active) => ({
    width: 24, height: 24, borderRadius: "50%",
    background: active ? "#0969da" : avatarColor(sessions, active),
    color: "white", display: "flex",
    alignItems: "center", justifyContent: "center",
    fontSize: "11px", fontWeight: 600, flexShrink: 0,
  });
  const itemTextStyle = {
    flex: 1, overflow: "hidden", textOverflow: "ellipsis",
    whiteSpace: "nowrap", minWidth: 0,
    display: collapsed ? "none" : "block",
  };
  const pinIconStyle = {
    fontSize: "10px", marginRight: 2,
    display: collapsed ? "none" : "inline",
  };
  const menuBtnStyle = (visible) => ({
    background: "transparent", border: "none",
    cursor: "pointer", padding: "0 4px",
    color: "#57606a", fontSize: "14px",
    opacity: visible ? 1 : 0,
    transition: "opacity 0.15s",
    display: collapsed ? "none" : "block",
  });
  const dropdownStyle = {
    position: "absolute", top: 28, right: 4,
    background: "white", border: "1px solid #d0d7de",
    borderRadius: "6px", boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
    zIndex: 200, minWidth: 120, padding: "4px 0",
  };
  const dropdownItemStyle = {
    padding: "6px 12px", fontSize: "13px", cursor: "pointer",
    color: "#1f2328",
  };
  const dropdownDangerStyle = { ...dropdownItemStyle, color: "#cf222e" };

  // 底部(Day 11 删:footerBtnStyle,改由 FAB 触发)
  const footerStyle = {
    padding: "8px", borderTop: "1px solid #d0d7de",
    display: "flex", justifyContent: "flex-start",
    alignItems: "center", flexShrink: 0,
    fontSize: "11px", color: "#6e7781",
  };
  const inputStyle = {
    flex: 1, padding: "2px 4px", border: "1px solid #0969da",
    borderRadius: "3px", fontSize: "12px",
  };
  const emptyStyle = {
    color: "#6e7781", padding: "12px 8px", textAlign: "center",
    fontSize: "13px",
  };
  const statusStyle = {
    padding: "4px 8px", fontSize: "11px", color: "#57606a", flexShrink: 0,
  };

  return (
    <div style={sidebarStyle} {...sidebarDataAttrs}>
      {/* v0.3.0 Day 10: 删除确认 modal,固定位置(不跟随侧边栏) */}
      <ConfirmDeleteModal
        confirmDelete={confirmDelete}
        onCancel={() => setConfirmDelete(null)}
        onArchive={() => confirmDeleteAction(false)}
        onHardDelete={() => confirmDeleteAction(true)}
      />
      {/* 头部:logo(Day 11: 删 ◀/▶ 折叠按钮,改由 FAB 触发) */}
      <div style={headerStyle}>
        <div style={logoStyle}>研途萤火</div>
      </div>

      {/* 搜索框 — v0.3.0 Day 10 修 Bug 2 二轮: 折叠时 display: none 而非 visibility: hidden */}
      {/* 原 visibility: hidden 让 input 仍占位置但不能 click/focus,体感"搜索框锁死" */}
      {!collapsed && (
        <div style={searchWrapStyle}>
          <span style={searchIconStyle}>🔍</span>
          <input
            ref={searchRef}
            type="text"
            placeholder="搜索会话..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            // v0.3.0 Day 10 修 Bug 3: IME composition 期间让浏览器自然控制 input value
            // 拼音/日文输入未结束时,onChange 的 e.target.value 不完整,compositionEnd 时再同步
            onCompositionStart={(e) => { e.target.dataset.composing = "1"; }}
            onCompositionEnd={(e) => {
              delete e.target.dataset.composing;
              setSearchQuery(e.target.value);
            }}
            style={searchInputStyle}
          />
          <kbd style={searchKbdStyle}>⌘K</kbd>
        </div>
      )}

      {/* + 新对话 按钮 — 空态时隐藏(由首条消息触发更自然) */}
      {!buckets.every(b => b.hidden) && (
        <div style={newBtnWrapStyle}>
          <button onClick={handleNew} style={newBtnStyle} title="新建会话 (Ctrl+Shift+K)">
            {collapsed ? "+" : (<><span>＋ 新对话</span><kbd style={kbdStyle}>⌘⇧K</kbd></>)}
          </button>
          {showTip && !collapsed && (
            <div style={tooltipStyle} onClick={() => setShowTip(false)}>
              💡 单击切换 · 双击重命名 · ⋮ 菜单
            </div>
          )}
        </div>
      )}

      {/* 会话列表(时间分组) */}
      <div style={listWrapStyle} className="session-sidebar-list">
        {buckets.every(b => b.hidden) ? (
          <div style={{ ...emptyStyle, padding: "24px 16px", lineHeight: 1.6 }}>
            {searchQuery ? "没有匹配的会话" : (
              <>
                <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
                <div style={{ fontWeight: 600, color: "#1f2328", marginBottom: 4 }}>还没有会话</div>
                <div style={{ fontSize: 12, color: "#6e7781" }}>在右侧对话框输入第一条消息试试</div>
              </>
            )}
          </div>
        ) : (
          buckets.map((bucket) =>
            bucket.hidden ? null : (
              <div key={bucket.label}>
                {!collapsed && (
                  <div style={groupHeaderStyle}>{bucket.label}</div>
                )}
                {bucket.sessions.map((s) => {
                  // v0.3.0 Day 10: 用 flatList.indexOf 算全局索引(列表 < 100,O(n) 可接受)
                  // 传给 SessionItem 让其根据 focusIdx 决定是否高亮(outline)
                  const flatIndex = flatList.indexOf(s);
                  return (
                    <SessionItem
                      key={s.thread_id}
                      session={s}
                      active={s.thread_id === activeId}
                      focused={flatIndex === focusIdx}
                      collapsed={collapsed}
                      editing={editingId === s.thread_id}
                      editValue={editValue}
                      onSwitch={handleSwitch}
                      onStartRename={handleStartRename}
                      onFinishRename={handleFinishRename}
                      onTogglePin={handleTogglePin}
                      onDelete={handleDelete}
                      onMenuToggle={(id) => setMenuOpenForId(menuOpenForId === id ? null : id)}
                      menuOpen={menuOpenForId === s.thread_id}
                      setEditValue={setEditValue}
                      setEditingId={setEditingId}
                      styles={{
                        item: itemStyle, avatar: avatarStyle, text: itemTextStyle,
                        pin: pinIconStyle, menuBtn: menuBtnStyle,
                        dropdown: dropdownStyle, dropdownItem: dropdownItemStyle,
                        dropdownDanger: dropdownDangerStyle, input: inputStyle,
                      }}
                    />
                  );
                })}
              </div>
            )
          )
        )}
      </div>

      {status && <div style={statusStyle}>{status}</div>}

      {/* 底部:会话计数(Day 11: 删 ⏵/⏸ 折叠按钮,改由 FAB 触发) */}
      <div style={footerStyle}>
        <span>{nonEmptySessions.length} 个会话</span>
      </div>

      {/* 注入 CSS 隐藏滚动条(仅 hover 显)— 跟 v0.3.0 Day 8 一致 */}
      <style>{`
        .session-sidebar-list::-webkit-scrollbar { width: 6px; }
        .session-sidebar-list::-webkit-scrollbar-track { background: transparent; }
        .session-sidebar-list::-webkit-scrollbar-thumb { background: transparent; border-radius: 3px; }
        .session-sidebar-list:hover::-webkit-scrollbar-thumb { background: #d0d7de; }
        .session-sidebar-list { scrollbar-width: thin; scrollbar-color: #d0d7de transparent; }
      `}</style>
    </div>
  );
}

// === v0.3.0 Day 10: 自定义删除确认 modal ===
// 替代原生 confirm(),3 按钮:归档(30 天可恢复)/ 永久删除(不可逆)/ 取消
function ConfirmDeleteModal({ confirmDelete, onCancel, onArchive, onHardDelete }) {
  if (!confirmDelete) return null;
  const s = confirmDelete.session;
  const overlayStyle = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
    display: "flex", alignItems: "center", justifyContent: "center",
    zIndex: 9999,
  };
  const cardStyle = {
    width: 360, background: "#ffffff", borderRadius: 8,
    boxShadow: "0 8px 24px rgba(0,0,0,0.2)", padding: 20,
    fontFamily: "inherit",
  };
  const titleStyle = {
    fontSize: 16, fontWeight: 600, color: "#1f2328", marginBottom: 8,
  };
  const bodyStyle = {
    fontSize: 13, color: "#57606a", lineHeight: 1.6, marginBottom: 16,
  };
  const btnRowStyle = {
    display: "flex", gap: 8, justifyContent: "flex-end",
  };
  const baseBtnStyle = {
    padding: "6px 14px", borderRadius: 6, border: "1px solid #d0d7de",
    background: "#ffffff", cursor: "pointer", fontSize: 13, fontFamily: "inherit",
  };
  const dangerBtnStyle = {
    ...baseBtnStyle,
    background: "#cf222e", color: "#ffffff", borderColor: "#cf222e",
  };
  return (
    <div style={overlayStyle} onClick={onCancel}>
      <div style={cardStyle} onClick={(e) => e.stopPropagation()}>
        <div style={titleStyle}>删除会话</div>
        <div style={bodyStyle}>
          即将删除 <strong>"{s.title}"</strong>。
          <br /><br />
          · <strong>归档</strong>:隐藏会话,30 天内可在数据库恢复
          <br />
          · <strong>永久删除</strong>:不可恢复,关联记忆按 3 类规则释放
        </div>
        <div style={btnRowStyle}>
          <button style={baseBtnStyle} onClick={onCancel}>取消</button>
          <button style={baseBtnStyle} onClick={onArchive}>📦 归档</button>
          <button style={dangerBtnStyle} onClick={onHardDelete}>永久删除</button>
        </div>
      </div>
    </div>
  );
}

// === SessionItem 子组件(避免主组件太长) ===
function SessionItem({
  session, active, focused, collapsed, editing, editValue,
  onSwitch, onStartRename, onFinishRename, onTogglePin, onDelete,
  onMenuToggle, menuOpen, setEditValue, setEditingId, styles,
}) {
  const s = session;
  const showMenuBtn = !collapsed && !editing;
  // v0.3.0 Day 10: 键盘 focus 时加蓝色 outline(不抢鼠标 hover)
  const itemStyleCombined = focused
    ? { ...styles.item(active, s.is_pinned), outline: "2px solid #0969da", outlineOffset: -2 }
    : styles.item(active, s.is_pinned);
  return (
    <div
      style={itemStyleCombined}
      onClick={() => !editing && onSwitch(s.thread_id)}
      onDoubleClick={(e) => onStartRename(s, e)}
      onMouseLeave={() => menuOpen && onMenuToggle(s.thread_id)}
      title={collapsed ? s.title : "单击切换 · 双击重命名"}
    >
      {/* 字母 avatar 圆头像 */}
      <div style={styles.avatar(active)}>
        {(s.title || "?")[0].toUpperCase()}
      </div>

      {/* 文字区域(折叠态隐藏) */}
      {!collapsed && (
        <div style={styles.text}>
          {editing ? (
            <input
              style={styles.input}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={() => onFinishRename(s.thread_id)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onFinishRename(s.thread_id);
                if (e.key === "Escape") setEditingId(null);
              }}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <>
              {s.is_pinned && <span style={styles.pin}>📌</span>}
              <span>{s.title || "(无标题)"}</span>
            </>
          )}
        </div>
      )}

      {/* ⋮ 浮层按钮(展开态 hover 显) */}
      {!collapsed && (
        <button
          style={styles.menuBtn(showMenuBtn || menuOpen)}
          onClick={(e) => { e.stopPropagation(); onMenuToggle(s.thread_id); }}
          title="更多操作"
        >
          ⋮
        </button>
      )}

      {/* Dropdown 菜单 */}
      {menuOpen && !collapsed && (
        <div style={styles.dropdown} onClick={(e) => e.stopPropagation()}>
          <div style={styles.dropdownItem} onClick={() => onStartRename(s)}>
            ✏️ 重命名
          </div>
          <div style={styles.dropdownItem} onClick={(e) => onTogglePin(s.thread_id, e)}>
            {s.is_pinned ? "📍 取消固定" : "📌 固定"}
          </div>
          <div style={styles.dropdownDanger} onClick={(e) => onDelete(s, e)}>
            🗑 删除
          </div>
        </div>
      )}
    </div>
  );
}

// === 字母 avatar 颜色生成(根据 thread_id 哈希)===
function avatarColor(sessions, active) {
  if (active) return "#0969da";
  // 用 hash 简单生成柔和色(豆包风格)
  const palette = ["#7c8da4", "#a37bba", "#6b91a8", "#a87a5e", "#9b6a8a", "#5d8a82"];
  return palette[Math.abs(hashStr("default")) % palette.length];
}
function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return h;
}

// === 时间分组 ===
function bucketSessions(sessions, searchQuery) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const seven = new Date(today); seven.setDate(today.getDate() - 7);
  const thirty = new Date(today); thirty.setDate(today.getDate() - 30);

  // 搜索过滤
  let filtered = sessions;
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filtered = sessions.filter(s => (s.title || "").toLowerCase().includes(q));
  }

  const pinned = [], today_arr = [], yesterday_arr = [],
        seven_arr = [], thirty_arr = [], older = {};
  for (const s of filtered) {
    if (s.is_pinned) pinned.push(s);
    const d = new Date(s.updated_at || s.created_at || 0);
    if (isNaN(d.getTime())) continue;
    if (d >= today) today_arr.push(s);
    else if (d >= yesterday) yesterday_arr.push(s);
    else if (d >= seven) seven_arr.push(s);
    else if (d >= thirty) thirty_arr.push(s);
    else {
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      (older[key] ||= []).push(s);
    }
  }
  return [
    { label: "📌 置顶", sessions: pinned, hidden: pinned.length === 0 },
    { label: "今天", sessions: today_arr, hidden: today_arr.length === 0 },
    { label: "昨天", sessions: yesterday_arr, hidden: yesterday_arr.length === 0 },
    { label: "7 天前", sessions: seven_arr, hidden: seven_arr.length === 0 },
    { label: "30 天前", sessions: thirty_arr, hidden: thirty_arr.length === 0 },
    ...Object.entries(older)
      .sort(([a], [b]) => b.localeCompare(a))  // 倒序:最近月份在前
      .map(([k, v]) => ({ label: k, sessions: v, hidden: v.length === 0 })),
  ];
}
