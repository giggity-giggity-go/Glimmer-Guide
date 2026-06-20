// SessionSidebar.jsx
// v0.3.0-beta:多会话侧边栏
// Chainlit 通过 GET /public/elements/SessionSidebar.jsx 加载
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

  // 样式
  const containerStyle = {
    padding: "8px",
    background: "#f6f8fa",
    borderRadius: "6px",
    fontSize: "12px",
    minWidth: "200px",
    maxHeight: "70vh",
    overflowY: "auto",
  };
  const itemStyle = (active, pinned) => ({
    padding: "6px 8px",
    marginBottom: "3px",
    background: active ? "#ddf4ff" : "white",
    border: active ? "1px solid #0969da" : "1px solid #d0d7de",
    borderRadius: "4px",
    cursor: "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    fontWeight: pinned ? 600 : 400,
  });
  const btnStyle = {
    background: "transparent",
    border: "none",
    cursor: "pointer",
    fontSize: "12px",
    padding: "0 2px",
    color: "#57606a",
  };
  const newBtnStyle = {
    width: "100%",
    padding: "6px",
    marginBottom: "8px",
    background: "#2da44e",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: 500,
  };
  const inputStyle = {
    flex: 1,
    padding: "2px 4px",
    border: "1px solid #0969da",
    borderRadius: "3px",
    fontSize: "12px",
  };
  const emptyStyle = { color: "#6e7781", padding: "12px 8px", textAlign: "center" };

  return (
    <div style={containerStyle}>
      <button onClick={handleNew} style={newBtnStyle} title="新建会话">
        + 新会话
      </button>

      {sorted.length === 0 ? (
        <div style={emptyStyle}>暂无会话</div>
      ) : (
        sorted.map((s) => (
          <div
            key={s.thread_id}
            style={itemStyle(s.thread_id === activeId, s.is_pinned)}
            onClick={() => editingId !== s.thread_id && handleSwitch(s.thread_id)}
            onDoubleClick={(e) => handleStartRename(s, e)}
            title="单击切换 · 双击重命名"
          >
            <div style={{ flex: 1, overflow: "hidden" }}>
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
                  {s.is_pinned && <span style={{ marginRight: "4px" }}>📌</span>}
                  <span style={{ display: "inline-block", maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.title || "(无标题)"}
                  </span>
                  <span style={{ fontSize: "10px", color: "#6e7781", marginLeft: "4px" }}>
                    {s.message_count || 0}条
                  </span>
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: "2px" }}>
              <button onClick={(e) => handleTogglePin(s.thread_id, e)} style={btnStyle} title={s.is_pinned ? "取消固定" : "固定"}>
                {s.is_pinned ? "📍" : "📌"}
              </button>
              <button onClick={(e) => handleDelete(s, e)} style={{ ...btnStyle, color: "#cf222e" }} title="删除">
                🗑
              </button>
            </div>
          </div>
        ))
      )}

      {status && <div style={{ marginTop: "6px", fontSize: "11px", color: "#57606a" }}>{status}</div>}
    </div>
  );
}
