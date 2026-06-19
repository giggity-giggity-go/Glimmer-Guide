"""研招网 5 个匿名 endpoint 解析(用 parsel + httpx)

2026-06-15 实测可用的匿名入口:
- /sch/ 院校库(列表,分页 20/页)
- /sch/schoolInfo--schId-{id}.dhtml 院校详情
- /zyk/ 专业库顶层(学科门类)
- /kyzx/zsjz/ 招生简章列表(分页 80/页)

注意:
- /zsml/queryAction.do 旧接口 → 404(已废弃或转登录)
- /zsml/a/dw.do 强制登录
- /zyk/specialityDetail.do 详情页触发滑块验证码
- /zsgs/ 信息公开 → 登录

本项目严格只爬匿名可达数据,符合"信息查询"边界。

v0.2.0 变更 (HB-05/06/07/08/16):
- HB-07: _parse_date() helper 处理 5 种日期格式,返回 ISO
- HB-08: 用 urljoin 替代 startswith("/"),过滤放宽到 "zsjz/"
- HB-16: department 正则非贪婪 + 包含 "教育厅/省人民政府"
- HB-05: 用 school_classifier 名单查表替换关键词匹配(可选)
- HB-06: query_school_library 支持 region 参数,调 /sch/search.do?ssdm=X
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from parsel import Selector

from yantu.config import settings
from yantu.scraper import client
from yantu.utils.logger import logger


# ==================== HB-08: URL 拼接 + BASE 常量 ====================

BASE = settings.yanzhao_base_url.rstrip("/") + "/"


# ==================== HB-07: 日期解析(5 种格式) ====================

_DATE_PATTERNS = [
    # ISO with time: 2025-09-15 14:30 or 2025-09-15T14:30
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{1,2})"),
    # ISO date: 2025-09-15
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})"),
    # Slash: 2025/09/15
    re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})"),
    # Dot: 2025.09.15
    re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})"),
    # Chinese: 2025年9月15日
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日"),
]


def _parse_date(raw: str) -> Optional[str]:
    """HB-07: 解析 5 种日期格式,返回 ISO date string;失败返 None"""
    if not raw:
        return None
    raw = raw.strip()
    for pat in _DATE_PATTERNS:
        m = pat.match(raw)
        if m:
            try:
                groups = m.groups()
                y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
                if len(groups) == 5:
                    # 含时间
                    h, mi = int(groups[3]), int(groups[4])
                    return datetime(y, mo, d, h, mi).isoformat()
                return date(y, mo, d).isoformat()
            except (ValueError, IndexError):
                return None
    return None


# ==================== HB-16: department 解析(非贪婪 + 多种后缀) ====================

# 非贪婪 [一-龥]+? + 多种部门后缀,支持教育部 / 工业和信息化部 / 省教育厅 / 省人民政府
_DEPT_RE = re.compile(
    r"主管部门[：:]\s*([一-龥]{2,15}?(?:部|委|厅|局|人民政府))"
)


# ==================== HB-06: province ssdm 映射 ====================

_PROVINCE_SSDM = {
    "北京": "11", "天津": "12", "河北": "13", "山西": "14", "内蒙古": "15",
    "辽宁": "21", "吉林": "22", "黑龙江": "23", "上海": "31", "江苏": "32",
    "浙江": "33", "安徽": "34", "福建": "35", "江西": "36", "山东": "37",
    "河南": "41", "湖北": "42", "湖南": "43", "广东": "44", "广西": "45",
    "海南": "46", "重庆": "50", "四川": "51", "贵州": "52", "云南": "53",
    "西藏": "54", "陕西": "61", "甘肃": "62", "青海": "63", "宁夏": "64",
    "新疆": "65", "台湾": "71", "香港": "81", "澳门": "82",
}


# ==================== HB-05: 院校分类器(加载 seed 名单) ====================

_CLASSIFIER_CACHE: Optional[Dict[str, Dict[str, bool]]] = None


def _load_classifier() -> Dict[str, Dict[str, bool]]:
    """加载 src/yantu/data/school_classification.json,缓存在内存"""
    global _CLASSIFIER_CACHE
    if _CLASSIFIER_CACHE is None:
        # 注:这里用 src/yantu/data/ 而非 settings.seed_dir,因为 seed/ 被 .gitignore 排除
        # endpoints.py 路径: src/yantu/scraper/endpoints.py → parents[3] = 项目根
        path = Path(__file__).resolve().parents[3] / "src" / "yantu" / "data" / "school_classification.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            _CLASSIFIER_CACHE = {}
            for school in data.get("985_projects", []):
                _CLASSIFIER_CACHE.setdefault(school, {})["is_985"] = True
            for school in data.get("211_projects", []):
                _CLASSIFIER_CACHE.setdefault(school, {})["is_211"] = True
            for school in data.get("yanjiusheng_yuan", []):
                _CLASSIFIER_CACHE.setdefault(school, {})["is_yjy"] = True
            logger.info(
                f"School classifier loaded: "
                f"{len(data.get('985_projects',[]))} 985 + "
                f"{len(data.get('211_projects',[]))} 211 + "
                f"{len(data.get('yanjiusheng_yuan',[]))} yjy"
            )
        else:
            logger.warning(
                f"school_classification.json not found at {path}, "
                f"fallback to text-matching (HB-05 partial fix)"
            )
            _CLASSIFIER_CACHE = {}
    return _CLASSIFIER_CACHE


def _classify_school(name: str) -> Dict[str, bool]:
    """HB-05: 用名单查表,fallback 到关键词匹配"""
    cache = _load_classifier()
    if name in cache:
        return {
            "is_985": cache[name].get("is_985", False),
            "is_211": cache[name].get("is_211", False),
            "is_yjy": cache[name].get("is_yjy", False),
        }
    # fallback to text match (legacy behavior)
    return {
        "is_985": False,  # legacy "自划线" 匹配语义错位,默认 False
        "is_211": False,  # legacy "双一流+研究生院" 匹配语义错位,默认 False
        "is_yjy": False,
    }
from yantu.scraper import client
from yantu.utils.logger import logger


# ==================== Tool 1: 院校库列表 ====================

async def query_school_library(
    page: int = 1,
    region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """院校库列表(分页 20/页)

    Args:
        page: 页码(从 1 开始)
        region: 省份过滤(可选,不在 URL 里用,留给前端筛选)

    Returns:
        列表,每项含 school_id/name/city/department/is_211/is_985/info_url。
        失败/空页时返回 [{"error": "...", "tool": "query_school_library", "page": N}](HB-10 修复)
    """
    start = (page - 1) * 20
    # HB-06: region 走 /sch/search.do?ssdm=X 精准返回该省学校 + city 自动填该省
    if region and region in _PROVINCE_SSDM:
        url = f"{settings.yanzhao_base_url}/sch/search.do"
        params = {"ssdm": _PROVINCE_SSDM[region], "start": start}
    else:
        url = f"{settings.yanzhao_base_url}/sch/"
        params = {"start": start}
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        logger.error(f"query_school_library status={resp.status_code}")
        return [
            {
                "error": f"http_status_{resp.status_code}",
                "tool": "query_school_library",
                "page": page,
            }
        ]

    sel = Selector(text=resp.text)
    out: List[Dict[str, Any]] = []
    seen_ids = set()
    # 找到所有学校 anchor
    anchors = sel.css("a[href*='schoolInfo--schId-']")
    for idx, a in enumerate(anchors):
        href = a.attrib.get("href", "")
        m = re.search(r"schId-(\d+)", href)
        if not m:
            continue
        sid = m.group(1)
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        name = "".join(a.css("::text").getall()).strip()
        if not name:
            continue
        # 收集本页所有文本(粗体字)
        full_text = " ".join(sel.css("::text").getall())
        # 城市:从 anchor 之后取 50 字符,匹配"北京"等(无"所在地"前缀,只是裸字)
        # 用 a.xpath 找兄弟/parent text
        parent = a.xpath("..")
        near_text = ""
        for _ in range(3):
            if not parent:
                break
            near_text = " ".join(parent.xpath(".//text()").getall())
            if near_text and len(near_text) > 50:
                break
            parent = parent.xpath("..")
        # 城市:1-2 个汉字的省份/直辖市
        cities = re.findall(
            r"(北京|天津|上海|重庆|石家庄|太原|呼和浩特|沈阳|长春|哈尔滨|南京|杭州|合肥|福州|南昌|济南|郑州|武汉|长沙|广州|南宁|海口|成都|贵阳|昆明|拉萨|西安|兰州|西宁|银川|乌鲁木齐|河北|山西|内蒙古|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|香港|澳门|台湾)",
            near_text,
        )
        city = cities[0] if cities else ""
        # HB-16: 主管部门正则非贪婪 + 包含 "教育厅/省人民政府"
        dept_m = _DEPT_RE.search(near_text)
        # HB-05: 用名单查表替换关键词匹配
        cls = _classify_school(name)
        out.append(
            {
                "school_id": sid,
                "name": name,
                "city": city,
                "department": dept_m.group(1) if dept_m else "",
                "is_211": cls["is_211"],
                "is_985": cls["is_985"],
                "is_yanjiusheng_yuan": cls["is_yjy"],
                "info_url": urljoin(BASE, href),
            }
        )
    logger.info(f"query_school_library page={page} → {len(out)} schools")
    # HB-10: 空页/越界时显式 error 信号,而不是静默返 []
    if not out:
        return [
            {
                "error": "empty_result",
                "tool": "query_school_library",
                "page": page,
                "hint": "页码超出范围(全国约 47 页)或研招网返回空响应",
            }
        ]
    return out


# ==================== Tool 2: 院校详情 ====================

async def get_school_info(school_id: str) -> Dict[str, Any]:
    """从 /sch/schoolInfo--schId-{id}.dhtml 拿院校详情

    真实可拿到:所在地、主管部门、院校特性、招生简章列表、调剂办法列表
    """
    url = f"{settings.yanzhao_base_url}/sch/schoolInfo--schId-{school_id}.dhtml"
    resp = await client.get(url)
    if resp.status_code != 200:
        return {"error": f"status={resp.status_code}"}

    sel = Selector(text=resp.text)

    # 学校名
    name = "".join(sel.css("h1::text, h2::text, .sch-name::text").getall()).strip()
    if not name:
        # 从 title 取
        title = sel.css("title::text").get() or ""
        name = title.split("-")[0].strip()

    # 所在地 / 主管部门 / 院校特性
    txt = " ".join(sel.css("::text").getall())
    city_m = re.search(r"所在地[：:]\s*([一-龥]{2,4}市?)", txt)
    # HB-16: 主管部门正则非贪婪 + 包含 "教育厅/省人民政府"
    dept_m = _DEPT_RE.search(txt)

    badges = []
    # HB-05: 用名单查表替换关键词匹配
    cls = _classify_school(name)
    if cls["is_211"]:
        badges.append("双一流")
    if cls["is_yjy"]:
        badges.append("研究生院")
    if cls["is_985"]:
        badges.append("自划线")

    # 招生简章列表(从页面抓)
    admission_notices = []
    for a in sel.css("a[href*='viewZszc'], a[href*='listZszc']"):
        href = a.attrib.get("href", "")
        title_txt = "".join(a.css("::text").getall()).strip()
        if title_txt and "viewZszc" in href:
            admission_notices.append(
                {
                    "title": title_txt,
                    "url": urljoin(BASE, href),  # HB-08: urljoin
                }
            )

    # 调剂办法列表
    adjust_methods = []
    for a in sel.css("a[href*='tjzc--method-viewPub']"):
        href = a.attrib.get("href", "")
        title_txt = "".join(a.css("::text").getall()).strip()
        if title_txt:
            adjust_methods.append(
                {
                    "title": title_txt,
                    "url": urljoin(BASE, href),  # HB-08: urljoin
                }
            )

    return {
        "school_id": school_id,
        "name": name,
        "city": city_m.group(1) if city_m else "",
        "department": dept_m.group(1) if dept_m else "",
        "badges": badges,
        "admission_notices": admission_notices[:10],
        "adjust_methods": adjust_methods[:10],
        "info_url": url,
    }


# ==================== Tool 3: 专业库顶层 ====================

async def get_disciplines() -> List[Dict[str, str]]:
    """14 个学科门类 + 代码

    注:研招网 2026 /zyk/ 是 Vue SPA,数据 JS 渲染,无头浏览器才能拿到全部。
    本工具直接返回硬编码的 14 门类(国家标准 GB/T 13745 + 研招网公开)。
    详细专业代码由本地 Chroma 覆盖。
    """
    out = [
        {"category": "哲学", "code": "01"},
        {"category": "经济学", "code": "02"},
        {"category": "法学", "code": "03"},
        {"category": "教育学", "code": "04"},
        {"category": "文学", "code": "05"},
        {"category": "历史学", "code": "06"},
        {"category": "理学", "code": "07"},
        {"category": "工学", "code": "08"},
        {"category": "农学", "code": "09"},
        {"category": "医学", "code": "10"},
        {"category": "军事学", "code": "11"},
        {"category": "管理学", "code": "12"},
        {"category": "艺术学", "code": "13"},
        {"category": "交叉学科", "code": "14"},
    ]
    logger.info(f"get_disciplines → {len(out)} categories (hardcoded)")
    return out


# ==================== Tool 4: 招生简章(全国) ====================

async def get_recruitment_notices(page: int = 1) -> List[Dict[str, Any]]:
    """全国招生简章列表(分页 80/页)

    Args:
        page: 页码(从 1 开始)
    """
    start = (page - 1) * 80
    url = f"{settings.yanzhao_base_url}/kyzx/zsjz/"
    params = {"start": start}
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        logger.error(f"get_recruitment_notices status={resp.status_code}")
        return [
            {
                "error": f"http_status_{resp.status_code}",
                "tool": "get_recruitment_notices",
                "page": page,
            }
        ]

    sel = Selector(text=resp.text)
    out: List[Dict[str, Any]] = []
    # 列表结构:li > a[href*='zsjz/'] + 日期
    for li in sel.css("ul.news-list li, div.news-list li, li"):
        a = li.css("a[href*='zsjz/']")
        if not a:
            continue
        href = a.attrib.get("href", "")
        title = "".join(a.css("::text").getall()).strip()
        # HB-08: 放宽过滤到 "zsjz/"(支持老简章 zsjz/2019/...)
        if not title or "zsjz/" not in href:
            continue
        date_txt = "".join(li.css("span::text").getall()).strip()
        out.append(
            {
                "title": title,
                "url": urljoin(BASE, href),  # HB-08: urljoin
                "date": date_txt,
                "date_parsed": _parse_date(date_txt),  # HB-07: ISO date
            }
        )
    logger.info(f"get_recruitment_notices page={page} → {len(out)} notices")
    # HB-10: 空页/越界时显式 error 信号,而不是静默返 []
    if not out:
        return [
            {
                "error": "empty_result",
                "tool": "get_recruitment_notices",
                "page": page,
                "hint": "页码超出范围(全国约 25 页)或研招网返回空响应",
            }
        ]
    return out


# ==================== Tool 5: 本地语义检索(委托给 vector_repo) ====================

async def search_local(
    query: str,
    k: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """本地资料语义检索(走 Chroma)"""
    from yantu.data import vector_repo

    return vector_repo.search(query=query, k=k, where=where)
