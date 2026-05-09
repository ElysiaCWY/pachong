# -*- coding: utf-8 -*-
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd

INDEX_URL = "http://www.zf365.com.cn/tzgg2/index.jhtml"


def _parse_chinese_date(text: str) -> datetime | None:
    if not text:
        return None
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if m:
        return parse_ymd(m.group(1))
    m2 = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
    if m2:
        y, mo, d = m2.group(1), m2.group(2).zfill(2), m2.group(3).zfill(2)
        try:
            return parse_ymd(f"{y}-{mo}-{d}")
        except Exception:
            return None
    return None


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    results: list[dict] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        try:
            href = norm(a.get("href") or "")
            title = norm(a.get_text(" ", strip=True))
            if not href or not title:
                continue

            full = urljoin(page_url, href)

            # 保留站内详情页链接，通常以 .jhtml 或 .html 结尾
            if not full.lower().endswith(('.jhtml', '.html')):
                continue

            # 有时列表项不在 /tzgg2/ 下，但我们只保留 domain 内链接
            if 'zf365.com.cn' not in full:
                continue

            # 尝试解析日期
            dt = None
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", title)
            if m:
                dt = parse_ymd(m.group(1))
                title = norm(title.replace(m.group(1), "", 1))

            if dt is None:
                container = a.parent.parent if a.parent and a.parent.parent else (a.parent if a.parent else None)
                container_text = norm(container.get_text(" ", strip=True)) if container else ""
                dt = _parse_chinese_date(container_text)

            key = (full, title)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "title": mark_income_related(title),
                "url": full,
                "date": dt,
                "source": "zf365_tzgg",
            })
        except Exception:
            continue

    return results


def crawl_zf365_tzgg(current_time: datetime | None = None, max_pages: int = 2) -> list[dict]:
    """抓取 zf365 通知公告列表（返回 title/url/date/source 列表）。外层负责近24小时筛选。"""
    _ = current_time or now_cn()
    session = make_session()
    results: list[dict] = []
    seen_urls = set()

    for page_no in range(1, max_pages + 1):
        page_url = INDEX_URL if page_no <= 1 else INDEX_URL
        try:
            resp = session.get(page_url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                break
        except Exception as e:
            print(f"[ZF365] Crawl error(p{page_no}): {e}")
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

        if page_no > 1 and not page_has_new:
            break

    results.sort(key=lambda x: (x.get("date") or now_cn().date(), x.get("title", "")), reverse=True)
    return results
