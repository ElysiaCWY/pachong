# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from .common import make_session, mark_income_related, now_cn, norm, parse_ymd


HLBE_GJJ_INDEX = "https://zjj.hlbe.gov.cn/News/showList/8007/page_1.html"


def _page_url(page_no: int) -> str:
    if page_no <= 1:
        return HLBE_GJJ_INDEX
    return HLBE_GJJ_INDEX.replace("page_1.html", f"page_{page_no}.html")


def _extract_items(page_url: str, html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[dict] = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = norm(a_tag.get("href") or "")
        if "/News/show/" not in href:
            continue

        title = norm(a_tag.get("title") or a_tag.get_text(" ", strip=True))
        if not title or len(title) < 4:
            continue

        container = a_tag.parent if a_tag.parent else None
        container_text = norm(container.get_text(" ", strip=True)) if container else ""
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", container_text)
        if not match:
            parent = container.parent if container and container.parent else None
            parent_text = norm(parent.get_text(" ", strip=True)) if parent else ""
            match = re.search(r"(20\d{2}-\d{2}-\d{2})", parent_text)

        if not match:
            continue

        article_date = parse_ymd(match.group(1))
        if not article_date:
            continue

        full_url = urljoin(page_url, href)
        key = (title, full_url, article_date)
        if key in seen:
            continue
        seen.add(key)

        items.append(
            {
                "title": mark_income_related(title),
                "url": full_url,
                "date": article_date,
                "source": "hlbe_gjj_policy",
            }
        )

    return items


def crawl_hlbe_gjj_policy(current_time: datetime | None = None, max_pages: int = 3) -> list[dict]:
    """抓取呼伦贝尔市住房公积金政策法规列表，仅保留近24小时内条目。"""
    now = current_time or now_cn()
    since = now - timedelta(hours=24)
    session = make_session()
    results: list[dict] = []
    seen_urls: set[str] = set()

    for page_no in range(1, max_pages + 1):
        page_url = _page_url(page_no)
        try:
            resp = session.get(page_url, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
        except Exception as e:
            print(f"[HLBE GJJ] fetch error(page={page_no}): {e}")
            break

        page_items = _extract_items(page_url, resp.text)
        if not page_items:
            break

        page_has_recent = False
        page_hit_older = False
        for item in page_items:
            item_date = item.get("date")
            if not item_date:
                continue
            if item_date > now.date():
                continue
            if item_date < since.date():
                page_hit_older = True
                continue

            page_has_recent = True
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            results.append(item)

        if page_hit_older or not page_has_recent:
            break

    results.sort(key=lambda x: (x["date"], x["title"]), reverse=True)
    return results