# -*- coding: utf-8 -*-
import os
import re
from datetime import date
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn, target_prev_workday, parse_ymd

# ===================== HR价值网：政策 =====================
HRVALUE_POLICY_URL = "https://www.hrvalue.com.cn/news/?category=13"


def _parse_ymd(text: str):
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", norm(text))
    if not m:
        return None
    try:
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    except Exception:
        return None


def crawl_hrvalue_policy():
    """
    抓取 HR价值网-政策板块。
    默认抓取上一工作日（周一抓上周五），支持 HRVALUE_POLICY_TARGET_DATE 覆盖。
    """
    override = parse_ymd(os.getenv("HRVALUE_POLICY_TARGET_DATE"))
    target = override or target_prev_workday(now_cn().date())
    max_items = int(os.getenv("HRVALUE_POLICY_MAX_ITEMS", "12"))

    s = make_session()
    try:
        r = s.get(HRVALUE_POLICY_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"HRValue Policy fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen = set()

    for li in soup.select("div.ins-news ul li"):
        a = li.find("a", href=True)
        if not a:
            continue

        href = (a.get("href") or "").strip()
        if not href:
            continue

        title_node = li.find("h1")
        title = norm(title_node.get_text(" ", strip=True) if title_node else a.get("title") or "")
        if not title or len(title) < 6:
            continue

        h3 = li.find("h3")
        spans = h3.find_all("span") if h3 else []
        date_text = spans[-1].get_text(" ", strip=True) if spans else ""
        dt = _parse_ymd(date_text)
        if not dt or dt != target:
            continue

        url = urljoin(HRVALUE_POLICY_URL, href)
        if url in seen:
            continue
        seen.add(url)

        results.append({"title": title, "url": url, "date": dt, "source": "hrvalue_policy"})
        if len(results) >= max_items:
            break

    return results
