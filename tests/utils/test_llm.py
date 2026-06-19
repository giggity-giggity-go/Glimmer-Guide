"""LLM 单元测试 — HB-13 cache key + HB-14 api_key redact"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clear_llm_cache():
    """每个测试清空 _LLM_CACHE,避免污染"""
    from yantu.utils.llm import _LLM_CACHE
    _LLM_CACHE.clear()
    yield
    _LLM_CACHE.clear()


class TestHB13CacheKey:
    """HB-13: get_llm cache key 包含 (model, base_url, api_key_prefix, temperature)"""

    def test_same_key_returns_same_instance(self):
        """相同 (model, base_url, key, temp) → 同实例"""
        from yantu.utils.llm import get_llm

        a = get_llm(temperature=0.7)
        b = get_llm(temperature=0.7)
        assert a is b, "cache miss for identical keys"

    def test_different_temperature_different_instance(self):
        from yantu.utils.llm import get_llm

        a = get_llm(temperature=0.7)
        b = get_llm(temperature=0.0)
        assert a is not b, "cache should differ by temperature"

    @patch("yantu.utils.llm.resolve_vendor")
    def test_different_model_invalidates_cache(self, mock_resolve):
        """模拟切换 vendor model → 新实例(HB-13)"""
        from dataclasses import dataclass
        from yantu.utils.llm import _LLM_CACHE, get_llm

        @dataclass
        class FakeVendor:
            name: str
            model: str
            base_url: str
            api_key_env: str = "LLM_API_KEY"
            # v0.2.2: 字段名从 extra_model_kwargs 改 extra_body
            extra_body: dict = None

        # vendor-A model-X
        mock_resolve.return_value = FakeVendor(
            name="vendor-a", model="model-X", base_url="https://api.test"
        )
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test1234567890abcdef"}):
            a = get_llm()
            assert len(_LLM_CACHE) == 1

        # vendor-A model-Y(同一 vendor 不同 model → 新实例)
        mock_resolve.return_value = FakeVendor(
            name="vendor-a", model="model-Y", base_url="https://api.test"
        )
        b = get_llm()
        assert a is not b, "model change should invalidate cache"
        assert len(_LLM_CACHE) == 2

    @patch("yantu.utils.llm.resolve_vendor")
    def test_different_vendor_invalidates_cache(self, mock_resolve):
        """切换 vendor → 新实例(HB-13)"""
        from dataclasses import dataclass
        from yantu.utils.llm import _LLM_CACHE, get_llm

        @dataclass
        class FakeVendor:
            name: str
            model: str
            base_url: str
            api_key_env: str = "LLM_API_KEY"
            # v0.2.2: 字段名从 extra_model_kwargs 改 extra_body
            extra_body: dict = None

        mock_resolve.return_value = FakeVendor(
            name="vendor-a", model="model-X", base_url="https://api-a.test"
        )
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test1234567890abcdef"}):
            a = get_llm()
            assert len(_LLM_CACHE) == 1

        mock_resolve.return_value = FakeVendor(
            name="vendor-b", model="model-X", base_url="https://api-b.test"
        )
        b = get_llm()
        assert a is not b, "vendor change should invalidate cache"
        assert len(_LLM_CACHE) == 2


class TestV022ExtraBody:
    """v0.2.2: vendor 私有参数(reasoning_split)走 extra_body= 而不是 model_kwargs=

    LangChain 官方警告:model_kwargs 会被合并到 OpenAI SDK 的 create(**kwargs)
    顶层签名参数,SDK 见非标准参数直接 TypeError(reasoning_split 不是 OpenAI
    签名的一部分)。extra_body 走 HTTP body 透传,绕过签名校验。
    """

    @patch("yantu.utils.llm.resolve_vendor")
    def test_extra_body_passed_to_chatopenai(self, mock_resolve):
        """resolve_vendor 返回带 extra_body 的 VendorConfig → ChatOpenAI 应收到 extra_body= 参数"""
        from dataclasses import dataclass
        from langchain_openai import ChatOpenAI
        from yantu.utils.llm import get_llm

        @dataclass
        class FakeVendor:
            name: str
            model: str
            base_url: str
            api_key_env: str = "LLM_API_KEY"
            extra_body: dict = None

        mock_resolve.return_value = FakeVendor(
            name="minimax",
            model="MiniMax-M3",
            base_url="https://api.minimaxi.com/v1",
            extra_body={"reasoning_split": True},
        )
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test1234567890abcdef"}):
            with patch.object(ChatOpenAI, "__init__", return_value=None) as mock_init:
                get_llm(temperature=0.7)

        # 关键断言:ChatOpenAI 构造收到 extra_body={...},没有 model_kwargs
        _, kwargs = mock_init.call_args
        assert "extra_body" in kwargs, (
            f"v0.2.2: ChatOpenAI 必须收到 extra_body= 参数(传给 OpenAI SDK "
            f"extra_body 透传),实际收到: {list(kwargs.keys())}"
        )
        assert kwargs["extra_body"] == {"reasoning_split": True}, (
            f"extra_body 内容错: {kwargs['extra_body']}"
        )
        assert "model_kwargs" not in kwargs, (
            f"v0.2.2: 必须删除 model_kwargs= 参数(否则 OpenAI SDK 仍 TypeError)"
        )

    @patch("yantu.utils.llm.resolve_vendor")
    def test_extra_body_change_invalidates_cache(self, mock_resolve):
        """v0.2.2: 同 vendor/model/temp 但 extra_body 不同 → 新实例"""
        from dataclasses import dataclass
        from yantu.utils.llm import _LLM_CACHE, get_llm

        @dataclass
        class FakeVendor:
            name: str
            model: str
            base_url: str
            api_key_env: str = "LLM_API_KEY"
            extra_body: dict = None

        # 第一次: extra_body={"reasoning_split": True}
        mock_resolve.return_value = FakeVendor(
            name="minimax",
            model="MiniMax-M3",
            base_url="https://api.minimaxi.com/v1",
            extra_body={"reasoning_split": True},
        )
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test1234567890abcdef"}):
            a = get_llm()
            assert len(_LLM_CACHE) == 1

        # 第二次: extra_body 改为空(M2.7 切换到 M3 时 cache 不该命中)
        mock_resolve.return_value = FakeVendor(
            name="minimax",
            model="MiniMax-M3",
            base_url="https://api.minimaxi.com/v1",
            extra_body={},
        )
        b = get_llm()
        assert a is not b, (
            "v0.2.2: extra_body 变化必须 invalidate cache,否则 M2.7 切换 M3 会"
            "误用 M2.7 实例"
        )
        assert len(_LLM_CACHE) == 2

    @patch("yantu.utils.llm.resolve_vendor")
    def test_empty_extra_body_works(self, mock_resolve):
        """extra_body={} 空字典也合法 — 不传任何 vendor 私有参数时"""
        from dataclasses import dataclass
        from langchain_openai import ChatOpenAI
        from yantu.utils.llm import get_llm

        @dataclass
        class FakeVendor:
            name: str
            model: str
            base_url: str
            api_key_env: str = "LLM_API_KEY"
            extra_body: dict = None

        mock_resolve.return_value = FakeVendor(
            name="zhipu",
            model="glm-5.1",
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            extra_body={},
        )
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test1234567890abcdef"}):
            with patch.object(ChatOpenAI, "__init__", return_value=None) as mock_init:
                get_llm(temperature=0.7)

        _, kwargs = mock_init.call_args
        assert kwargs.get("extra_body") == {}, "空 extra_body 也应传给 ChatOpenAI"


class TestHB14RedactKey:
    """HB-14: api_key 日志 redact"""

    def test_empty_key(self):
        from yantu.utils.llm import _redact_key
        assert _redact_key("") == "<empty>"

    def test_short_key_returns_stars(self):
        from yantu.utils.llm import _redact_key
        assert _redact_key("short") == "***"

    def test_long_key_redacted_with_prefix_suffix(self):
        from yantu.utils.llm import _redact_key
        result = _redact_key("sk-1234567890abcdef")
        assert result.startswith("sk-1"), f"expected prefix preserved: {result}"
        assert "***" in result
        assert result.endswith("cdef"), f"expected suffix preserved: {result}"
        assert "1234567890ab" not in result, "middle should be hidden"

    def test_no_full_key_leak(self):
        """绝对不能从 redact 结果反推完整 key"""
        from yantu.utils.llm import _redact_key
        full_key = "sk-proj-AbCdEf1234567890XyZ9876543210MnOp"
        result = _redact_key(full_key)
        # 中间 22 字符被隐藏
        hidden_part = full_key[4:-4]
        assert hidden_part not in result, f"middle leaked: {result}"