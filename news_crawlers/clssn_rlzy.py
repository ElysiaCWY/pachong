# -*- coding: utf-8 -*-
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .common import make_session, norm, now_cn

# ===================== 中国劳动保障新闻网：人力资源 =====================
CLSSN_RLZY_URL = "https://www.clssn.com/yw/rlzy/index.shtml"


def _parse_publish_time(article_html: str):
    """从正文页提取发布时间，格式示例：2026-03-17 13:23。"""
    if not article_html:
        return None

    # 优先匹配“YYYY-MM-DD HH:MM”
    m = re.search(r"(20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2})", article_html)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
            # 按中国时区解释
            return dt.replace(tzinfo=now_cn().tzinfo)
        except Exception:
            pass

    return None


def crawl_clssn_rlzy():
    """
    抓取中国劳动保障新闻网-人力资源板块：
    - 返回标题、链接
    - 仅保留近 24 小时发布的文章
    """
    max_items = int(os.getenv("CLSSN_MAX_ITEMS", "8"))
    now = now_cn()
    cutoff = now - timedelta(hours=24)

    s = make_session()
    try:
        r = s.get(CLSSN_RLZY_URL, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"CLSSN RLZY fetch fail: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # 先收集候选链接（列表页只拿正文文章链接）
    candidates = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not re.search(r"/20\d{2}/\d{2}/\d{2}/\d+\.html$", href):
            continue

        title = norm(a.get_text(" ", strip=True))
        if not title or len(title) < 6:
            continue

        url = urljoin(CLSSN_RLZY_URL, href)
        if url in seen:
            continue

        seen.add(url)
        candidates.append((title, url))

    results = []

    # 逐条进入正文页判断发布时间是否在24小时内
    for title, url in candidates:
        try:
            ar = s.get(url, timeout=15)
            ar.encoding = ar.apparent_encoding or "utf-8"
            pub_dt = _parse_publish_time(ar.text)
        except Exception:
            pub_dt = None

        if not pub_dt:
            continue

        if pub_dt >= cutoff:
            results.append(
                {
                    "title": title,
                    "url": url,
                    "source": "clssn_rlzy",
                    "published_at": pub_dt.strftime("%Y-%m-%d %H:%M"),
                }
            )

        if len(results) >= max_items:
            break

    return results
