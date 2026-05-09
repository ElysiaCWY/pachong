# -*- coding: utf-8 -*-
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


INDEX_URL = "http://www.qhdgjj.com/list?code=MTA1"


def _extract_date_and_title(raw_text: str) -> tuple[datetime | None, str]:
    text = norm(raw_text)
    if not text:
        return None, ""

    # 常见：前置日期 2026-05-08 标题
    m = re.match(r"^(20\d{2}-\d{2}-\d{2})\s*(.+)$", text)
    if m:
        dt = parse_ymd(m.group(1))
        title = norm(m.group(2))
        return dt, title

    # 在其他位置寻找日期
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if m:
        dt = parse_ymd(m.group(1))
        title = norm(text.replace(m.group(1), "", 1))
        return dt, title

    return None, text


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        try:
            href = norm(a.get("href") or "")
            if not href:
                continue

            full_url = urljoin(page_url, href)
            # 站内链接优先保留
            if not full_url.startswith("http://www.qhdgjj.com") and not full_url.startswith("https://www.qhdgjj.com"):
                continue

            raw_text = a.get_text(" ", strip=True)
            dt, title = _extract_date_and_title(raw_text)

            # 兜底：如果标题为空，从父容器获取
            if not title:
                title = norm(a.parent.get_text(" ", strip=True) if a.parent else raw_text)

            if not title or len(title) < 4:
                continue

            key = (full_url, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": mark_income_related(title),
                "url": full_url,
                "date": dt,
                "source": "qhdgjj_tzgg",
            })
        except Exception:
            continue

    return results


def crawl_qhdgjj_tzgg(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取秦皇岛公积金网 - 通知公告（返回 title/url/date/source 列表）"""
    now = current_time or now_cn()
    since = now - timedelta(days=1)
    session = make_session()
    results: list[dict] = []
    seen_urls = set()

    for p in range(1, max_pages + 1):
        # 该站点可能使用分页参数不同，尝试常见格式
        if p == 1:
            page_url = INDEX_URL
        else:
            page_url = f"{INDEX_URL}&page={p}"

        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[QHDGJJ] Crawl error(p{p}): {e}")
            break

        page_items = _extract_items(page_url, resp.text)
        if not page_items:
            continue

        page_has_new = False
        for it in page_items:
            if it["url"] in seen_urls:
                continue
            seen_urls.add(it["url"])
            results.append(it)
            page_has_new = True

        if p > 1 and not page_has_new:
            break

    # keep only near-24h items (by date granularity)
    keep = []
    for it in results:
        d = it.get("date")
        if not d:
            continue
        if d >= since.date():
            keep.append(it)

    # sort newest first
    keep.sort(key=lambda x: (x.get("date") or now.date(), x.get("title", "")), reverse=True)
    return keep
