// ContextSettings.jsx
// v0.3.0-beta:上下文设置面板
// Chainlit 通过 GET /public/elements/ContextSettings.jsx 加载
// 4 个控件:context_window 滑块 / keep_recent 滑块 / memory_injection 滑块 / memory_enabled 复选框
// 保存调 callAction("save_context_settings") 批量更新 UserSetting 表

// props 是 react-runner scope 里的全局变量,不是函数参数

import { useState, useEffect } from "react";

export default function ContextSettings() {
  // react-runner 注入 props 为全局
  const initial = (props && props.initial) || {};
  const init = {
    context_window_tokens: 30000,
    context_keep_recent_messages: 10,
    memory_injection_count: 10,
    memory_enabled: true,
    ...initial,
  };

  const [contextWindow, setContextWindow] = useState(init.context_window_tokens);
  const [keepRecent, setKeepRecent] = useState(init.context_keep_recent_messages);
  const [memoryInjection, setMemoryInjection] = useState(init.memory_injection_count);
  const [memoryEnabled, setMemoryEnabled] = useState(init.memory_enabled);
  const [status, setStatus] = useState("");

  // 同步 initial(JSX 重渲染时,父组件传新值)
  useEffect(() => {
    setContextWindow(initial.context_window_tokens ?? 30000);
    setKeepRecent(initial.context_keep_recent_messages ?? 10);
    setMemoryInjection(initial.memory_injection_count ?? 10);
    setMemoryEnabled(initial.memory_enabled ?? true);
  }, [initial.context_window_tokens, initial.context_keep_recent_messages, initial.memory_injection_count, initial.memory_enabled]);

  const handleSave = async () => {
    setStatus("保存中...");
    try {
      await callAction({
        name: "save_context_settings",
        payload: {
          context_window_tokens: Number(contextWindow),
          context_keep_recent_messages: Number(keepRecent),
          memory_injection_count: Number(memoryInjection),
          memory_enabled: Boolean(memoryEnabled),
        },
      });
      setStatus("✅ 已保存");
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus(`❌ 保存失败: ${e}`);
    }
  };

  const labelStyle = { display: "block", marginTop: "12px", marginBottom: "4px", fontSize: "13px", color: "#57606a", fontWeight: 500 };
  const valueStyle = { display: "inline-block", minWidth: "60px", color: "#0969da", fontWeight: 600, fontSize: "13px" };
  const inputStyle = { width: "100%", padding: "4px 8px", border: "1px solid #d0d7de", borderRadius: "4px", fontSize: "13px" };
  const btnStyle = { marginTop: "14px", padding: "6px 14px", background: "#2da44e", color: "white", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "13px" };

  return (
    <div style={{ padding: "12px 16px", border: "1px solid #d0d7de", borderRadius: "6px", background: "#f6f8fa", fontSize: "13px" }}>
      <h4 style={{ margin: "0 0 8px 0", fontSize: "14px" }}>⚙️ 上下文与记忆设置</h4>

      <label style={labelStyle}>
        上下文窗口上限 (tokens):<span style={valueStyle}> {contextWindow}</span>
        <input
          type="range"
          min="5000"
          max="100000"
          step="1000"
          value={contextWindow}
          onChange={(e) => setContextWindow(e.target.value)}
          style={{ width: "100%", marginTop: "4px" }}
        />
        <div style={{ fontSize: "11px", color: "#6e7781" }}>5k-100k,默认 30k。LLM 输入超此值时自动压缩。</div>
      </label>

      <label style={labelStyle}>
        保留最近消息条数:<span style={valueStyle}> {keepRecent}</span>
        <input
          type="range"
          min="2"
          max="30"
          step="1"
          value={keepRecent}
          onChange={(e) => setKeepRecent(e.target.value)}
          style={{ width: "100%", marginTop: "4px" }}
        />
        <div style={{ fontSize: "11px", color: "#6e7781" }}>2-30,默认 10。压缩时保留这么多条原文不摘要。</div>
      </label>

      <label style={labelStyle}>
        注入长期记忆条数:<span style={valueStyle}> {memoryInjection}</span>
        <input
          type="range"
          min="0"
          max="30"
          step="1"
          value={memoryInjection}
          onChange={(e) => setMemoryInjection(e.target.value)}
          style={{ width: "100%", marginTop: "4px" }}
        />
        <div style={{ fontSize: "11px", color: "#6e7781" }}>0-30,默认 10。每轮 query 检索 top-K 注入 system prompt。</div>
      </label>

      <label style={{ ...labelStyle, display: "flex", alignItems: "center", gap: "6px" }}>
        <input
          type="checkbox"
          checked={memoryEnabled}
          onChange={(e) => setMemoryEnabled(e.target.checked)}
        />
        启用长期记忆(每 3 轮对话后后台抽取 facts)
      </label>

      <button onClick={handleSave} style={btnStyle}>保存</button>
      {status && <div style={{ marginTop: "8px", fontSize: "12px" }}>{status}</div>}
    </div>
  );
}
