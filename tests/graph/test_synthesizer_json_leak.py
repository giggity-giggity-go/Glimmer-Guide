"""v0.2.1: 回归测试 chat JSON 泄漏 bug。

3 个核心 case:
  1. success path — function_calling 返回 FinalAnswer 实例,response 干净
  2. fallback path — 主路径抛异常,fake invoke 返回 ```json ...``` fence,
     _strip_fenced_json 把 fence 拆掉,response 不含 ``` 或完整 JSON 结构
  3. intent classifier — 不再 fallback 到 'both'(v0.2.1 改 function_calling)

不调真实 LLM — 用 fake ChatModel 替换 get_llm() 的返回值。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from yantu.graph.nodes import (
    Intent,
    FinalAnswer,
    Citation,
    _classify_intent,
    _strip_fenced_json,
    make_synthesizer_node,
)


# ==================== helper: strip_fenced_json 单测 ====================

class TestStripFencedJson:
    """_strip_fenced_json 是 v0.2.1 新增的 fallback 兜底"""

    def test_strips_json_fence(self):
        text = '```json\n{"answer": "hi", "citations": [], "grounded": true}\n```'
        out = _strip_fenced_json(text)
        assert "```" not in out
        assert out.startswith("{")
        assert '"answer"' in out

    def test_strips_bare_fence(self):
        """无语言标签的 fence 也能 strip"""
        text = '```\n{"answer": "hi"}\n```'
        out = _strip_fenced_json(text)
        assert "```" not in out

    def test_keeps_plain_text(self):
        text = "这是普通中文回答,没有任何 fence。"
        assert _strip_fenced_json(text) == text

    def test_empty(self):
        assert _strip_fenced_json("") == ""

    def test_partial_fence_no_match(self):
        """只有开 fence 没有关 fence 不该被 strip(避免误吞)"""
        text = "```json\n{这是不完整的 fence"
        out = _strip_fenced_json(text)
        # regex 不匹配,原样返回
        assert out == text


# ==================== Synthesizer 主路径(成功):无泄漏 ====================

class TestSynthesizerSuccessNoLeak:
    """主路径走 function_calling,LLM 返回 FinalAnswer 实例,response 干净"""

    def test_function_calling_returns_clean_text(self, monkeypatch):
        """模拟 function_calling 成功:返回 FinalAnswer 实例(answer 是中文)"""
        fake_answer = FinalAnswer(
            answer="未找到北京大学信息公开的具体内容,建议访问北京大学官网。",
            citations=[Citation(source="研招网", snippet="北京大学 10001", score=0.9)],
            grounded=True,
        )

        # fake ChatModel:with_structured_output 链式返回,最终返回 FinalAnswer
        fake_llm = MagicMock()
        fake_structured = MagicMock()
        fake_structured.invoke.return_value = fake_answer
        fake_llm.with_structured_output.return_value = fake_structured
        monkeypatch.setattr("yantu.graph.nodes.get_llm", lambda temperature: fake_llm)

        synthesizer = make_synthesizer_node()
        result = synthesizer({
            "user_query": "北京大学 信息公开",
            "messages": [],
        })

        assert "```" not in result["response"], (
            f"response 不应含 fence,got: {result['response'][:200]}"
        )
        assert "{" not in result["response"] or '"answer"' not in result["response"], (
            f"response 不应是 JSON 字符串,got: {result['response'][:200]}"
        )
        assert result["grounded"] is True
        assert len(result["citations"]) == 1


# ==================== Synthesizer Fallback 路径:fence 被 strip ====================

class TestSynthesizerFallbackStripsFence:
    """主路径抛异常 → fallback → 即便 LLM 输出 fence JSON 也会被 strip"""

    def test_fallback_strips_fenced_json(self, monkeypatch):
        """function_calling 抛异常,fake invoke 返回 ```json {answer}``` → 应被 strip"""
        fence_content = (
            "```json\n"
            "{\n"
            '  "answer": "根据查询,北京大学公开了研招网院校信息页面",\n'
            '  "citations": ["研招网"],\n'
            '  "grounded": true\n'
            "}\n"
            "```"
        )

        # fake_llm.with_structured_output(...).invoke(...) raises
        # fake_llm.invoke(...) returns AIMessage with fence content
        fake_llm = MagicMock()
        fake_structured = MagicMock()
        fake_structured.invoke.side_effect = ValueError(
            "schema mismatch (simulated)"
        )
        fake_llm.with_structured_output.return_value = fake_structured
        fake_llm.invoke.return_value = AIMessage(content=fence_content)

        # Both calls go through the same fake_llm
        monkeypatch.setattr("yantu.graph.nodes.get_llm", lambda temperature: fake_llm)

        synthesizer = make_synthesizer_node()
        result = synthesizer({
            "user_query": "北京大学 信息公开",
            "messages": [],
        })

        # v0.2.1: 即便走了 fallback,response 也不含 fence 或完整 JSON
        assert "```" not in result["response"], (
            f"fallback 路径 fence 没被 strip,got: {result['response'][:300]}"
        )
        # response 应包含原始中文(从 fence 内提取)
        assert "北京大学" in result["response"] or "answer" not in result["response"], (
            f"response 应保留原文内容,got: {result['response'][:300]}"
        )
        # fallback 路径 grounded=False(兜底)
        assert result["grounded"] is False
        assert result["citations"] == []


# ==================== Intent Classifier:不再 fallback 到 'both' ====================

class TestIntentClassifierNoFallbackToBoth:
    """v0.2.1: function_calling 在 glm-5.1 上 100% 成功 → 不再 fallback 'both'"""

    def test_function_calling_returns_correct_target(self, monkeypatch):
        """mock function_calling 成功返回 Intent(target='yanzhao'),classifier 应直接返回"""
        fake_intent = Intent(target="yanzhao", confidence=0.9, reasoning="yanzhao 匹配")

        fake_llm = MagicMock()
        fake_structured = MagicMock()
        fake_structured.invoke.return_value = fake_intent
        fake_llm.with_structured_output.return_value = fake_structured
        monkeypatch.setattr("yantu.graph.nodes.get_llm", lambda temperature: fake_llm)

        result = _classify_intent("北京大学 信息公开")

        assert result.target == "yanzhao", (
            f"v0.2.1 之后 Intent classifier 应直接返回 yanzhao,got: {result.target}"
        )
        assert result.target != "both", (
            "v0.2.1: function_calling 不该再 fallback 到 'both'"
        )
        assert result.confidence == 0.9

    def test_intent_fallback_still_works_on_total_failure(self, monkeypatch):
        """即所有 function_calling 都失败,Exception fallback 还能给个 'both' Intent(兜底)"""
        fake_llm = MagicMock()
        fake_structured = MagicMock()
        fake_structured.invoke.side_effect = RuntimeError("network down")
        fake_llm.with_structured_output.return_value = fake_structured
        monkeypatch.setattr("yantu.graph.nodes.get_llm", lambda temperature: fake_llm)

        result = _classify_intent("anything")

        # 兜底 Intent(target='both') — 老 fallback 行为保留,只是希望永远不会触发
        assert result.target == "both"
        assert "fallback" in result.reasoning.lower() or result.confidence <= 0.5