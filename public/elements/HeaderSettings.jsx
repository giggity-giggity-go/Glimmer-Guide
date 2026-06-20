// HeaderSettings.jsx
// 文件路径: D:\WORKSTATION\Glimmer Guide\public\elements\HeaderSettings.jsx
// Chainlit 通过 GET /public/elements/HeaderSettings.jsx 加载
// 用 position: fixed 钉在右上角"说明"按钮左边
// 点击调 callAction("edit_profile") 打开设置表单

import { useState } from "react";

export default function HeaderSettings() {
  const [hover, setHover] = useState(false);

  const handleClick = async () => {
    try {
      await callAction({ name: "edit_profile", payload: {} });
    } catch (e) {
      // 用户关闭/忽略都忽略错误
    }
  };

  return (
    <button
      onClick={handleClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title="设置用户画像(分数/偏好/关键词)"
      aria-label="设置用户画像"
      style={{
        position: "fixed",
        // 钉在右上角,位于"说明"按钮(~120px from right)和"Toggle theme"按钮(~60px)之间
        top: "12px",
        right: "184px",
        zIndex: 9999,
        background: hover ? "rgba(31, 35, 40, 0.08)" : "transparent",
        border: "1px solid transparent",
        cursor: "pointer",
        fontSize: "18px",
        lineHeight: 1,
        padding: "6px 8px",
        borderRadius: "6px",
        color: "#1f2328",
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        transition: "background 0.15s, border-color 0.15s",
        fontFamily: "inherit",
      }}
    >
      <span aria-hidden="true">⚙️</span>
      <span
        style={{
          fontSize: "13px",
          fontWeight: 500,
          color: hover ? "#0969da" : "#57606a",
        }}
      >
        设置
      </span>
    </button>
  );
}
