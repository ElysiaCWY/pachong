# coding: utf-8
"""
爬虫：hldgjj（示例站点）- 政策查询栏目抓取
目标：抓取标题与链接，返回近24小时内发布的条目
接口：crawl_hldgjj_policy() -> list[dict]{title,url,ts}
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import List, Dict
from .common import make_session, now_cn

BASE = "https://www.hldgjj.com.cn"
LIST_URL = "https://www.hldgjj.com.cn/zccx/index.jhtml"


def _parse_datetime_from_text(s: str):
    if not s:
        return None
    s = s.strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[\sT]+(\d{1,2}):(\d{1,2}))?", s)
    if m:
        y, mo, d, hh, mm = m.groups()
        hh = hh or "0"
        mm = mm or "0"
        try:
            return datetime(int(y), int(mo), int(d), int(hh), int(mm), tzinfo=now_cn().tzinfo)
        except Exception:
            return None
    m2 = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m2:
        y, mo, d = m2.groups()
        try:
            return datetime(int(y), int(mo), int(d), tzinfo=now_cn().tzinfo)
        except Exception:
            return None
    return None


def crawl_hldgjj_policy() -> List[Dict]:
    sess = make_session()
    try:
        resp = sess.get(LIST_URL, timeout=15)
        resp.encoding = resp.apparent_encoding
        html = resp.text
    except Exception as e:
        print(f"[crawl_hldgjj_policy] fetch error: {e}")
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # 尝试找到列表项
    anchors = []
    for sel in (".list a", "ul li a", "div.list a", "div.news a", "table a"):
        anchors = soup.select(sel)
        if anchors:
            break

    if not anchors:
        anchors = [a for a in soup.find_all("a", href=True) if "/zccx/" in a.get("href", "") or a.get("href", "").endswith('.jhtml')]

    cutoff = now_cn() - timedelta(hours=24)
    items: List[Dict] = []

    for a in anchors:
        title = (a.get_text() or "").strip()
        href = a.get("href") or ""
        if not href or not title:
            continue
        if href.startswith("/"):
            url = BASE + href
        elif href.startswith("http"):
            url = href
        else:
            url = BASE.rstrip("/") + "/" + href.lstrip("/")

        pub_ts = None
        parent = a.parent
        date_text = ""
        if parent:
            date_text = " ".join([t.strip() for t in parent.strings if re.search(r"\d{4}|\d{2}", t)])
        if date_text:
            dt = _parse_datetime_from_text(date_text)
            if dt:
                pub_ts = dt
        if not pub_ts:
            try:
                dresp = sess.get(url, timeout=15)
                dresp.encoding = dresp.apparent_encoding
                dsoup = BeautifulSoup(dresp.text, "lxml")
                cand = dsoup.select_one("time, .pubtime, .date, .time, .info, .article-meta")
                if cand:
                    pub_txt = cand.get_text().strip()
                    dt = _parse_datetime_from_text(pub_txt)
                    if dt:
                        pub_ts = dt
            except Exception:
                pub_ts = None

        if not pub_ts:
            continue
        if pub_ts < cutoff:
            continue

        items.append({"title": title, "url": url, "ts": pub_ts.isoformat()})

    return items
