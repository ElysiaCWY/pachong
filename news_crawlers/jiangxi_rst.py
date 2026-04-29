# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from .common import make_session, now_cn, norm, parse_ymd, mark_income_related


JX_BASE = "https://rst.jiangxi.gov.cn"
JX_POLICY_JSON_URL = "https://rst.jiangxi.gov.cn/jxsrlzyhshbzt/col5115/col5115-articleList.json"
JX_NORM_INDEX_URL = "https://rst.jiangxi.gov.cn/jxsrlzyhshbzt/col/col65577/index.html"
JX_NORM_JSON_FALLBACK_URL = "https://rst.jiangxi.gov.cn/jxsrlzyhshbzt/col47819/col47819-articleList.json"


def _extract_normative_json_url(index_html: str) -> str:
    html = index_html or ""

    m_agg = re.search(r'"code":"col65577".*?"aggChannelIds":"(\d+)"', html, flags=re.S)
    if not m_agg:
        return JX_NORM_JSON_FALLBACK_URL
    agg_id = m_agg.group(1)

    m_json = re.search(rf'"id":"{agg_id}".*?"articleJson":"([^"]+)"', html, flags=re.S)
    if not m_json:
        return JX_NORM_JSON_FALLBACK_URL

    path = m_json.group(1)
    return urljoin(JX_BASE, path)


def _safe_unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s


def _parse_items_from_json_text(raw_text: str, source: str) -> list[dict]:
    text = raw_text or ""
    items = []

    # 优先按标准 JSON 解析
    for strict in (True, False):
        try:
            data = json.loads(text, strict=strict)
            for obj in data if isinstance(data, list) else []:
                title = norm(str(obj.get("title") or ""))
                pub = norm(str(obj.get("pubDate") or ""))

                urls_raw = obj.get("urls")
                pc = ""
                if isinstance(urls_raw, str) and urls_raw:
                    try:
                        pc = norm(str((json.loads(urls_raw) or {}).get("pc") or ""))
                    except Exception:
                        pc = ""
                elif isinstance(urls_raw, dict):
                    pc = norm(str(urls_raw.get("pc") or ""))

                if not title or not pub or not pc:
                    continue

                dt = parse_ymd(pub[:10])
                if not dt:
                    continue

                items.append(
                    {
                        "title": mark_income_related(title),
                        "url": urljoin(JX_BASE, pc),
                        "date": dt,
                        "source": source,
                    }
                )
            if items:
                return items
        except Exception:
            pass

    # 兜底：正则抽取核心字段，容忍源 JSON 轻微不规范
    pattern = re.compile(
        r'"title":"(?P<title>.*?)".*?"pubDate":"(?P<pub>20\d{2}-\d{2}-\d{2}[^"]*)".*?'
        r'"urls":"\\{\\"pc\\":\\"(?P<pc>.*?)\\"\\}"',
        flags=re.S,
    )
    for m in pattern.finditer(text):
        title = norm(_safe_unescape(m.group("title")))
        pub = norm(_safe_unescape(m.group("pub")))
        pc = norm(_safe_unescape(m.group("pc")))
        if not title or not pub or not pc:
            continue

        dt = parse_ymd(pub[:10])
        if not dt:
            continue

        items.append(
            {
                "title": mark_income_related(title),
                "url": urljoin(JX_BASE, pc),
                "date": dt,
                "source": source,
            }
        )

    return items


def _fetch_text(session, url: str, referer: str | None = None) -> str:
    headers = {"Referer": referer} if referer else None
    r = session.get(url, timeout=20, headers=headers)
    r.encoding = r.apparent_encoding or "utf-8"
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {url}")
    return r.text


def crawl_jiangxi_rst_policy(current_time: datetime | None = None) -> list[dict]:
    """
    抓取江西省人社厅：规范性文件 + 政策文件。
    仅保留近24小时发布（按日期粒度）的标题与链接。
    """
    now = current_time or now_cn()
    since_date = (now - timedelta(hours=24)).date()
    today = now.date()

    session = make_session()
    results = []
    seen = set()

    # 1) 规范性文件：col65577 为聚合栏目，实际取其 agg 频道 articleList
    try:
        norm_index_html = _fetch_text(session, JX_NORM_INDEX_URL)
        norm_json_url = _extract_normative_json_url(norm_index_html)
        norm_json_text = _fetch_text(session, norm_json_url, referer=JX_NORM_INDEX_URL)
        norm_items = _parse_items_from_json_text(norm_json_text, "jiangxi_rst_normative")
    except Exception as e:
        print(f"[JiangxiRST] normative fetch failed: {e}")
        norm_items = []

    # 2) 政策文件：col5115
    try:
        policy_json_text = _fetch_text(session, JX_POLICY_JSON_URL, referer="https://rst.jiangxi.gov.cn/jxsrlzyhshbzt/col/col5115/index.html")
        policy_items = _parse_items_from_json_text(policy_json_text, "jiangxi_rst_policy")
    except Exception as e:
        print(f"[JiangxiRST] policy fetch failed: {e}")
        policy_items = []

    for it in norm_items + policy_items:
        dt = it["date"]
        if dt > today:
            continue
        if dt < since_date:
            continue
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        results.append(it)

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results
