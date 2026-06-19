"""LLM 单元测试 — HB-13 cache key + HB-14 api_key redact"""
from __future__ import annotations

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

    @patch("yantu.utils.llm.settings")
    def test_different_model_invalidates_cache(self, mock_settings):
        """模拟切换 LLM_MODEL → 新实例"""
        # 先建一个实例
        from yantu.utils.llm import _LLM_CACHE, get_llm
        mock_settings.llm_model = "model-A"
        mock_settings.llm_base_url = "https://api.test"
        mock_settings.llm_api_key = "sk-test1234567890abcdef"
        mock_settings.llm_temperature = 0.7
        a = get_llm()
        assert len(_LLM_CACHE) == 1

        # 切到 model-B → 应新建实例
        mock_settings.llm_model = "model-B"
        b = get_llm()
        assert a is not b, "model change should invalidate cache"
        assert len(_LLM_CACHE) == 2

    @patch("yantu.utils.llm.settings")
    def test_different_base_url_invalidates_cache(self, mock_settings):
        from yantu.utils.llm import _LLM_CACHE, get_llm
        mock_settings.llm_model = "model-X"
        mock_settings.llm_base_url = "https://api-a.test"
        mock_settings.llm_api_key = "sk-test1234567890abcdef"
        mock_settings.llm_temperature = 0.7
        a = get_llm()
        assert len(_LLM_CACHE) == 1

        mock_settings.llm_base_url = "https://api-b.test"
        b = get_llm()
        assert a is not b
        assert len(_LLM_CACHE) == 2


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