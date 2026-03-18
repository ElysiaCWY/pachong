# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== HR价值网：快讯 =====================
HRVALUE_KUAI_URL = "https://www.hrvalue.com.cn/kuai/"


def _parse_date_only(text: str):
    """解析列表日期（仅到天）：YYYY/MM/DD 或 YYYY-MM-DD。"""
    s = norm(text)
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", s)
    if not m:
        return None

    try:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d).replace(tzinfo=now_cn().tzinfo)
    except Exception:
        return None


def crawl_hrvalue_kuai():
    """
    抓取 HR价值网快讯：
    - 列表页无独立详情链接，使用列表页 URL 作为详情链接。
    - 仅保留近 24 小时发布的快讯（基于列表日期字段过滤）。
    """
    max_items = int(os.getenv("HRVALUE_KUAI_MAX_ITEMS", "10"))
    now = now_cn()
    cutoff = now - timedelta(hours=24)

    s = make_session()
    try:
        r = s.get(HRVALUE_KUAI_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"HRValue Kuai fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    seen_titles = set()

    for li in soup.select("div.ins-kuai ul li"):
        title_node = li.find("h1")
        body_node = li.find("h2")
        date_node = li.find("h3")

        title = norm(title_node.get_text(" ", strip=True)) if title_node else ""
        if not title or len(title) < 6:
            continue
        if title in seen_titles:
            continue

        pub_dt = _parse_date_only(date_node.get_text(" ", strip=True) if date_node else "")
        if not pub_dt:
            continue

        # 站点仅提供到“天”的时间精度，这里按当天 00:00 参与 24h 判断。
        if pub_dt < cutoff:
            continue

        raw_content = norm(body_node.get_text(" ", strip=True)) if body_node else ""
        seen_titles.add(title)
        results.append(
            {
                "title": title,
                "url": HRVALUE_KUAI_URL,
                "source": "hrvalue_kuai",
                "published_at": pub_dt.strftime("%Y-%m-%d"),
                "raw_content": raw_content,
            }
        )

        if len(results) >= max_items:
            break

    return results
