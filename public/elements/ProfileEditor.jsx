// ProfileEditor.jsx
// 文件路径必须: D:\WORKSTATION\Glimmer Guide\public\elements\ProfileEditor.jsx
// Chainlit 通过 GET /public/elements/ProfileEditor.jsx 加载
// props.initial = 当前用户画像 dict(从 Python get_profile() 传过来)

import { useState } from "react";

export default function ProfileEditor() {
  const init = props.initial || {};
  const initScores = init.scores || {};
  const initPrefs = init.preferences || {};

  // scores
  const [politics, setPolitics] = useState(initScores.politics || 0);
  const [english, setEnglish] = useState(initScores.english_2 || 0);
  const [math, setMath] = useState(initScores.math || 0);

  // preferences
  const [avoidMath, setAvoidMath] = useState(
    initPrefs.avoid_math !== undefined ? initPrefs.avoid_math : true
  );
  const [avoid985, setAvoid985] = useState(
    initPrefs.avoid_985 !== undefined ? initPrefs.avoid_985 : true
  );
  const [keywords, setKeywords] = useState(
    initPrefs.specialty_keywords || ""
  );

  const [status, setStatus] = useState("");

  const handleSave = async () => {
    setStatus("保存中...");
    try {
      await callAction({
        name: "save_profile",
        payload: {
          scores: {
            politics: Number(politics),
            english_2: Number(english),
            math: Number(math),
          },
          preferences: {
            avoid_math: avoidMath,
            avoid_985: avoid985,
            specialty_keywords: keywords,
          },
        },
      });
      setStatus("✅ 已保存(可关此面板)");
    } catch (e) {
      setStatus(`❌ 保存失败: ${e}`);
    }
  };

  const handleReset = async () => {
    setStatus("重置中...");
    try {
      await callAction({ name: "reset_profile", payload: {} });
      setStatus("↩️ 已重置为默认值");
    } catch (e) {
      setStatus(`❌ 重置失败: ${e}`);
    }
  };

  const inputStyle = {
    padding: "4px 8px",
    border: "1px solid #d0d7de",
    borderRadius: "4px",
    fontSize: "14px",
    width: "80px",
    marginLeft: "8px",
  };

  const labelStyle = {
    display: "flex",
    alignItems: "center",
    marginBottom: "8px",
    fontSize: "14px",
  };

  const fieldsetStyle = {
    border: "1px solid #e1e4e8",
    borderRadius: "6px",
    padding: "10px 14px",
    marginBottom: "12px",
  };

  const legendStyle = {
    fontWeight: 600,
    fontSize: "14px",
    color: "#1f2328",
    padding: "0 6px",
  };

  return (
    <div
      style={{
        border: "1px solid #d0d7de",
        borderRadius: "8px",
        padding: "14px 16px",
        margin: "8px 0",
        background: "#ffffff",
        fontFamily: "inherit",
      }}
    >
      <h3 style={{ margin: "0 0 12px 0", fontSize: "16px" }}>
        📝 编辑用户画像
      </h3>

      {/* 分数 */}
      <fieldset style={fieldsetStyle}>
        <legend style={legendStyle}>📊 分数</legend>
        <label style={labelStyle}>
          政治:
          <input
            type="number"
            min="0"
            max="100"
            value={politics}
            onChange={(e) => setPolitics(e.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          英语:
          <input
            type="number"
            min="0"
            max="100"
            value={english}
            onChange={(e) => setEnglish(e.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          数学:
          <input
            type="number"
            min="0"
            max="150"
            value={math}
            onChange={(e) => setMath(e.target.value)}
            style={inputStyle}
          />
        </label>
      </fieldset>

      {/* 偏好 */}
      <fieldset style={fieldsetStyle}>
        <legend style={legendStyle}>⚙️ 偏好</legend>
        <label style={labelStyle}>
          <input
            type="checkbox"
            checked={avoidMath}
            onChange={(e) => setAvoidMath(e.target.checked)}
          />
          <span style={{ marginLeft: "6px" }}>避开数学(数学分数低,优先选不考数学的专业)</span>
        </label>
        <label style={labelStyle}>
          <input
            type="checkbox"
            checked={avoid985}
            onChange={(e) => setAvoid985(e.target.checked)}
          />
          <span style={{ marginLeft: "6px" }}>排除 985 院校</span>
        </label>
        <label style={labelStyle}>
          业务课关键词(逗号分隔):
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="计算机, 信息, 农业信息技术"
            style={{ ...inputStyle, width: "240px" }}
          />
        </label>
      </fieldset>

      {/* 按钮 */}
      <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
        <button
          onClick={handleSave}
          style={{
            padding: "6px 14px",
            background: "#1f883d",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontSize: "14px",
          }}
        >
          💾 保存
        </button>
        <button
          onClick={handleReset}
          style={{
            padding: "6px 14px",
            background: "#d1242f",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
            fontSize: "14px",
          }}
        >
          ↩️ 重置
        </button>
      </div>

      {status && (
        <div
          style={{
            marginTop: "10px",
            padding: "6px 10px",
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: "4px",
            fontSize: "13px",
            color: "#1f2328",
          }}
        >
          {status}
        </div>
      )}
    </div>
  );
}
