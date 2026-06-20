// MemoryPanel.jsx
// v0.3.0-beta:长期记忆列表面板
// Chainlit 通过 GET /public/elements/MemoryPanel.jsx 加载
// 显示所有 fact(分 fact_type 分组),支持删除 + 软删标记
// 数据:props.facts 一次性传入(由 on_chat_start 调 list_memories action 取)

import { useState } from "react";

const FACT_TYPE_LABELS = {
  user_attribute: { label: "用户属性", color: "#0969da" },
  preference: { label: "偏好", color: "#bf3989" },
  conversation_outcome: { label: "会话结论", color: "#1a7f37" },
  open_question: { label: "未解决问题", color: "#9a6700" },
  person_mention: { label: "提及", color: "#6e7781" },
  timeline_event: { label: "时间事件", color: "#6e7781" },
};

export default function MemoryPanel({ initial = [] }) {
  const [facts, setFacts] = useState(initial);
  const [status, setStatus] = useState("");

  const handleDelete = async (factId) => {
    if (!confirm(`删除 fact #${factId}?`)) return;
    setStatus(`删除 #${factId}...`);
    try {
      await callAction({
        name: "delete_memory_fact",
        payload: { fact_id: factId },
      });
      // 本地移除(避免依赖后端回包刷新)
      setFacts(facts.filter((f) => f.id !== factId));
      setStatus(`✅ 已删除 #${factId}`);
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus(`❌ 删除失败: ${e}`);
    }
  };

  const containerStyle = { padding: "12px 16px", border: "1px solid #d0d7de", borderRadius: "6px", background: "#f6f8fa", fontSize: "13px", maxHeight: "400px", overflowY: "auto" };
  const factStyle = { padding: "8px 10px", marginBottom: "6px", background: "white", borderRadius: "4px", border: "1px solid #d0d7de", fontSize: "12px" };
  const typeBadgeStyle = (color) => ({ display: "inline-block", padding: "1px 6px", background: color, color: "white", borderRadius: "3px", fontSize: "10px", fontWeight: 600, marginRight: "6px" });

  // 按 fact_type 分组
  const groups = {};
  for (const f of facts) {
    if (!groups[f.fact_type]) groups[f.fact_type] = [];
    groups[f.fact_type].push(f);
  }
  const sortedTypes = Object.keys(groups).sort();

  return (
    <div style={containerStyle}>
      <h4 style={{ margin: "0 0 8px 0", fontSize: "14px" }}>🧠 长期记忆 ({facts.length} 条)</h4>

      {facts.length === 0 && (
        <div style={{ color: "#6e7781", fontSize: "12px", padding: "8px 0" }}>
          暂无记忆。开启长期记忆后,每 3 轮对话自动抽取。
        </div>
      )}

      {sortedTypes.map((ftype) => {
        const cfg = FACT_TYPE_LABELS[ftype] || { label: ftype, color: "#6e7781" };
        return (
          <div key={ftype} style={{ marginBottom: "10px" }}>
            <div style={{ fontSize: "12px", color: "#57606a", marginBottom: "4px", fontWeight: 600 }}>
              {cfg.label} ({groups[ftype].length})
            </div>
            {groups[ftype].map((f) => (
              <div key={f.id} style={factStyle}>
                <div style={{ marginBottom: "4px" }}>
                  <span style={typeBadgeStyle(cfg.color)}>{ftype}</span>
                  {f.is_deleted && <span style={{ ...typeBadgeStyle("#9a6700"), marginLeft: "4px" }}>⚠️ 来自已删除会话</span>}
                  {f.subject && <span style={{ color: "#57606a", fontSize: "11px" }}> · {f.subject}</span>}
                </div>
                <div style={{ color: "#1f2328" }}>{f.text}</div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px", color: "#6e7781", fontSize: "10px" }}>
                  <span>conf={f.confidence?.toFixed(2) || "?"} · 访问 {f.access_count || 0} 次</span>
                  <button onClick={() => handleDelete(f.id)} style={{ background: "transparent", border: "none", color: "#cf222e", cursor: "pointer", fontSize: "11px" }}>
                    🗑 删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {status && <div style={{ marginTop: "8px", fontSize: "12px" }}>{status}</div>}
    </div>
  );
}
