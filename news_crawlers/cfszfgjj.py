# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, date
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

CFSZFGJJ_INDEX = "https://www.cfszfgjj.cn/zcfg/index.jhtml"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return CFSZFGJJ_INDEX
    return f"https://www.cfszfgjj.cn/zcfg/index_{page_no - 1}.jhtml"


def _extract_page_items(page_url: str, html: str, since_date: date) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    has_older_item = False

    # 页面中条目形如: [标题](link)YYYY-MM-DD
    # 找所有带 href 的 a 标签，取其文本或 title，再在相邻文本中寻找日期
    for a in soup.find_all("a", href=True):
        href = norm(a.get("href") or "")
        if not href:
            continue

        title = norm(a.get("title") or a.get_text(" ", strip=True))
        if not title:
            continue

        # 在 a 标签后面的文本中寻找日期 YYYY-MM-DD
        parent = a.parent
        parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", parent_text)
        if not m and parent and parent.parent:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", norm(parent.parent.get_text(" ", strip=True)))
        if not m:
            continue

        dt = parse_ymd(m.group(1))
        if not dt:
            continue

        if dt.date() < since_date:
            has_older_item = True
            continue

        full_url = urljoin(page_url, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        results.append({
            "title": mark_income_related(title),
            "url": full_url,
            "date": dt,
            "source": "cfszfgjj_zcfg",
        })

    return results, has_older_item


def crawl_cfszfgjj_policy(current_time: datetime | None = None, max_pages: int = 5) -> list[dict]:
    """抓取赤峰市住房公积金中心-政策法规，返回近24小时内条目。"""
    now = current_time or now_cn()
    since_date = (now - timedelta(days=1)).date()
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[CFSZFGJJ] fetch failed(page={page_no}): {e}")
            break

        if resp.status_code != 200:
            break

        page_items, has_older_item = _extract_page_items(page_url, resp.text, since_date)
        if not page_items and page_no == 1:
            break

        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)

        if has_older_item:
            break

    results.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return results
