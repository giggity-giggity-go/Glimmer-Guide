"""scraper/endpoints 单元测试 — HB-07 _parse_date + HB-06 ssdm 映射"""
from __future__ import annotations

import pytest


class TestHB07ParseDate:
    """HB-07: _parse_date 处理 5 种日期格式"""

    def test_iso_date(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025-09-15") == "2025-09-15"

    def test_iso_with_time(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025-09-15 14:30") == "2025-09-15T14:30:00"

    def test_iso_t_separator(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025-09-15T14:30") == "2025-09-15T14:30:00"

    def test_slash_format(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025/09/15") == "2025-09-15"

    def test_dot_format(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025.09.15") == "2025-09-15"

    def test_chinese_format(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025年9月15日") == "2025-09-15"

    def test_empty_returns_none(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("") is None
        assert _parse_date(None) is None

    def test_garbage_returns_none(self):
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("昨天") is None
        assert _parse_date("本周") is None
        assert _parse_date("not a date") is None

    def test_partial_format_fails_gracefully(self):
        """不完整日期不抛异常,返回 None"""
        from yantu.scraper.endpoints import _parse_date
        assert _parse_date("2025-09") is None
        assert _parse_date("2025") is None


class TestHB06ProvinceSsdm:
    """HB-06: 省份 ssdm 映射"""

    def test_direct_provinces(self):
        from yantu.scraper.endpoints import _PROVINCE_SSDM
        assert _PROVINCE_SSDM["北京"] == "11"
        assert _PROVINCE_SSDM["上海"] == "31"
        assert _PROVINCE_SSDM["湖北"] == "42"
        assert _PROVINCE_SSDM["广东"] == "44"

    def test_special_regions(self):
        from yantu.scraper.endpoints import _PROVINCE_SSDM
        assert _PROVINCE_SSDM["香港"] == "81"
        assert _PROVINCE_SSDM["澳门"] == "82"
        assert _PROVINCE_SSDM["台湾"] == "71"

    def test_all_31_provinces_present(self):
        """全国 31 省市必须全覆盖(直辖市 4 + 省 23 + 自治区 5 = 32,加 HK/MO/TW = 35)"""
        from yantu.scraper.endpoints import _PROVINCE_SSDM
        assert len(_PROVINCE_SSDM) >= 31


class TestHB05Classifier:
    """HB-05: school classifier"""

    def test_known_985_classified(self):
        from yantu.scraper.endpoints import _classify_school
        assert _classify_school("北京大学")["is_985"] is True
        assert _classify_school("清华大学")["is_985"] is True
        assert _classify_school("复旦大学")["is_985"] is True

    def test_unknown_school_no_985(self):
        from yantu.scraper.endpoints import _classify_school
        # 没在名单里的默认 is_985=False(避免假阳性)
        result = _classify_school("某某民办高校")
        assert result["is_985"] is False


class TestHB16DeptRegex:
    """HB-16: department 正则非贪婪"""

    def test_education_ministry(self):
        from yantu.scraper.endpoints import _DEPT_RE
        m = _DEPT_RE.search("主管部门:教育部")
        assert m is not None
        assert m.group(1) == "教育部"

    def test_provincial_education_department(self):
        from yantu.scraper.endpoints import _DEPT_RE
        m = _DEPT_RE.search("主管部门:湖北省教育厅")
        assert m is not None
        assert "教育厅" in m.group(1)

    def test_provincial_government(self):
        from yantu.scraper.endpoints import _DEPT_RE
        m = _DEPT_RE.search("主管部门:上海市人民政府")
        assert m is not None

    def test_greedy_no_overflow(self):
        """非贪婪不会跨多段抓到错误部门"""
        from yantu.scraper.endpoints import _DEPT_RE
        m = _DEPT_RE.search("主管部门:教育部 更多信息:工业和信息化部")
        # 非贪婪应该只匹配"教育部",不会到"工业和信息化部"
        assert m.group(1) == "教育部"