// CollapsibleReasoning.jsx
// 文件路径必须: src/yantu/ui/.chainlit/public/elements/CollapsibleReasoning.jsx
// Chainlit 通过 GET /public/elements/CollapsibleReasoning.jsx 加载此文件
// react-runner 在浏览器里编译 + 渲染
// props 是 react-runner scope 里的全局变量,不是函数参数

import { useState } from "react";

export default function CollapsibleReasoning() {
  const [open, setOpen] = useState(props.defaultOpen || false);

  const { title, content } = props;

  return (
    <div
      style={{
        border: "1px solid #d0d7de",
        borderRadius: "8px",
        padding: "10px 14px",
        margin: "8px 0",
        fontFamily: "inherit",
        background: "#fafbfc",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          fontSize: "14px",
          fontWeight: 600,
          color: "#1f2328",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          width: "100%",
          textAlign: "left",
        }}
      >
        <span
          style={{
            display: "inline-block",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.15s",
            color: "#57606a",
            fontSize: "12px",
          }}
        >
          ▶
        </span>
        <span>{title}</span>
      </button>
      {open && (
        <pre
          style={{
            marginTop: "10px",
            marginBottom: 0,
            padding: "10px 12px",
            background: "#ffffff",
            border: "1px solid #e1e4e8",
            borderRadius: "6px",
            fontSize: "12.5px",
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            maxHeight: "420px",
            overflow: "auto",
            color: "#24292f",
            fontFamily:
              "ui-monospace, SFMono-Regular, Menlo, monospace",
          }}
        >
          {content}
        </pre>
      )}
    </div>
  );
}
