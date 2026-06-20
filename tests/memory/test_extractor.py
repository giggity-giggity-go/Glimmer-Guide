"""v0.3.0-beta extractor 测试

覆盖:
- _filter_privacy 隐私正则(身份证/手机号/银行卡)
- _parse_llm_output JSON 解析 + fence 剥离
- _serialize_messages 文本拼接
- extract_facts_async LLM mock 全流程
- should_extract 触发条件
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from yantu.data import db as db_module
from yantu.data import vector_repo
from yantu.data.models import Base, MemoryFact
from yantu.memory.extractor import (
    MIN_CONFIDENCE,
    PRIVACY_RE,
    _filter_privacy,
    _parse_llm_output,
    _serialize_messages,
    extract_facts_async,
    should_extract,
)


class TestPrivacyFilter:
    def test_身份证号_18位(self):
        assert _filter_privacy("我的身份证是 110101199003078811")

    def test_手机号_11位_1开头(self):
        assert _filter_privacy("电话 13800138000")

    def test_银行卡_16_19位(self):
        assert _filter_privacy("卡号 6222021234567890")

    def test_普通文本_不命中(self):
        assert not _filter_privacy("用户想去清华读研")

    def test_部分数字_不命中(self):
        # 短数字不应误判
        assert not _filter_privacy("分数线 360 分")


class TestParseLlmOutput:
    def test_pure_json(self):
        raw = '[{"fact_type": "user_attribute", "text": "test"}]'
        out = _parse_llm_output(raw)
        assert len(out) == 1
        assert out[0]["fact_type"] == "user_attribute"

    def test_fenced_json(self):
        """LLM 输出 ```json ... ``` 包裹(v0.2.1 教训)"""
        raw = '```json\n[{"fact_type": "user_attribute", "text": "test"}]\n```'
        out = _parse_llm_output(raw)
        assert len(out) == 1

    def test_fenced_no_lang(self):
        raw = '```\n[{"fact_type": "user_attribute", "text": "test"}]\n```'
        out = _parse_llm_output(raw)
        assert len(out) == 1

    def test_dict_with_facts_key(self):
        raw = '{"facts": [{"fact_type": "user_attribute", "text": "test"}]}'
        out = _parse_llm_output(raw)
        assert len(out) == 1

    def test_invalid_json_returns_empty(self):
        out = _parse_llm_output("not json at all")
        assert out == []

    def test_empty_string(self):
        assert _parse_llm_output("") == []


class TestSerializeMessages:
    def test_basic(self):
        msgs = [HumanMessage(content="你好"), AIMessage(content="hi")]
        out = _serialize_messages(msgs)
        assert "[human] 你好" in out
        assert "[ai] hi" in out

    def test_truncate(self):
        msgs = [HumanMessage(content="x" * 10000)]
        out = _serialize_messages(msgs)
        # 限长 4000
        assert len(out) <= 4000


class TestShouldExtract:
    def test_default_n_3(self):
        # 默认每 3 轮抽 1 次
        with patch("yantu.memory.extractor.get_setting", lambda k, d=None: {"memory_extract_every_n_turns": 3}.get(k, d)):
            assert should_extract(0) is False  # 0 不触发
            assert should_extract(1) is False  # 1 轮未到
            assert should_extract(3) is True   # 3 轮
            assert should_extract(6) is True   # 6 轮
            assert should_extract(9) is True   # 9 轮

    def test_disabled_n_0(self):
        with patch("yantu.memory.extractor.get_setting", lambda k, d=None: {"memory_extract_every_n_turns": 0}.get(k, d)):
            assert should_extract(100) is False


class TestExtractFactsAsync:
    @pytest.mark.asyncio
    async def test_no_messages_noop(self, tmp_path, monkeypatch):
        """空 messages 不调 LLM"""
        ids = await extract_facts_async("tid", [])
        assert ids == []

    @pytest.mark.asyncio
    async def test_low_confidence_filtered(self, tmp_path, monkeypatch):
        """confidence < 0.7 不写入"""
        # isolated DB
        from sqlalchemy import create_engine as _ce
        db_path = tmp_path / "test.db"
        test_engine = _ce(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        monkeypatch.setattr(db_module, "_engine", test_engine)
        Base.metadata.create_all(test_engine)
        monkeypatch.setattr(vector_repo, "_client", None)
        monkeypatch.setattr("yantu.memory.extractor.get_setting", lambda k, d=None: True if k == "memory_enabled" else d)

        # Mock LLM 返回低 confidence fact
        fake_response = MagicMock()
        fake_response.content = '[{"fact_type": "user_attribute", "text": "test", "confidence": 0.5}]'
        with patch("yantu.memory.extractor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=fake_response)
            with patch.object(vector_repo, "add_documents"):
                ids = await extract_facts_async("tid", [
                    HumanMessage(content="test msg"),
                ])

        assert ids == []  # 低 confidence 被过滤
        test_engine.dispose()

    @pytest.mark.asyncio
    async def test_privacy_text_filtered(self, tmp_path, monkeypatch):
        """含身份证号的 fact 被隐私正则丢弃"""
        from sqlalchemy import create_engine as _ce
        db_path = tmp_path / "test.db"
        test_engine = _ce(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        monkeypatch.setattr(db_module, "_engine", test_engine)
        Base.metadata.create_all(test_engine)
        monkeypatch.setattr(vector_repo, "_client", None)
        monkeypatch.setattr("yantu.memory.extractor.get_setting", lambda k, d=None: True if k == "memory_enabled" else d)

        fake_response = MagicMock()
        fake_response.content = '[{"fact_type": "user_attribute", "text": "身份证 110101199003078811", "confidence": 0.9}]'
        with patch("yantu.memory.extractor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=fake_response)
            with patch.object(vector_repo, "add_documents"):
                ids = await extract_facts_async("tid", [HumanMessage(content="x")])

        assert ids == []  # 隐私丢弃
        test_engine.dispose()

    @pytest.mark.asyncio
    async def test_valid_fact_writes_to_sqlite_chroma_store(self, tmp_path, monkeypatch):
        """合法 fact 写入 SQLite + Chroma + LangMem store"""
        from sqlalchemy import create_engine as _ce
        db_path = tmp_path / "test.db"
        test_engine = _ce(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        monkeypatch.setattr(db_module, "_engine", test_engine)
        Base.metadata.create_all(test_engine)
        monkeypatch.setattr(vector_repo, "_client", None)
        monkeypatch.setattr("yantu.memory.extractor.get_setting", lambda k, d=None: True if k == "memory_enabled" else d)
        monkeypatch.setattr("yantu.memory.extractor.embed_texts", lambda texts: [[0.1] * 5] * len(texts))
        monkeypatch.setattr("yantu.memory.extractor.add_fact_to_store", lambda *a, **kw: None)

        fake_response = MagicMock()
        fake_response.content = '[{"fact_type": "user_attribute", "text": "用户数学较弱", "subject": "数学", "confidence": 0.9, "keywords": ["数学"]}]'
        with patch("yantu.memory.extractor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=fake_response)
            with patch.object(vector_repo, "add_documents") as mock_add:
                ids = await extract_facts_async("tid-abc", [HumanMessage(content="x")])

        assert len(ids) == 1
        # SQLite 写入
        with db_module.session_scope() as s:
            f = s.get(MemoryFact, ids[0])
            assert f is not None
            assert f.fact_type == "user_attribute"
            assert f.source_thread == "tid-abc"
            assert f.confidence == 0.9
        # Chroma add 调了
        mock_add.assert_called_once()
        # 验证 collection_name
        assert mock_add.call_args.kwargs["collection_name"] == vector_repo.LONG_TERM_MEMORY_COLLECTION
        test_engine.dispose()

    @pytest.mark.asyncio
    async def test_unknown_fact_type_skipped(self, tmp_path, monkeypatch):
        """fact_type 不在 6 种内 → skip"""
        from sqlalchemy import create_engine as _ce
        db_path = tmp_path / "test.db"
        test_engine = _ce(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        monkeypatch.setattr(db_module, "_engine", test_engine)
        Base.metadata.create_all(test_engine)
        monkeypatch.setattr(vector_repo, "_client", None)
        monkeypatch.setattr("yantu.memory.extractor.get_setting", lambda k, d=None: True if k == "memory_enabled" else d)

        fake_response = MagicMock()
        fake_response.content = '[{"fact_type": "weird_type", "text": "test", "confidence": 0.9}]'
        with patch("yantu.memory.extractor.get_llm") as mock_llm:
            mock_llm.return_value.ainvoke = AsyncMock(return_value=fake_response)
            with patch.object(vector_repo, "add_documents"):
                ids = await extract_facts_async("tid", [HumanMessage(content="x")])
        assert ids == []
        test_engine.dispose()
